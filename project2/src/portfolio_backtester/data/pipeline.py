"""Coordinate retries, isolated ticker failures, validation, and persisted datasets."""

from collections.abc import Callable
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import logging
import platform
import time
from typing import Any, TypeVar
import uuid

import numpy as np
import pandas as pd

from portfolio_backtester import __version__
from portfolio_backtester.config import Settings
from .calendar import latest_completed_session, trading_sessions
from .provider import DataProvider, METADATA_COLUMNS, NUMERIC_COLUMNS, empty_prices
from .storage import atomic_json, atomic_parquet, atomic_target, merge_prices, pipeline_lock
from .transform import build_datasets
from .universe import validate_tickers
from .validation import validate_prices

LOGGER = logging.getLogger(__name__)
T = TypeVar("T")
SCHEMA_VERSION = "1.0.0"
ADJUSTMENT_CONVENTION = (
    "Yahoo provider OHLC retained with auto_adjust=False, back_adjust=False, repair=False. "
    "Yahoo unadjusted Close can already reflect stock splits; it is not original as-traded tape. "
    "Adjusted Close is Yahoo's dividend/split-adjusted series. Returns = Adjusted Close[t] / "
    "Adjusted Close[t-1] - 1 over adjacent XNYS sessions, without filling or adding dividends again."
)


class Pipeline:
    """A reusable orchestration layer independent of provider implementation."""

    def __init__(self, settings: Settings, provider: DataProvider):
        self.settings = settings
        self.provider = provider

    def _retry(self, operation: Callable[[], T], description: str) -> T:
        for attempt in range(self.settings.retry_attempts):
            try:
                time.sleep(self.settings.pacing_seconds)
                return operation()
            except Exception as error:
                if attempt + 1 == self.settings.retry_attempts:
                    raise
                delay = min(self.settings.backoff_seconds * 2 ** attempt, self.settings.max_backoff_seconds)
                LOGGER.warning("%s failed on attempt %d: %s; retrying in %.1fs", description, attempt + 1, error, delay)
                time.sleep(delay)
        raise RuntimeError("Retry loop terminated unexpectedly")

    def _fetch(self, ticker: str, start: pd.Timestamp, end: pd.Timestamp):
        def operation():
            response = self.provider.fetch_prices(ticker, start, end)
            if response.frame.empty:
                raise ValueError(f"Empty provider response for {ticker} ({start.date()} through {end.date()})")
            return response
        return self._retry(operation, f"Price download for {ticker}")

    def _validate(self, frame, ticker, sessions, first_trade_date=None):
        return validate_prices(frame, ticker, sessions, self.settings.expected_currency,
                               self.settings.extreme_return_threshold, first_trade_date)

    def run(self, tickers: list[str], *, mode: str = "download", full_refresh: bool = False,
            end: pd.Timestamp | None = None) -> dict[str, Any]:
        """Initialize or update prices; a completed manifest is the publication marker."""
        validate_tickers(tickers)
        if mode not in {"download", "update"}:
            raise ValueError("mode must be download or update")
        with pipeline_lock(self.settings.path("metadata_path") / ".pipeline.lock"):
            return self._run(tickers, mode, full_refresh, end)

    def _run(self, tickers, mode, full_refresh, end):
        settings = self.settings
        if end is None:
            end = latest_completed_session(delay_minutes=settings.completion_delay_minutes)
            if settings.end_date_policy == "fixed":
                end = min(end, settings.end_date)
        sessions = trading_sessions(settings.start_date, pd.Timestamp(end))
        if sessions.empty:
            raise ValueError("Configured date range contains no trading sessions")
        end = sessions[-1]
        metadata_dir = settings.path("metadata_path")
        manifest_path = metadata_dir / "dataset_manifest.json"
        previous_manifest = {}
        if manifest_path.exists():
            try:
                previous_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                LOGGER.warning("Previous manifest is unreadable; history coverage will be rechecked")
        manifest = {
            "run_id": uuid.uuid4().hex, "status": "running", "provider": self.provider.name,
            "download_timestamp": pd.Timestamp.now(tz="UTC").isoformat(), "mode": mode,
            "full_refresh": full_refresh, "start_date": str(settings.start_date.date()),
            "end_date": str(end.date()), "configured_universe": tickers,
            "successful_tickers": [], "downloaded_tickers": [], "skipped_tickers": [],
            "failed_tickers": {}, "adjusted_price_convention": ADJUSTMENT_CONVENTION,
            "schema_version": SCHEMA_VERSION, "package_version": __version__,
            "python_version": platform.python_version(), "dependency_versions": {},
            "refresh_overlap_days": settings.refresh_overlap_days,
            "limitations": ["Current snapshot universe retains survivorship bias.",
                            "Incremental updates are not guaranteed to equal full refreshes.",
                            "Current company metadata is not point-in-time historical data."],
            "ticker_details": {}, "automatic_full_refresh_tickers": [], "cache_issues": {},
        }
        for package in ["pandas", "numpy", "yfinance", "pyarrow", "PyYAML", "exchange-calendars"]:
            try:
                manifest["dependency_versions"][package] = version(package)
            except PackageNotFoundError:
                manifest["dependency_versions"][package] = "not installed"
        universe_manifest = settings.path("universe_manifest_path")
        if universe_manifest.exists():
            manifest["universe_definition"] = json.loads(universe_manifest.read_text(encoding="utf-8"))
        universe_path = settings.path("universe_path")
        if universe_path.exists():
            manifest["universe_file_sha256"] = hashlib.sha256(universe_path.read_bytes()).hexdigest()
        atomic_json(manifest, manifest_path)
        download_failures: dict[str, str] = {}
        quality: dict[str, Any] = {"run_id": manifest["run_id"], "generated_at": manifest["download_timestamp"],
                                   "tickers": {}, "download_failures": download_failures, "processing_errors": []}
        frames = []
        for index, ticker in enumerate(tickers):
            if index and index % settings.batch_size == 0:
                time.sleep(settings.batch_pause_seconds)
            path = settings.path("raw_data_path") / f"{ticker}.parquet"
            old = empty_prices()
            previous_detail = previous_manifest.get("ticker_details", {}).get(ticker, {})
            previous_first_trade = previous_detail.get("first_trade_date")
            first_trade_date = pd.Timestamp(previous_first_trade) if previous_first_trade else None
            try:
                if path.exists():
                    try:
                        existing = pd.read_parquet(path)
                        if set(empty_prices().columns) - set(existing.columns):
                            raise ValueError("Saved raw schema is invalid")
                        if not pd.api.types.is_datetime64_any_dtype(existing.date) or existing.date.isna().any():
                            raise ValueError("Saved raw dates are invalid")
                        existing_sessions = trading_sessions(existing.date.min(), existing.date.max()) if not existing.empty else sessions
                        if not self._validate(existing, ticker, existing_sessions)["valid"]:
                            raise ValueError("Saved raw data failed validation")
                        old = existing
                    except Exception as error:
                        manifest["cache_issues"][ticker] = f"{type(error).__name__}: {error}"
                        LOGGER.warning("%s: unusable cache retained for inspection; fetching complete history: %s", ticker, error)
                        with atomic_target(metadata_dir / "rejected" / f"{ticker}_{manifest['run_id']}_cache.parquet") as target:
                            target.write_bytes(path.read_bytes())
                        old = empty_prices()
                cached = old.loc[old.date.between(sessions[0], end)].copy()
                previous_start = previous_manifest.get("start_date")
                range_extended = previous_start is not None and settings.start_date < pd.Timestamp(previous_start)
                unverified_start = (not old.empty and old.date.min() > sessions[0]
                                    and (first_trade_date is None or first_trade_date < sessions[0]))
                needs_history = range_extended or unverified_start
                cached_valid = (not cached.empty and not needs_history
                                and self._validate(cached, ticker, sessions, first_trade_date)["valid"])
                if cached_valid and not full_refresh and cached.date.max() >= end:
                    manifest["skipped_tickers"].append(ticker)
                    LOGGER.info("[%d/%d] %s: no newer session; using validated cache", index + 1, len(tickers), ticker)
                else:
                    start = settings.start_date
                    if not full_refresh and not old.empty and not needs_history:
                        start = max(start, old.date.max() - pd.Timedelta(days=settings.refresh_overlap_days))
                    response = self._fetch(ticker, start, end)
                    new = response.frame
                    first_trade_date = response.first_trade_date
                    # Validate downloaded rows before duplicate resolution or overlap replacement.
                    fetch_sessions = trading_sessions(start, end)
                    new_quality = self._validate(new, ticker, fetch_sessions, first_trade_date)
                    if not new_quality["valid"]:
                        quality["tickers"][ticker] = new_quality
                        atomic_parquet(new, metadata_dir / "rejected" / f"{ticker}_{manifest['run_id']}.parquet")
                        raise ValueError("Downloaded data failed validation; observations saved under metadata/rejected")
                    if not old.empty and self._missing_overlap_values(old, new):
                        atomic_parquet(new, metadata_dir / "rejected" / f"{ticker}_{manifest['run_id']}.parquet")
                        raise ValueError("Downloaded overlap loses previously valid values; previous cache preserved and response quarantined")
                    if not full_refresh and not old.empty and self._adjustment_changed(old, new):
                        LOGGER.warning("%s: overlapping price adjustment basis changed; refreshing full history", ticker)
                        manifest["automatic_full_refresh_tickers"].append(ticker)
                        response = self._fetch(ticker, settings.start_date, end)
                        new = response.frame
                        first_trade_date = response.first_trade_date
                        candidate = new
                    else:
                        candidate = new if full_refresh or old.empty else merge_prices(old, new)
                    prior_in_scope = old.loc[old.date.between(sessions[0], end)]
                    dropped_dates = prior_in_scope.date[~prior_in_scope.date.isin(candidate.date)]
                    if len(dropped_dates) or self._missing_overlap_values(prior_in_scope, candidate):
                        atomic_parquet(candidate, metadata_dir / "rejected" / f"{ticker}_{manifest['run_id']}.parquet")
                        raise ValueError("Final refresh loses previously valid dates or values; response quarantined and previous cache preserved")
                    candidate = candidate.sort_values(["date", "ticker"]).reset_index(drop=True)
                    in_scope = candidate.loc[candidate.date.between(sessions[0], end)].copy()
                    candidate_quality = self._validate(in_scope, ticker, sessions, first_trade_date)
                    quality["tickers"][ticker] = candidate_quality
                    if not candidate_quality["valid"]:
                        atomic_parquet(candidate, metadata_dir / "rejected" / f"{ticker}_{manifest['run_id']}.parquet")
                        raise ValueError("Merged dataset failed validation; previous raw file preserved")
                    atomic_parquet(candidate, path)
                    cached = in_scope
                    manifest["downloaded_tickers"].append(ticker)
                    LOGGER.info("[%d/%d] %s: saved %d rows through %s", index + 1, len(tickers), ticker, len(candidate), end.date())
                manifest["successful_tickers"].append(ticker)
            except Exception as error:
                message = f"{type(error).__name__}: {error}"
                download_failures[ticker] = message
                LOGGER.error("[%d/%d] %s: %s", index + 1, len(tickers), ticker, message)
                cached = old.loc[old.date.between(sessions[0], end)].copy()
            saved_quality = self._validate(cached, ticker, sessions, first_trade_date)
            if ticker not in quality["tickers"]:
                quality["tickers"][ticker] = saved_quality
            elif ticker in download_failures:
                quality["tickers"][ticker]["cached_data_quality"] = saved_quality
            # Previously valid history remains usable as partial history after a failed update.
            historical_sessions = sessions[sessions <= cached.date.max()] if not cached.empty else sessions
            usable_cache = not cached.empty and self._validate(cached, ticker, historical_sessions)["valid"]
            if usable_cache:
                frames.append(cached)
            manifest["ticker_details"][ticker] = {
                "rows": len(cached), "start_date": str(cached.date.min().date()) if not cached.empty else None,
                "end_date": str(cached.date.max().date()) if not cached.empty else None,
                "first_trade_date": str(first_trade_date.date()) if first_trade_date is not None else None,
                "currency": sorted(cached.currency.dropna().unique().tolist()) if not cached.empty else [],
            }
        raw = pd.concat(frames, ignore_index=True) if frames else empty_prices()
        manifest["failed_tickers"] = download_failures
        manifest["available_tickers"] = sorted(raw.ticker.unique().tolist())
        manifest["actual_start_date"] = str(raw.date.min().date()) if not raw.empty else None
        manifest["actual_end_date"] = str(raw.date.max().date()) if not raw.empty else None
        manifest["row_count"] = len(raw)
        manifest["processed_files"] = {}
        try:
            long, wide, returns = build_datasets(raw, tickers, sessions)
            for name, dataset, indexed in [("prices", long, False), ("adjusted_close", wide, True), ("daily_returns", returns, True)]:
                target = settings.path("processed_data_path") / f"{name}.parquet"
                atomic_parquet(dataset, target, index=indexed)
                manifest["processed_files"][target.name] = {"rows": len(dataset), "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
            if long.empty:
                quality["processing_errors"].append("Required processed prices dataset is empty")
        except Exception as error:
            quality["processing_errors"].append(f"{type(error).__name__}: {error}")
            LOGGER.exception("Processed dataset publication failed")
        quality["missing_tickers"] = sorted(set(tickers) - set(manifest["available_tickers"]))
        quality["valid"] = (not download_failures and not quality["processing_errors"]
                            and not quality["missing_tickers"] and all(report["valid"] for report in quality["tickers"].values()))
        quality["warning_count"] = sum(sum(i["severity"] == "warning" for i in r["issues"]) for r in quality["tickers"].values())
        manifest["status"] = "complete" if quality["valid"] else "incomplete"
        manifest["completed_at"] = pd.Timestamp.now(tz="UTC").isoformat()
        atomic_json({"run_id": manifest["run_id"], "failed_tickers": download_failures}, metadata_dir / "download_failures.json")
        atomic_json(quality, metadata_dir / "data_quality_report.json")
        atomic_json(manifest, manifest_path)
        return manifest

    @staticmethod
    def _adjustment_changed(old: pd.DataFrame, new: pd.DataFrame) -> bool:
        overlap = old.merge(new, on=["ticker", "date"], suffixes=("_old", "_new"))
        if overlap.empty:
            return False
        old_factor = overlap.adjusted_close_old.div(overlap.close_old)
        new_factor = overlap.adjusted_close_new.div(overlap.close_new)
        changed_factor = ~np.isclose(old_factor, new_factor, rtol=1e-5, atol=1e-8, equal_nan=True)
        # Splits may also restate Yahoo's otherwise unadjusted OHLC history.
        changed_split = ~np.isclose(overlap.stock_splits_old, overlap.stock_splits_new, equal_nan=True)
        changed_close = ~np.isclose(overlap.close_old, overlap.close_new, rtol=1e-5, atol=1e-8, equal_nan=True)
        new_dates = new.loc[~new.date.isin(old.date)]
        new_split = new_dates.stock_splits.fillna(0).ne(0).any()
        return bool(changed_factor.any() or changed_split.any() or changed_close.any() or new_split)

    @staticmethod
    def _missing_overlap_values(old: pd.DataFrame, new: pd.DataFrame) -> bool:
        overlap = old.merge(new, on=["ticker", "date"], suffixes=("_old", "_new"))
        return any((overlap[f"{column}_old"].notna() & overlap[f"{column}_new"].isna()).any()
                   for column in NUMERIC_COLUMNS)

    def refresh_metadata(self, tickers: list[str], *, force: bool = False) -> dict[str, Any]:
        """Run company metadata requests separately, preserving prior successful profiles."""
        validate_tickers(tickers)
        settings = self.settings
        metadata_dir = settings.path("metadata_path")
        with pipeline_lock(metadata_dir / ".pipeline.lock"):
            target = metadata_dir / "company_metadata.parquet"
            frame = pd.read_parquet(target) if target.exists() else pd.DataFrame(columns=METADATA_COLUMNS)
            failures = {}
            successful = []
            skipped = []
            for index, ticker in enumerate(tickers):
                if index and index % settings.batch_size == 0:
                    time.sleep(settings.batch_pause_seconds)
                old = frame.loc[frame.ticker.eq(ticker)]
                policy = settings.metadata_refresh_policy
                if not force and not old.empty and policy in {"missing", "stale"}:
                    fetched = pd.to_datetime(old.metadata_fetched_at.iloc[-1], utc=True, errors="coerce")
                    fresh = pd.notna(fetched) and (pd.Timestamp.now(tz="UTC") - fetched).days < settings.metadata_max_age_days
                    if policy == "missing" or fresh:
                        skipped.append(ticker)
                        continue
                try:
                    row = self._retry(lambda: self.provider.fetch_metadata(ticker), f"Metadata for {ticker}")
                    new = pd.DataFrame([row], columns=METADATA_COLUMNS)
                    frame = pd.concat([frame.loc[~frame.ticker.eq(ticker)], new], ignore_index=True) if not frame.empty else new
                    successful.append(ticker)
                    LOGGER.info("[%d/%d] %s: metadata retrieved", index + 1, len(tickers), ticker)
                except Exception as error:
                    failures[ticker] = f"{type(error).__name__}: {error}"
                    LOGGER.error("%s: metadata unavailable: %s", ticker, error)
            frame["market_cap"] = pd.to_numeric(frame.market_cap, errors="coerce").astype("float64")
            atomic_parquet(frame.sort_values("ticker").reset_index(drop=True), target)
            report = {"generated_at": pd.Timestamp.now(tz="UTC").isoformat(), "successful_tickers": successful,
                      "skipped_tickers": skipped, "failed_tickers": failures,
                      "limitation": "Current company metadata is not historically point-in-time accurate."}
            atomic_json(report, metadata_dir / "metadata_refresh_report.json")
            return report
