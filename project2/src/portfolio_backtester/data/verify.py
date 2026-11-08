"""Offline verification of persisted raw and processed datasets."""

import hashlib
import json
from typing import Any

import pandas as pd

from portfolio_backtester.config import Settings
from .calendar import trading_sessions
from .provider import empty_prices
from .storage import atomic_json, pipeline_lock
from .transform import build_datasets
from .validation import validate_prices


def verify_saved(settings: Settings, tickers: list[str]) -> dict[str, Any]:
    """Recompute expected outputs and compare their values and publication hashes."""
    directory = settings.path("metadata_path")
    with pipeline_lock(directory / ".pipeline.lock"):
        report: dict[str, Any] = {"checked_at": pd.Timestamp.now(tz="UTC").isoformat(),
                                   "valid": False, "errors": [], "tickers": {}}
        errors = report["errors"]
        try:
            manifest = json.loads((directory / "dataset_manifest.json").read_text(encoding="utf-8"))
            if manifest["status"] != "complete":
                errors.append(f"Dataset manifest status is {manifest['status']}")
            if manifest["configured_universe"] != tickers:
                errors.append("Configured universe differs from published universe; rerun the price pipeline")
            if manifest["start_date"] != str(settings.start_date.date()):
                errors.append("Configured start_date differs from the published dataset")
            sessions = trading_sessions(pd.Timestamp(manifest["start_date"]), pd.Timestamp(manifest["end_date"]))
            frames = []
            for ticker in tickers:
                path = settings.path("raw_data_path") / f"{ticker}.parquet"
                try:
                    frame = pd.read_parquet(path)
                    frame = frame.loc[frame.date.between(sessions[0], sessions[-1])].copy()
                    first_trade = manifest.get("ticker_details", {}).get(ticker, {}).get("first_trade_date")
                    quality = validate_prices(frame, ticker, sessions, settings.expected_currency,
                                              settings.extreme_return_threshold,
                                              pd.Timestamp(first_trade) if first_trade else None)
                    report["tickers"][ticker] = quality
                    if not quality["valid"]:
                        errors.append(f"{ticker}: raw data failed validation")
                    else:
                        frames.append(frame)
                except Exception as error:
                    errors.append(f"{ticker}: {type(error).__name__}: {error}")
            raw = pd.concat(frames, ignore_index=True) if frames else empty_prices()
            long, wide, returns = build_datasets(raw, tickers, sessions)
            for name, expected in [("prices", long), ("adjusted_close", wide), ("daily_returns", returns)]:
                path = settings.path("processed_data_path") / f"{name}.parquet"
                try:
                    saved = pd.read_parquet(path)
                    pd.testing.assert_frame_equal(saved, expected, check_freq=False, check_exact=False,
                                                  rtol=1e-12, atol=1e-12)
                    recorded = manifest["processed_files"][path.name]["sha256"]
                    if hashlib.sha256(path.read_bytes()).hexdigest() != recorded:
                        errors.append(f"{name}: file hash differs from the published manifest")
                except Exception as error:
                    errors.append(f"{name}: {type(error).__name__}: {error}")
            if long.empty:
                errors.append("Required prices dataset is empty")
            report["row_count"] = len(long)
            report["configured_tickers"] = len(tickers)
        except Exception as error:
            errors.append(f"Cannot verify dataset: {type(error).__name__}: {error}")
        report["valid"] = not errors
        atomic_json(report, directory / "saved_data_validation.json")
        return report
