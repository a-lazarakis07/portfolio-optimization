"""Align same-date stock returns, RF, and six factors without filling observations."""

import numpy as np
import pandas as pd

from portfolio_backtester.config import Settings
from portfolio_backtester.data.calendar import latest_completed_session, trading_sessions
from portfolio_backtester.data.universe import validate_tickers
from . import ALL_COLUMNS, FACTOR_COLUMNS

PANEL_COLUMNS = ["date", "ticker", "stock_return", "rf", "excess_return", *FACTOR_COLUMNS]


def _check_dates(frame: pd.DataFrame, name: str) -> None:
    if frame.empty:
        raise ValueError(f"{name} is empty")
    dates = frame.index
    if not isinstance(dates, pd.DatetimeIndex) or dates.hasnans or dates.tz is not None:
        raise ValueError(f"{name} requires timezone-naive daily DatetimeIndex labels")
    if dates.has_duplicates or not dates.is_monotonic_increasing or not dates.equals(dates.normalize()):
        raise ValueError(f"{name} has duplicate, unordered, or non-daily dates")


def build_regression_panel(stock_returns: pd.DataFrame, factors: pd.DataFrame, tickers: list[str],
                           settings: Settings, *, as_of_date: pd.Timestamp | None = None) -> tuple[pd.DataFrame, dict, pd.DatetimeIndex]:
    """Create the standardized research panel and a shared bounded candidate window."""
    validate_tickers(tickers)
    _check_dates(stock_returns, "Stock Daily Returns")
    _check_dates(factors, "Factor Data")
    if stock_returns.columns.has_duplicates:
        raise ValueError("Duplicate stock columns in Daily Returns")
    if list(factors.columns) != ALL_COLUMNS:
        raise ValueError(f"Factor Data schema must be {ALL_COLUMNS}")
    cutoff = latest_completed_session(delay_minutes=settings.completion_delay_minutes)
    requested = pd.Timestamp(as_of_date) if as_of_date is not None else None
    if requested is not None:
        if pd.isna(requested) or requested.tz is not None or requested != requested.normalize():
            raise ValueError("as_of_date must be a valid timezone-naive date")
        cutoff = min(cutoff, requested)
    # Validate values only inside the requested information horizon.
    stocks = stock_returns.loc[stock_returns.index <= cutoff].reindex(columns=tickers).copy()
    factor_sample = factors.loc[factors.index <= cutoff].copy()
    if stocks.empty or factor_sample.empty:
        raise ValueError("No data available at or before the requested as_of_date")
    if any(not pd.api.types.is_numeric_dtype(stocks[column]) for column in stocks):
        raise ValueError("Stock Daily Returns must be numeric decimals")
    if any(not pd.api.types.is_numeric_dtype(factor_sample[column]) for column in factor_sample):
        raise ValueError("Factor Data must be numeric decimals")
    if np.isinf(stocks.to_numpy()).any() or stocks.le(-1).any().any():
        raise ValueError("Stock Daily Returns contain non-finite or impossible observations")
    if np.isinf(factor_sample.to_numpy()).any():
        raise ValueError("Factor Data contains non-finite observations")
    expected = trading_sessions(stocks.index.min(), stocks.index.max())
    if len(stocks.index.difference(expected)):
        raise ValueError("Stock Daily Returns contain non-trading dates")
    common = stocks.index.intersection(factor_sample.index).sort_values()
    if common.empty:
        raise ValueError("Stock Daily Returns and Factor Data have no common dates")
    valid_factors = factor_sample.loc[common, ALL_COLUMNS].notna().all(axis=1)
    available = common[valid_factors]
    if available.empty:
        raise ValueError("No complete factor dates overlap stock date labels")
    effective = available[-1]
    common = common[common <= effective].rename("date")
    candidates = common[-settings.regression_window:]
    stocks = stocks.reindex(index=common, columns=tickers)
    stocks.columns.name = "ticker"
    long = stocks.stack(future_stack=True).rename("stock_return").reset_index()
    factor_sample.index.name = "date"
    panel = long.merge(factor_sample.reset_index(), on="date", how="left", validate="many_to_one")
    panel["excess_return"] = panel.stock_return - panel.rf
    panel = panel[PANEL_COLUMNS].sort_values(["date", "ticker"]).reset_index(drop=True)
    original_stock_dates = stock_returns.index[stock_returns.index <= cutoff]
    complete_factor_dates = factor_sample.index[factor_sample[ALL_COLUMNS].notna().all(axis=1)]
    missing_factor_dates = original_stock_dates.difference(complete_factor_dates)
    complete_history = factors.dropna(subset=ALL_COLUMNS)
    report = {"requested_as_of_date": str(requested.date()) if requested is not None else None,
              "as_of_date": str(effective.date()), "no_future_cutoff": str(cutoff.date()),
              "stock_start_date": str(stock_returns.index.min().date()), "stock_end_date": str(stock_returns.index.max().date()),
              "factor_complete_start_date": str(complete_history.index.min().date()),
              "factor_complete_end_date": str(complete_history.index.max().date()),
              "stock_dates_without_complete_factors": [str(date.date()) for date in missing_factor_dates],
              "future_stock_dates_excluded": int((stock_returns.index > cutoff).sum()),
              "future_factor_dates_excluded": int((factors.index > cutoff).sum()),
              "missing_stock_columns": sorted(set(tickers) - set(stock_returns.columns)),
              "panel_rows": len(panel), "panel_start_date": str(common[0].date()), "panel_end_date": str(effective.date()),
              "candidate_window_start": str(candidates[0].date()), "candidate_window_end": str(candidates[-1].date()),
              "candidate_window_dates": len(candidates), "configured_window": settings.regression_window,
              "missing_stock_observations_in_window": {ticker: int(stocks.loc[candidates, ticker].isna().sum()) for ticker in tickers},
              "missing_factor_observations_in_window": int(factor_sample.loc[candidates, ALL_COLUMNS].isna().any(axis=1).sum()),
              "missing_data_policy": "Exact same-date inner join; retain missing cells; per-stock complete cases within the shared bounded window; no filling or back-extension."}
    return panel, report, candidates
