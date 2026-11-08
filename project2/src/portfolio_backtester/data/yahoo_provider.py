"""Yahoo Finance adapter with explicit price-adjustment conventions."""

from typing import Any

import pandas as pd
from curl_cffi import requests
import yfinance as yf

from portfolio_backtester.config import Settings
from .provider import METADATA_COLUMNS, NUMERIC_COLUMNS, RAW_COLUMNS, PriceResult, empty_prices


class BoundedSession(requests.Session):
    """Cap all provider HTTP requests, including independent metadata requests."""

    def __init__(self, timeout: float):
        super().__init__(impersonate="chrome", timeout=timeout)
        self.request_timeout = timeout

    def request(self, *args: Any, **kwargs: Any) -> Any:
        timeout = kwargs.get("timeout")
        if isinstance(timeout, (int, float)):
            kwargs["timeout"] = min(timeout, self.request_timeout)
        else:
            kwargs["timeout"] = self.request_timeout
        return super().request(*args, **kwargs)


class YahooProvider:
    """Fetch prices without requiring slow company-profile endpoints."""

    name = "yahoo"

    def __init__(self, settings: Settings):
        self.settings = settings
        cache = settings.path("cache_path")
        cache.mkdir(parents=True, exist_ok=True)
        yf.set_tz_cache_location(str(cache))
        self.session = BoundedSession(settings.timeout_seconds)

    def fetch_prices(self, ticker: str, start: pd.Timestamp, end: pd.Timestamp) -> PriceResult:
        """Translate inclusive dates to Yahoo's exclusive end-date API."""
        client = yf.Ticker(ticker, session=self.session)
        frame = client.history(start=start.strftime("%Y-%m-%d"),
                               end=(end + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                               interval="1d", auto_adjust=False, back_adjust=False,
                               actions=True, repair=False, keepna=True, rounding=False,
                               prepost=False, timeout=self.settings.timeout_seconds,
                               raise_errors=True)
        if frame is None or frame.empty:
            return PriceResult(empty_prices())
        metadata = client.history_metadata or {}
        renamed = frame.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close",
                                        "Adj Close": "adjusted_close", "Volume": "volume",
                                        "Dividends": "dividends", "Stock Splits": "stock_splits"}).copy()
        dates = pd.DatetimeIndex(renamed.index)
        if dates.tz is not None:
            dates = dates.tz_convert("America/New_York").tz_localize(None)
        renamed = renamed.reset_index(drop=True)
        renamed["date"] = dates.normalize().to_numpy(dtype="datetime64[ns]")
        renamed["ticker"] = ticker
        for column in NUMERIC_COLUMNS:
            if column not in renamed:
                renamed[column] = float("nan")
            renamed[column] = pd.to_numeric(renamed[column], errors="coerce").astype("float64")
        renamed["provider"] = self.name
        renamed["currency"] = metadata.get("currency")
        renamed["fetched_at"] = pd.Timestamp.now(tz="UTC").isoformat()
        first_trade = metadata.get("firstTradeDate")
        first_date = (pd.Timestamp(first_trade, unit="s", tz="UTC").tz_convert("America/New_York")
                      .tz_localize(None).normalize()) if first_trade else None
        return PriceResult(renamed[RAW_COLUMNS], currency=metadata.get("currency"),
                           exchange=metadata.get("exchangeName"), first_trade_date=first_date)

    def fetch_metadata(self, ticker: str) -> dict[str, Any]:
        """Fetch a current profile; failures do not affect saved price observations."""
        info = yf.Ticker(ticker, session=self.session).get_info()
        if not info or not (info.get("longName") or info.get("shortName")):
            raise ValueError(f"Empty company metadata for {ticker}")
        row = {"ticker": ticker, "company_name": info.get("longName") or info.get("shortName"),
               "sector": info.get("sector"), "industry": info.get("industry"),
               "exchange": info.get("exchange"), "currency": info.get("currency"),
               "market_cap": info.get("marketCap"), "metadata_fetched_at": pd.Timestamp.now(tz="UTC").isoformat()}
        return {key: row[key] for key in METADATA_COLUMNS}
