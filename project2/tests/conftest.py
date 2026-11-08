from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from portfolio_backtester.config import load_settings
from portfolio_backtester.data.provider import PriceResult

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def settings(tmp_path):
    config = load_settings(ROOT / "config/settings.yaml", root=ROOT)
    return replace(config, root=tmp_path, start_date=pd.Timestamp("2024-01-02"),
                   retry_attempts=2, pacing_seconds=0, batch_pause_seconds=0,
                   backoff_seconds=0)


def prices(ticker="AAA", values=(100.0, 110.0, 121.0), dates=None, currency="USD"):
    dates = pd.to_datetime(dates if dates is not None else ["2024-01-02", "2024-01-03", "2024-01-04"])
    n = len(dates)
    return pd.DataFrame({
        "date": dates, "ticker": [ticker] * n,
        "open": values, "high": [v * 1.01 for v in values],
        "low": [v * 0.99 for v in values], "close": values,
        "adjusted_close": values, "volume": [1000.0] * n,
        "dividends": [0.0] * n, "stock_splits": [0.0] * n,
        "provider": ["yahoo"] * n, "currency": [currency] * n,
        "fetched_at": ["2024-01-05T00:00:00+00:00"] * n,
    })


class FakeProvider:
    name = "yahoo"

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def fetch_prices(self, ticker, start, end):
        self.calls.append((ticker, start, end))
        response = self.responses[ticker]
        if isinstance(response, Exception):
            raise response
        frame = response.loc[response.date.between(start, end)].copy()
        return PriceResult(frame, currency="USD", first_trade_date=pd.Timestamp("2000-01-03"))

    def fetch_metadata(self, ticker):
        raise RuntimeError("Company metadata unavailable")
