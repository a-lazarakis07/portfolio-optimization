import pandas as pd
import pytest

from portfolio_backtester.data.yahoo_provider import YahooProvider


def test_yahoo_preserves_raw_and_adjusted_fields_with_explicit_settings(settings, monkeypatch):
    calls = []
    class Client:
        history_metadata = {"currency": "USD", "exchangeName": "NMS", "firstTradeDate": 946857600}
        def history(self, **kwargs):
            calls.append(kwargs)
            return pd.DataFrame({"Open": [100.0], "High": [101.0], "Low": [99.0], "Close": [100.0],
                                 "Adj Close": [95.0], "Volume": [1234], "Dividends": [1.0], "Stock Splits": [0.0]},
                                index=pd.DatetimeIndex(["2024-01-02"], tz="America/New_York", name="Date"))
    monkeypatch.setattr("portfolio_backtester.data.yahoo_provider.yf.Ticker", lambda *args, **kwargs: Client())
    provider = YahooProvider(settings)
    result = provider.fetch_prices("AAA", pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-02"))
    assert result.frame.close.iloc[0] == 100
    assert result.frame.adjusted_close.iloc[0] == 95
    assert result.frame.date.iloc[0] == pd.Timestamp("2024-01-02")
    assert result.currency == "USD"
    assert calls[0]["auto_adjust"] is False
    assert calls[0]["back_adjust"] is False
    assert calls[0]["repair"] is False
    assert calls[0]["end"] == "2024-01-03"


def test_yahoo_missing_adjusted_close_is_not_replaced_by_close(settings, monkeypatch):
    class Client:
        history_metadata = {"currency": "USD"}
        def history(self, **kwargs):
            return pd.DataFrame({"Open": [100.0], "High": [101.0], "Low": [99.0], "Close": [100.0], "Volume": [1000]},
                                index=pd.DatetimeIndex(["2024-01-02"], name="Date"))
    monkeypatch.setattr("portfolio_backtester.data.yahoo_provider.yf.Ticker", lambda *args, **kwargs: Client())
    result = YahooProvider(settings).fetch_prices("AAA", pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-02"))
    assert result.frame.adjusted_close.isna().all()


@pytest.mark.integration
def test_live_smoke_is_opt_in(settings):
    import os
    if os.environ.get("SGC_RUN_INTEGRATION") != "1":
        pytest.skip("Set SGC_RUN_INTEGRATION=1 to make real Yahoo Finance requests")
    result = YahooProvider(settings).fetch_prices("AAPL", pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-05"))
    assert not result.frame.empty
    assert result.currency == "USD"
