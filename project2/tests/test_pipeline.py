import json
from dataclasses import replace

import pandas as pd

from conftest import FakeProvider, prices
from portfolio_backtester.data.pipeline import Pipeline

END = pd.Timestamp("2024-01-04")


def test_single_failure_preserves_successful_security(settings):
    provider = FakeProvider({"AAA": prices(), "BBB": RuntimeError("Temporary failure")})
    result = Pipeline(settings, provider).run(["AAA", "BBB"], end=END)
    assert result["successful_tickers"] == ["AAA"]
    assert list(result["failed_tickers"]) == ["BBB"]
    assert result["status"] == "incomplete"
    wide = pd.read_parquet(settings.path("processed_data_path") / "daily_returns.parquet")
    assert wide.BBB.isna().all()
    assert (settings.path("raw_data_path") / "AAA.parquet").exists()


def test_empty_provider_response_is_a_reported_failure(settings):
    provider = FakeProvider({"AAA": prices().iloc[:0]})
    result = Pipeline(settings, provider).run(["AAA"], end=END)
    assert result["failed_tickers"]
    assert result["status"] == "incomplete"
    assert not (settings.path("raw_data_path") / "AAA.parquet").exists()
    report = json.loads((settings.path("metadata_path") / "data_quality_report.json").read_text())
    assert not report["valid"]


def test_second_update_without_new_session_does_not_fetch(settings):
    provider = FakeProvider({"AAA": prices()})
    pipeline = Pipeline(settings, provider)
    pipeline.run(["AAA"], end=END)
    before = pd.read_parquet(settings.path("raw_data_path") / "AAA.parquet")
    provider.calls.clear()
    result = pipeline.run(["AAA"], mode="update", end=END)
    assert provider.calls == []
    assert result["skipped_tickers"] == ["AAA"]
    assert result["status"] == "complete"
    pd.testing.assert_frame_equal(pd.read_parquet(settings.path("raw_data_path") / "AAA.parquet"), before)


def test_incremental_fetch_uses_overlap_and_recalculates_boundary(settings):
    settings = replace(settings, refresh_overlap_days=1)
    provider = FakeProvider({"AAA": prices().iloc[:2]})
    pipeline = Pipeline(settings, provider)
    pipeline.run(["AAA"], end=pd.Timestamp("2024-01-03"))
    provider.responses["AAA"] = prices(values=(100.0, 115.0, 125.0))
    provider.calls.clear()
    result = pipeline.run(["AAA"], mode="update", end=END)
    assert provider.calls[0][1] == pd.Timestamp("2024-01-02")
    assert result["status"] == "complete"
    returns = pd.read_parquet(settings.path("processed_data_path") / "daily_returns.parquet")
    assert abs(returns.AAA.iloc[-1] - (125 / 115 - 1)) < 1e-12


def test_invalid_update_keeps_old_cache_and_reports_failure(settings):
    provider = FakeProvider({"AAA": prices().iloc[:2]})
    pipeline = Pipeline(settings, provider)
    pipeline.run(["AAA"], end=pd.Timestamp("2024-01-03"))
    path = settings.path("raw_data_path") / "AAA.parquet"
    old = path.read_bytes()
    provider.responses["AAA"] = prices().assign(adjusted_close=-1.0)
    result = pipeline.run(["AAA"], mode="update", end=END)
    assert result["failed_tickers"]
    assert path.read_bytes() == old
    assert list((settings.path("metadata_path") / "rejected").glob("*.parquet"))


def test_metadata_failure_is_separate_from_prices(settings):
    pipeline = Pipeline(settings, FakeProvider({"AAA": prices()}))
    assert pipeline.run(["AAA"], end=END)["status"] == "complete"
    report = pipeline.refresh_metadata(["AAA"])
    assert "AAA" in report["failed_tickers"]
    assert (settings.path("processed_data_path") / "prices.parquet").exists()


def test_full_refresh_replaces_history_and_bypasses_skip(settings):
    provider = FakeProvider({"AAA": prices()})
    pipeline = Pipeline(settings, provider)
    pipeline.run(["AAA"], end=END)
    provider.responses["AAA"] = prices(values=(80.0, 88.0, 96.8))
    provider.calls.clear()
    result = pipeline.run(["AAA"], mode="update", full_refresh=True, end=END)
    assert provider.calls[0][1] == settings.start_date
    assert result["status"] == "complete"
    assert pd.read_parquet(settings.path("raw_data_path") / "AAA.parquet").adjusted_close.iloc[0] == 80


def test_split_restatement_of_both_price_series_triggers_full_refresh(settings):
    settings = replace(settings, refresh_overlap_days=1)
    provider = FakeProvider({"AAA": prices()})
    pipeline = Pipeline(settings, provider)
    pipeline.run(["AAA"], end=END)
    revised = prices(values=(50.0, 55.0, 60.5, 61.0), dates=["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
    revised.loc[3, "stock_splits"] = 2.0
    provider.responses["AAA"] = revised
    result = pipeline.run(["AAA"], mode="update", end=pd.Timestamp("2024-01-05"))
    assert result["automatic_full_refresh_tickers"] == ["AAA"]
    saved = pd.read_parquet(settings.path("raw_data_path") / "AAA.parquet")
    assert saved.adjusted_close.tolist() == [50.0, 55.0, 60.5, 61.0]


def test_full_refresh_repairs_invalid_cached_schema(settings):
    path = settings.path("raw_data_path") / "AAA.parquet"
    path.parent.mkdir(parents=True)
    prices().drop(columns="adjusted_close").to_parquet(path)
    result = Pipeline(settings, FakeProvider({"AAA": prices()})).run(["AAA"], full_refresh=True, end=END)
    assert result["status"] == "complete"
    assert "adjusted_close" in pd.read_parquet(path)


def test_corrupt_cache_cannot_abort_other_tickers(settings):
    path = settings.path("raw_data_path") / "AAA.parquet"
    path.parent.mkdir(parents=True)
    prices().assign(date=["bad"] * 3).to_parquet(path)
    provider = FakeProvider({"AAA": prices(), "BBB": prices(ticker="BBB")})
    result = Pipeline(settings, provider).run(["AAA", "BBB"], end=END)
    assert "BBB" in result["successful_tickers"]
    assert result["status"] != "running"


def test_missing_overlap_observation_does_not_erase_valid_cache(settings):
    provider = FakeProvider({"AAA": prices()})
    pipeline = Pipeline(settings, provider)
    pipeline.run(["AAA"], end=END)
    path = settings.path("raw_data_path") / "AAA.parquet"
    old = path.read_bytes()
    revised = prices(values=(100.0, 110.0, 121.0, 122.0), dates=["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
    revised.loc[1, "adjusted_close"] = float("nan")
    provider.responses["AAA"] = revised
    result = pipeline.run(["AAA"], mode="update", end=pd.Timestamp("2024-01-05"))
    assert result["status"] == "incomplete"
    assert path.read_bytes() == old


def test_extending_start_date_fetches_newly_requested_history(settings):
    original = replace(settings, start_date=pd.Timestamp("2024-01-03"))
    provider = FakeProvider({"AAA": prices()})
    Pipeline(original, provider).run(["AAA"], end=END)
    provider.calls.clear()
    result = Pipeline(settings, provider).run(["AAA"], mode="update", end=END)
    assert provider.calls[0][1] == pd.Timestamp("2024-01-02")
    assert result["actual_start_date"] == "2024-01-02"


def test_full_refresh_cannot_drop_previously_valid_history(settings):
    provider = FakeProvider({"AAA": prices()})
    pipeline = Pipeline(settings, provider)
    pipeline.run(["AAA"], end=END)
    path = settings.path("raw_data_path") / "AAA.parquet"
    old = path.read_bytes()
    provider.responses["AAA"] = prices().iloc[1:]
    result = pipeline.run(["AAA"], full_refresh=True, end=END)
    assert result["status"] == "incomplete"
    assert path.read_bytes() == old


def test_automatic_full_refresh_rechecks_missing_historical_values(settings):
    settings = replace(settings, refresh_overlap_days=1)
    provider = FakeProvider({"AAA": prices()})
    pipeline = Pipeline(settings, provider)
    pipeline.run(["AAA"], end=END)
    path = settings.path("raw_data_path") / "AAA.parquet"
    old = path.read_bytes()
    revised = prices(values=(50.0, 55.0, 60.5, 61.0), dates=["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
    revised.loc[0, "adjusted_close"] = float("nan")
    provider.responses["AAA"] = revised
    result = pipeline.run(["AAA"], mode="update", end=pd.Timestamp("2024-01-05"))
    assert result["status"] == "incomplete"
    assert path.read_bytes() == old


def test_transient_provider_failure_is_retried_successfully(settings):
    class TransientProvider(FakeProvider):
        attempts = 0
        def fetch_prices(self, ticker, start, end):
            self.attempts += 1
            if self.attempts == 1:
                raise TimeoutError("Temporary network timeout")
            return super().fetch_prices(ticker, start, end)
    provider = TransientProvider({"AAA": prices()})
    result = Pipeline(settings, provider).run(["AAA"], end=END)
    assert result["status"] == "complete"
    assert provider.attempts == 2


def test_full_refresh_extends_2010_cache_to_1995_without_filling(settings):
    class LongHistoryProvider(FakeProvider):
        def fetch_prices(self, ticker, start, end):
            result = super().fetch_prices(ticker, start, end)
            result.first_trade_date = pd.Timestamp("1980-01-02")
            return result
    dates = ["2010-01-04", "2010-01-05", "2010-01-06"]
    provider = LongHistoryProvider({"AAA": prices(values=(100., 110., 121.), dates=dates)})
    original = replace(settings, start_date=pd.Timestamp("2010-01-01"))
    Pipeline(original, provider).run(["AAA"], end=pd.Timestamp("2010-01-06"))
    provider.responses["AAA"] = prices(values=(50., 100., 110., 121.), dates=["1995-01-03", *dates])
    expanded = replace(settings, start_date=pd.Timestamp("1995-01-01"))
    result = Pipeline(expanded, provider).run(["AAA"], full_refresh=True, end=pd.Timestamp("2010-01-06"))
    assert result["status"] == "complete"
    assert result["actual_start_date"] == "1995-01-03"
    wide = pd.read_parquet(expanded.path("processed_data_path") / "adjusted_close.parquet")
    assert pd.isna(wide.loc["1995-01-04", "AAA"])
    raw = pd.read_parquet(expanded.path("raw_data_path") / "AAA.parquet")
    assert len(raw) == 4
