"""Publish reproducible factor regressions independently of Phase 1 stock writes."""

from importlib.metadata import version
from contextlib import contextmanager
import json
import logging
import uuid

import pandas as pd

from portfolio_backtester import __version__
from portfolio_backtester.config import Settings, validate_phase2_paths
from portfolio_backtester.data.storage import atomic_json, atomic_parquet, atomic_target, pipeline_lock
from portfolio_backtester.data.universe import load_universe, validate_tickers
from . import MODEL_VERSION
from .alignment import build_regression_panel
from .download import file_hash
from .regression import RESULT_COLUMNS, fit_regressions

LOGGER = logging.getLogger(__name__)
INTERPRETATION = "Historical factor regression estimates. Not forward-looking return forecasts."


@contextmanager
def input_locks(settings: Settings):
    """Use the existing writers' locks in stock-then-factor order."""
    with pipeline_lock(settings.path("metadata_path") / ".pipeline.lock"):
        with pipeline_lock(settings.path("factor_manifest_path").parent / ".factors.lock"):
            yield


def _read_inputs(settings: Settings) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Require complete, hash-verified price and factor publications before analysis."""
    returns_path = settings.path("processed_data_path") / "daily_returns.parquet"
    factor_path = settings.path("factor_data_path")
    stock_manifest = json.loads((settings.path("metadata_path") / "dataset_manifest.json").read_text())
    factor_manifest = json.loads(settings.path("factor_manifest_path").read_text())
    if stock_manifest.get("status") != "complete" or factor_manifest.get("status") != "complete":
        raise ValueError("Price and factor input manifests must both be complete")
    stocks_hash, factor_hash = file_hash(returns_path), file_hash(factor_path)
    if stocks_hash != stock_manifest["processed_files"]["daily_returns.parquet"]["sha256"]:
        raise ValueError("Daily Returns hash differs from the Phase 1 publication; validate or rebuild prices")
    if factor_hash != factor_manifest["processed_sha256"]:
        raise ValueError("Factor Data hash differs from its published snapshot")
    if factor_manifest.get("processed_units") != "decimal daily returns":
        raise ValueError("Factor units must explicitly be decimal daily returns")
    provenance = {"stock_returns_path": str(returns_path.relative_to(settings.root)), "stock_returns_sha256": stocks_hash,
                  "factor_data_path": str(factor_path.relative_to(settings.root)), "factor_data_sha256": factor_hash,
                  "factor_snapshot_id": factor_manifest["run_id"], "factor_downloaded_at": factor_manifest["downloaded_at"],
                  "factor_sources": factor_manifest["sources"]}
    stocks, factors = pd.read_parquet(returns_path), pd.read_parquet(factor_path)
    if file_hash(returns_path) != stocks_hash or file_hash(factor_path) != factor_hash:
        raise ValueError("Research inputs changed during snapshot reading")
    return stocks, factors, provenance


def load_inputs(settings: Settings) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Read one generation while excluding the stock and factor publishers."""
    with input_locks(settings):
        return _read_inputs(settings)


def run_factor_regression(settings: Settings, *, tickers: list[str] | None = None,
                          as_of_date: pd.Timestamp | None = None) -> dict:
    """Save the standardized panel, historical estimates, and explicit failure records."""
    validate_phase2_paths(settings)
    tickers = validate_tickers(tickers) if tickers is not None else load_universe(settings.path("universe_path"))
    report_path = settings.path("regression_report_path")
    with pipeline_lock(report_path.parent / ".regression.lock"):
        try:
            stocks, factors, provenance = load_inputs(settings)
            panel, alignment, candidates = build_regression_panel(stocks, factors, tickers, settings, as_of_date=as_of_date)
            results, failures = fit_regressions(panel, tickers, candidates, settings, pd.Timestamp(alignment["as_of_date"]))
            report = {"run_id": uuid.uuid4().hex, "status": "running", "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
                      "model_version": MODEL_VERSION, "package_version": __version__,
                      "dependencies": {name: version(name) for name in ["pandas", "numpy", "statsmodels", "scipy"]},
                      "configured_tickers": tickers, "successful_tickers": results.ticker.tolist(), "failed_tickers": failures,
                      "input_provenance": provenance, "alignment": alignment,
                      "methodology": {"estimation_method": settings.estimation_method, "intercept": True,
                          "regression_window": settings.regression_window, "minimum_valid_observations": settings.minimum_valid_observations,
                          "annualization_factor": settings.annualization_factor, "alpha_annualization": "alpha_daily * annualization_factor; linear approximation, not realized annual investment return",
                          "residual_volatility": "sample residual standard deviation (ddof=1) * sqrt(annualization_factor)",
                          "standard_errors": "Conventional OLS (nonrobust); t-tests assume correctly specified errors",
                          "interpretation": INTERPRETATION},
                      "limitations": ["Current revised factor snapshots are not historical point-in-time data, even with as_of_date truncation.",
                          "Current stock selection retains survivorship bias.", "Yahoo adjusted prices are total-return proxies and may contain corporate-action errors.",
                          "OLS exposures and significance describe in-sample history and are not future alpha or expected-return forecasts."]}
            atomic_json(report, report_path)
            outputs = [("panel", settings.path("regression_panel_path"), panel),
                       ("results", settings.path("regression_results_path"), results)]
            report["outputs"] = {}
            for key, path, frame in outputs:
                atomic_parquet(frame, path)
                report["outputs"][key] = {"path": str(path.relative_to(settings.root)), "sha256": file_hash(path), "rows": len(frame)}
            csv_path = settings.path("regression_csv_path")
            with atomic_target(csv_path) as temporary:
                results.to_csv(temporary, index=False, date_format="%Y-%m-%d", float_format="%.15g")
            report["outputs"]["csv"] = {"path": str(csv_path.relative_to(settings.root)), "sha256": file_hash(csv_path), "rows": len(results)}
            report["status"] = "failed" if results.empty else ("complete_with_failures" if failures else "complete")
            report["median_r_squared"] = float(results.r_squared.median()) if not results.empty else None
            report["completed_at"] = pd.Timestamp.now(tz="UTC").isoformat()
            atomic_json(report, report_path)
            return report
        except Exception as error:
            failure = {"status": "failed", "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
                       "error": f"{type(error).__name__}: {error}"}
            atomic_json(failure, report_path.parent / "phase2" / "regression_last_attempt.json")
            if report_path.exists():
                prior = json.loads(report_path.read_text())
                if prior.get("status") == "running":
                    prior.update(failure)
                    atomic_json(prior, report_path)
            raise


def load_regression_artifacts(settings: Settings) -> tuple[pd.DataFrame, dict]:
    """Reject stale/mixed mathematical outputs before a dashboard is generated."""
    report = json.loads(settings.path("regression_report_path").read_text())
    if report.get("status") not in {"complete", "complete_with_failures"}:
        raise ValueError("No completed regression results available for reporting")
    provenance = report["input_provenance"]
    for key in ("stock_returns", "factor_data"):
        path = (settings.root / provenance[f"{key}_path"]).resolve()
        if not path.is_relative_to(settings.root) or file_hash(path) != provenance[f"{key}_sha256"]:
            raise ValueError(f"{key} input changed; regression results are stale")
    _, _, current = load_inputs(settings)
    if any(current[key] != provenance[key] for key in ("stock_returns_sha256", "factor_data_sha256")):
        raise ValueError("Research input identity changed; regression results are stale")
    for key, setting in [("panel", "regression_panel_path"), ("results", "regression_results_path"), ("csv", "regression_csv_path")]:
        if file_hash(settings.path(setting)) != report["outputs"][key]["sha256"]:
            raise ValueError(f"Published regression {key} hash mismatch; rerun factor regression")
    results = pd.read_parquet(settings.path("regression_results_path"))
    if results.empty or list(results.columns) != RESULT_COLUMNS or results.ticker.duplicated().any():
        raise ValueError("Regression results are empty or have an invalid schema")
    return results, report
