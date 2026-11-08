"""Report suspect observations without interpolating, deleting, or repairing them."""

from typing import Any

import numpy as np
import pandas as pd

from .provider import RAW_COLUMNS


def validate_prices(frame: pd.DataFrame, ticker: str, sessions: pd.DatetimeIndex,
                    expected_currency: str, extreme_threshold: float,
                    first_trade_date: pd.Timestamp | None = None) -> dict[str, Any]:
    """Return structural errors and review warnings for a single normalized ticker."""
    issues: list[dict[str, Any]] = []

    def add(code: str, severity: str, count: int = 1, dates=None) -> None:
        item: dict[str, Any] = {"code": code, "severity": severity, "count": int(count)}
        if dates is not None:
            item["sample_dates"] = [str(pd.Timestamp(value).date()) for value in list(dates)[:5]]
        issues.append(item)

    report: dict[str, Any] = {"ticker": ticker, "row_count": len(frame), "issues": issues}
    missing = sorted(set(RAW_COLUMNS) - set(frame.columns))
    if missing:
        add("missing_columns", "error", len(missing))
        report["missing_columns"] = missing
    if frame.empty:
        add("empty_dataset", "error")
    if missing or frame.empty:
        report["valid"] = False
        return report
    if not pd.api.types.is_datetime64_any_dtype(frame.date) or frame.date.isna().any():
        add("invalid_dates", "error")
        report["valid"] = False
        return report
    if frame.date.dt.tz is not None or not frame.date.eq(frame.date.dt.normalize()).all():
        add("invalid_date_normalization", "error")
    duplicate = frame.duplicated(["ticker", "date"])
    if duplicate.any():
        add("duplicate_observations", "error", duplicate.sum(), frame.loc[duplicate, "date"])
    if not frame.date.is_monotonic_increasing:
        add("chronological_order", "error")
    if not frame.ticker.eq(ticker).all():
        add("ticker_mismatch", "error")
    outside = ~frame.date.isin(sessions)
    if outside.any():
        add("non_session_or_out_of_range_dates", "error", outside.sum(), frame.loc[outside, "date"])
    numeric = ["open", "high", "low", "close", "adjusted_close", "volume", "dividends", "stock_splits"]
    if any(not pd.api.types.is_numeric_dtype(frame[column]) for column in numeric):
        add("invalid_numeric_schema", "error")
        report["valid"] = False
        return report
    price_cols = ["open", "high", "low", "close", "adjusted_close"]
    nonpositive = frame[price_cols].le(0).any(axis=1)
    if nonpositive.any():
        add("non_positive_prices", "error", nonpositive.sum(), frame.loc[nonpositive, "date"])
    infinite = np.isinf(frame[numeric]).any(axis=1)
    if infinite.any():
        add("non_finite_prices", "error", infinite.sum(), frame.loc[infinite, "date"])
    missing_values = frame[price_cols + ["volume"]].isna().sum()
    report["missing_values"] = {key: int(value) for key, value in missing_values.items()}
    if missing_values.sum():
        add("missing_values", "warning", missing_values.sum())
    if frame.adjusted_close.notna().sum() == 0:
        add("unavailable_adjusted_close", "error")
    if frame.close.notna().sum() == 0:
        add("unavailable_close", "error")
    currency = frame.currency
    mismatch = currency.notna() & currency.ne("") & currency.ne(expected_currency)
    if mismatch.any():
        add("currency_mismatch", "error", mismatch.sum())
    if (currency.isna() | currency.eq("")).any():
        add("unverified_currency", "warning")
    if frame.provider.isna().any() or frame.fetched_at.isna().any():
        add("missing_provenance", "error")
    bad_volume = frame.volume.lt(0)
    if bad_volume.any():
        add("negative_volume", "error", bad_volume.sum())
    if frame.stock_splits.lt(0).any() or frame.dividends.lt(0).any():
        add("invalid_corporate_actions", "error")
    inconsistent = frame.high.lt(frame[["open", "close", "low"]].max(axis=1)) | frame.low.gt(frame[["open", "close", "high"]].min(axis=1))
    if inconsistent.any():
        add("inconsistent_ohlc", "error", inconsistent.sum(), frame.loc[inconsistent, "date"])
    adjustment = frame.adjusted_close.div(frame.close)
    if adjustment.gt(1.05).any():
        add("unusual_adjustment_ratio", "warning", adjustment.gt(1.05).sum())
    unique = frame.drop_duplicates("date").set_index("date").sort_index()
    aligned = unique.adjusted_close.reindex(sessions)
    daily = aligned.div(aligned.shift()).sub(1)
    invalid_returns = (daily.le(-1) | np.isinf(daily)) & daily.notna()
    if invalid_returns.any():
        add("invalid_returns", "error", invalid_returns.sum(), daily.index[invalid_returns])
    extreme = daily.abs().gt(extreme_threshold) & np.isfinite(daily)
    if extreme.any():
        add("extreme_returns", "warning", extreme.sum(), daily.index[extreme])
    start, end = frame.date.min(), frame.date.max()
    report.update(start_date=str(start.date()), end_date=str(end.date()))
    expected = sessions[(sessions >= start) & (sessions <= end)]
    gaps = expected.difference(frame.date)
    if len(gaps):
        add("missing_sessions", "warning", len(gaps), gaps)
    if len(sessions) and (end < sessions[-1] or pd.isna(aligned.iloc[-1])):
        add("incomplete_end", "error")
    if len(sessions) and start > sessions[0]:
        if first_trade_date is not None and first_trade_date >= sessions[0] and start <= first_trade_date + pd.Timedelta(days=7):
            add("post_start_listing", "warning")
        elif first_trade_date is not None and first_trade_date < sessions[0]:
            add("incomplete_start", "error")
        else:
            add("late_start_unverified", "warning")
    report["valid"] = not any(issue["severity"] == "error" for issue in issues)
    return report
