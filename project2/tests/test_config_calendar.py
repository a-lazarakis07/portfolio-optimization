import pandas as pd
import pytest

from conftest import ROOT
from portfolio_backtester.config import load_settings
from portfolio_backtester.data.calendar import latest_completed_session, trading_sessions
from portfolio_backtester.data.universe import load_universe


def test_configuration_paths_are_independent_of_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = load_settings(ROOT / "config/settings.yaml")
    assert config.root == ROOT
    assert config.path("raw_data_path") == ROOT / "data/raw"
    assert config.start_date == pd.Timestamp("1995-01-01")


@pytest.mark.parametrize("patch", ["raw_data_path: ../outside", "batch_size: 0", "frequency: 1h", "data_provider: unknown", "refresh_overlap_days: -1", "metadata_refresh_policy: invalid"])
def test_bad_configuration_is_rejected(tmp_path, patch):
    path = tmp_path / "settings.yaml"
    path.write_text(patch)
    with pytest.raises(ValueError):
        load_settings(path, root=tmp_path)


def test_universe_requires_valid_unique_tickers(tmp_path):
    path = tmp_path / "universe.csv"
    path.write_text("ticker\nAAPL\nAAPL\n")
    with pytest.raises(ValueError, match="Duplicate"):
        load_universe(path)
    path.write_text("ticker\n../BAD\n")
    with pytest.raises(ValueError):
        load_universe(path)


def test_frozen_universe_v2_matches_60_curated_candidates_and_all_sectors():
    import yaml
    tickers = load_universe(ROOT / "config/universe.csv")
    candidates = yaml.safe_load((ROOT / "config/universe_v2_candidates.yaml").read_text())
    assert len(tickers) == len(set(tickers)) == 60
    assert set(tickers) == {ticker for group in candidates.values() for ticker in group}
    frame = pd.read_csv(ROOT / "config/universe.csv")
    assert len(frame.sector.unique()) == len(candidates) == 11


def test_exchange_holiday_is_not_a_session():
    sessions = trading_sessions(pd.Timestamp("2024-07-03"), pd.Timestamp("2024-07-05"))
    assert sessions.tolist() == [pd.Timestamp("2024-07-03"), pd.Timestamp("2024-07-05")]


def test_intraday_and_early_close_are_handled():
    assert latest_completed_session(pd.Timestamp("2024-07-03T16:59Z"), delay_minutes=0) == pd.Timestamp("2024-07-02")
    assert latest_completed_session(pd.Timestamp("2024-07-03T17:01Z"), delay_minutes=0) == pd.Timestamp("2024-07-03")
    assert latest_completed_session(pd.Timestamp("2024-07-04T23:00Z"), delay_minutes=0) == pd.Timestamp("2024-07-03")


@pytest.mark.parametrize("patch", [
    "regression_csv_path: config/universe.csv",
    "factor_manifest_path: data/metadata/factor_last_attempt.json",
    "dashboard_path: Papers/dashboard.html",
    "factor_data_path: data/processed/daily_returns.parquet",
    "regression_report_path: data/metadata/saved_data_validation.json",
])
def test_phase2_paths_cannot_overwrite_protected_or_implicit_outputs(tmp_path, patch):
    path = tmp_path / "settings.yaml"
    path.write_text(patch)
    with pytest.raises(ValueError):
        load_settings(path, root=tmp_path)
