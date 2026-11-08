"""Provider contract; future WRDS/CRSP adapters can implement this protocol."""

from dataclasses import dataclass
from typing import Any, Protocol

import pandas as pd

PRICE_COLUMNS = ["date", "ticker", "open", "high", "low", "close", "adjusted_close", "volume"]
RAW_COLUMNS = PRICE_COLUMNS + ["dividends", "stock_splits", "provider", "currency", "fetched_at"]
NUMERIC_COLUMNS = ["open", "high", "low", "close", "adjusted_close", "volume", "dividends", "stock_splits"]
METADATA_COLUMNS = ["ticker", "company_name", "sector", "industry", "exchange", "currency", "market_cap", "metadata_fetched_at"]


@dataclass
class PriceResult:
    frame: pd.DataFrame
    currency: str | None = None
    exchange: str | None = None
    first_trade_date: pd.Timestamp | None = None


class DataProvider(Protocol):
    name: str

    def fetch_prices(self, ticker: str, start: pd.Timestamp, end: pd.Timestamp) -> PriceResult:
        """Fetch daily data over inclusive session dates; never substitute a security."""
        ...

    def fetch_metadata(self, ticker: str) -> dict[str, Any]:
        """Fetch current company metadata independently of price retrieval."""
        ...


def empty_prices() -> pd.DataFrame:
    """Return the normalized empty raw schema."""
    frame = pd.DataFrame({column: pd.Series(dtype="float64" if column in NUMERIC_COLUMNS else "object")
                          for column in RAW_COLUMNS})
    frame["date"] = pd.Series(dtype="datetime64[ns]")
    return frame
