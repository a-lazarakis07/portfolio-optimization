import json

import pandas as pd

from conftest import FakeProvider, prices
from portfolio_backtester.cli import main
from portfolio_backtester.data.pipeline import Pipeline
from portfolio_backtester.data.verify import verify_saved


def test_saved_validation_detects_tampered_returns(settings):
    Pipeline(settings, FakeProvider({"AAA": prices()})).run(["AAA"], end=pd.Timestamp("2024-01-04"))
    assert verify_saved(settings, ["AAA"])["valid"]
    path = settings.path("processed_data_path") / "daily_returns.parquet"
    returns = pd.read_parquet(path)
    returns.iloc[1, 0] = 0.0
    returns.to_parquet(path)
    report = verify_saved(settings, ["AAA"])
    assert not report["valid"]
    assert any("daily_returns" in issue for issue in report["errors"])


def test_saved_validation_detects_missing_raw(settings):
    Pipeline(settings, FakeProvider({"AAA": prices()})).run(["AAA"], end=pd.Timestamp("2024-01-04"))
    (settings.path("raw_data_path") / "AAA.parquet").unlink()
    assert not verify_saved(settings, ["AAA"])["valid"]


def test_saved_validation_rejects_incomplete_manifest(settings):
    Pipeline(settings, FakeProvider({"AAA": prices(), "BBB": RuntimeError("Offline")})).run(["AAA", "BBB"], end=pd.Timestamp("2024-01-04"))
    assert not verify_saved(settings, ["AAA", "BBB"])["valid"]


def test_cli_help_is_available_without_network(capsys):
    import pytest
    with pytest.raises(SystemExit) as result:
        main(["--help"])
    assert result.value.code == 0
    assert "download" in capsys.readouterr().out


def test_cli_rejects_subset_overwriting_main_datasets(capsys):
    assert main(["download", "--tickers", "AAPL"]) == 2
    assert "--smoke" in capsys.readouterr().err
