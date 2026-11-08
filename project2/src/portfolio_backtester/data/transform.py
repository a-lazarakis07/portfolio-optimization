"""Produce long prices, Adjusted Close matrices, and unfilled daily returns."""

import numpy as np
import pandas as pd

from .provider import PRICE_COLUMNS


def build_datasets(raw: pd.DataFrame, tickers: list[str], sessions: pd.DatetimeIndex) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Align to exchange sessions and preserve every unavailable observation as NaN."""
    if raw.duplicated(["ticker", "date"]).any():
        raise ValueError("Duplicate ticker-date observations must be resolved before transformation")
    long = raw.loc[raw.ticker.isin(tickers) & raw.date.isin(sessions), PRICE_COLUMNS].sort_values(["date", "ticker"]).reset_index(drop=True)
    wide = long.pivot(index="date", columns="ticker", values="adjusted_close")
    wide = wide.reindex(index=sessions, columns=tickers).astype("float64")
    wide.index.name = "date"
    wide.columns.name = "ticker"
    usable = wide.where((wide > 0) & np.isfinite(wide))
    returns = usable.div(usable.shift(1)).sub(1).replace([np.inf, -np.inf], np.nan)
    return long, wide, returns
