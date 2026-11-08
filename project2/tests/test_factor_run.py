import json

import pandas as pd
import pytest

from conftest import ROOT
from test_regression import synthetic_data
from portfolio_backtester.data.storage import atomic_json, atomic_parquet
from portfolio_backtester.factors.download import file_hash
from portfolio_backtester.factors.run import run_factor_regression, load_regression_artifacts


def saved_inputs(settings):
    returns, factors, _ = synthetic_data()
    stocks_path = settings.path("processed_data_path") / "daily_returns.parquet"
    atomic_parquet(returns, stocks_path, index=True)
    atomic_parquet(factors, settings.path("factor_data_path"), index=True)
    atomic_json({"status": "complete", "processed_files": {"daily_returns.parquet": {"sha256": file_hash(stocks_path)}}},
                settings.path("metadata_path") / "dataset_manifest.json")
    atomic_json({"status": "complete", "processed_units": "decimal daily returns", "processed_sha256": file_hash(settings.path("factor_data_path")),
                 "sources": {}, "run_id": "synthetic", "downloaded_at": "2026-01-01T00:00:00Z"}, settings.path("factor_manifest_path"))
    return stocks_path


def test_regression_publishes_panel_results_csv_and_failure_reasons(settings):
    stocks_path = saved_inputs(settings)
    before = stocks_path.read_bytes()
    report = run_factor_regression(settings, tickers=["AAA", "MISSING"])
    assert report["successful_tickers"] == ["AAA"]
    assert report["failed_tickers"]["MISSING"]["reason"] == "insufficient_valid_observations"
    assert report["status"] == "complete_with_failures"
    assert settings.path("regression_csv_path").exists()
    results, read_report = load_regression_artifacts(settings)
    assert results.ticker.tolist() == ["AAA"]
    assert read_report["run_id"] == report["run_id"]
    assert stocks_path.read_bytes() == before


def test_changed_factor_input_cannot_be_reported_as_old_results(settings):
    saved_inputs(settings)
    run_factor_regression(settings, tickers=["AAA"])
    factors = pd.read_parquet(settings.path("factor_data_path"))
    factors.iloc[-1, 0] += 0.01
    atomic_parquet(factors, settings.path("factor_data_path"), index=True)
    with pytest.raises(ValueError, match="changed|stale|hash"):
        load_regression_artifacts(settings)


def test_missing_or_invalid_input_manifest_fails_clearly(settings):
    with pytest.raises((ValueError, OSError)):
        run_factor_regression(settings, tickers=["AAA"])
    saved_inputs(settings)
    path = settings.path("factor_manifest_path")
    manifest = json.loads(path.read_text())
    manifest["status"] = "failed"
    atomic_json(manifest, path)
    with pytest.raises(ValueError, match="complete"):
        run_factor_regression(settings, tickers=["AAA"])


def test_reporting_rejects_a_new_snapshot_published_during_input_verification(settings, monkeypatch):
    import portfolio_backtester.factors.run as module
    saved_inputs(settings)
    run_factor_regression(settings, tickers=["AAA"])
    original_load = module.load_inputs
    def publish_then_load(config):
        frame = pd.read_parquet(config.path("factor_data_path"))
        frame.iloc[-1, 0] += 0.01
        atomic_parquet(frame, config.path("factor_data_path"), index=True)
        manifest = json.loads(config.path("factor_manifest_path").read_text())
        manifest["processed_sha256"] = file_hash(config.path("factor_data_path"))
        atomic_json(manifest, config.path("factor_manifest_path"))
        return original_load(config)
    monkeypatch.setattr(module, "load_inputs", publish_then_load)
    with pytest.raises(ValueError, match="changed|stale|identity"):
        load_regression_artifacts(settings)
