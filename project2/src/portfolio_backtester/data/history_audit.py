"""Audit historical availability without certifying point-in-time investability."""

import numpy as np
import pandas as pd

from .calendar import trading_sessions
from portfolio_backtester.factors import ALL_COLUMNS


def audit_universe_history(raw: pd.DataFrame, returns: pd.DataFrame, universe: pd.DataFrame,
                           factors: pd.DataFrame, policy: dict, *, window: int = 756,
                           minimum: int = 504, profiles: dict | None = None,
                           invalid_tickers: set[str] | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Return stock coverage, every-date research flags, event reviews, and crisis sets."""
    profiles = profiles or {}
    invalid_tickers = invalid_tickers or set()
    sessions = pd.DatetimeIndex(returns.index, name="date")
    if sessions.empty or sessions.has_duplicates or not sessions.is_monotonic_increasing:
        raise ValueError("Historical audit requires a nonempty ordered unique session index")
    if universe.ticker.duplicated().any() or raw.duplicated(["ticker", "date"]).any():
        raise ValueError("Historical audit does not accept duplicate securities or observations")
    if set(ALL_COLUMNS) - set(factors.columns):
        raise ValueError("Historical estimation audit requires all six factors and RF")
    complete_factors = pd.Series(np.isfinite(factors[ALL_COLUMNS].to_numpy()).all(axis=1), index=factors.index).reindex(sessions, fill_value=False)
    coverage_rows, daily_frames, events = [], [], []
    summary = {"universe_version": policy["universe_version"], "configured_tickers": universe.ticker.tolist(),
               "requested_first_session": str(sessions[0].date()), "last_session": str(sessions[-1].date()),
               "pre_crisis_candidate_window": window, "minimum_observations": minimum, "crises": {}}
    crisis_windows = {}
    for key, event in policy["crises"].items():
        start, end = pd.Timestamp(event["start"]), pd.Timestamp(event["end"])
        crisis_windows[key] = (trading_sessions(start, end), trading_sessions(
            start - pd.DateOffset(years=window // 200 + 2), start - pd.Timedelta(days=1))[-window:])
        summary["crises"][key] = {**event, "available_tickers": [], "full_coverage_tickers": [],
                                   "pre_crisis_estimation_eligible_tickers": [], "identity_clear_pre_crisis_eligible_tickers": []}
    for security in universe.itertuples(index=False):
        ticker = security.ticker
        observed = raw.loc[raw.ticker.eq(ticker)].set_index("date").sort_index().reindex(sessions)
        adjusted = observed.get("adjusted_close", pd.Series(np.nan, index=sessions))
        close = observed.get("close", pd.Series(np.nan, index=sessions))
        prices_valid = adjusted.gt(0) & close.gt(0) & np.isfinite(adjusted) & np.isfinite(close)
        series = returns[ticker].reindex(sessions) if ticker in returns else pd.Series(np.nan, index=sessions)
        returns_valid = np.isfinite(series) & series.gt(-1) & prices_valid
        first = sessions[prices_valid][0] if prices_valid.any() else None
        last = sessions[prices_valid][-1] if prices_valid.any() else None
        profile = profiles.get(ticker, {})
        mapping = pd.Series(False, index=sessions)
        if profile.get("identity_valid_from"):
            mapping = pd.Series(sessions < pd.Timestamp(profile["identity_valid_from"]), index=sessions) & prices_valid
        action_window = pd.Series(False, index=sessions)
        radius = pd.Timedelta(days=policy["corporate_action_review_days"])
        known_events = {pd.Timestamp(event["date"]): event for event in profile.get("events", [])}
        action_mismatches = 0
        for date, event in known_events.items():
            action_window |= (sessions >= date - radius) & (sessions <= date + radius)
            if sessions[0] <= date <= sessions[-1]:
                events.append({"ticker": ticker, "date": date, "event_type": event["type"],
                               "description": event["description"], "source_url": event.get("source_url", ""),
                               "observed_return": float(series.loc[date]) if date in series.index else np.nan,
                               "review_required": True})
                if event.get("expected_stock_split") is not None and date in observed.index:
                    actual = observed.loc[date, "stock_splits"]
                    expected = float(event["expected_stock_split"])
                    if pd.isna(actual) or not np.isclose(actual, expected, rtol=1e-5):
                        action_mismatches += 1
                        events.append({"ticker": ticker, "date": date, "event_type": "provider_corporate_action_mismatch",
                            "description": f"Official legal share ratio {expected}; Yahoo Stock Splits field {actual}. Combined distribution factors must not be treated as verified share conversion ratios.",
                            "source_url": event.get("source_url", ""), "observed_return": float(series.loc[date]), "review_required": True})
        adjustment = adjusted.div(close)
        jumps = adjustment.div(adjustment.shift()).sub(1).abs().gt(policy["adjustment_ratio_jump_threshold"])
        extreme = series.abs().gt(.5) & returns_valid
        split = observed.get("stock_splits", pd.Series(0., index=sessions)).fillna(0).ne(0)
        for code, mask in [("extreme_return", extreme), ("adjustment_ratio_jump", jumps), ("stock_split", split)]:
            for date in sessions[mask]:
                events.append({"ticker": ticker, "date": date, "event_type": code,
                               "description": "Provider observation retained without automatic economic correction",
                               "source_url": "Yahoo Finance normalized provider snapshot",
                               "observed_return": float(series.loc[date]) if returns_valid.loc[date] else np.nan,
                               "review_required": code != "stock_split" or bool(action_window.loc[date])})
        review = action_window | jumps | extreme
        status = np.select([~prices_valid, mapping, review],
                           ["unavailable", "mapped_history_requires_identity_review", "corporate_action_or_return_review"],
                           default="research_data_available_pit_unverified")
        daily = pd.DataFrame({"date": sessions, "ticker": ticker, "universe_version": policy["universe_version"],
            "price_available": prices_valid.to_numpy(), "return_available": returns_valid.to_numpy(),
            "predecessor_or_share_class_mapping": mapping.to_numpy(), "corporate_action_review_window": action_window.to_numpy(),
            "adjustment_ratio_jump_flag": jumps.to_numpy(), "extreme_return_flag": extreme.to_numpy(),
            "stock_split_event": split.to_numpy(), "research_return_available_identity_clear": (returns_valid & ~mapping & ~review).to_numpy(),
            "point_in_time_investability_verified": False, "investability_status": status})
        warnings = []
        if profile.get("warning"):
            warnings.append(profile["warning"])
        if first is not None and first > sessions[0]:
            warnings.append(f"Provider series begins {first.date()}; earlier observations remain unavailable")
        interior_missing = int((~prices_valid.loc[first:last]).sum()) if first is not None else 0
        if interior_missing:
            warnings.append(f"{interior_missing} missing price sessions inside the observed lifespan")
        if extreme.any() or jumps.any():
            warnings.append(f"{int(extreme.sum())} extreme returns and {int(jumps.sum())} adjustment ratio jumps require review")
        recent_count = int(returns_valid.iloc[-window:].sum())
        classification = "Eligible"
        if not prices_valid.any() or ticker in invalid_tickers or recent_count < minimum:
            classification = "Ineligible"
        elif mapping.any() or review.any() or warnings:
            classification = "Limited"
        row = {"ticker": ticker, "company_name": security.company_name, "sector": security.sector,
               "first_available_date": first, "last_available_date": last,
               "total_valid_observations": int(prices_valid.sum()), "valid_daily_return_observations": int(returns_valid.sum()),
               "data_coverage_percentage": float(prices_valid.mean() * 100),
               "lifespan_coverage_percentage": float(prices_valid.loc[first:last].mean() * 100) if first is not None else 0.,
               "recent_756_valid_observations": recent_count, "stock_split_observations": int(split.sum()),
               "extreme_return_observations": int(extreme.sum()), "adjustment_ratio_jump_observations": int(jumps.sum()),
               "corporate_action_field_mismatches": action_mismatches,
               "corporate_action_ticker_history_warnings": " | ".join(warnings), "status": classification}
        for key, event in policy["crises"].items():
            start, end = pd.Timestamp(event["start"]), pd.Timestamp(event["end"])
            crisis_dates, candidates = crisis_windows[key]
            before = returns_valid.reindex(candidates, fill_value=False)
            factor_before = complete_factors.reindex(candidates, fill_value=False)
            mapping_before = mapping.reindex(candidates, fill_value=False)
            review_before = review.reindex(candidates, fill_value=False)
            valid_count = int((before & factor_before).sum())
            event_returns = returns_valid.reindex(crisis_dates, fill_value=False)
            available = bool(event_returns.any()) if len(crisis_dates) else False
            fraction = float(event_returns.mean()) if len(crisis_dates) else 0.
            full = bool(len(crisis_dates) and fraction >= policy["minimum_crisis_coverage"])
            eligible = ticker not in invalid_tickers and valid_count >= minimum
            clear_count = int((before & factor_before & ~mapping_before & ~review_before).sum())
            row.update({f"{key}_crisis_available": available, f"{key}_full_crisis_coverage": full,
                        f"{key}_crisis_return_coverage_percentage": fraction * 100,
                        f"{key}_pre_crisis_candidate_sessions": len(candidates),
                        f"{key}_pre_crisis_valid_observations": valid_count,
                        f"{key}_pre_crisis_estimation_eligible": eligible,
                        f"{key}_identity_clear_pre_crisis_valid_observations": clear_count,
                        f"{key}_pre_crisis_identity_review_required": bool(mapping_before.any())})
            if available: summary["crises"][key]["available_tickers"].append(ticker)
            if full: summary["crises"][key]["full_coverage_tickers"].append(ticker)
            if eligible: summary["crises"][key]["pre_crisis_estimation_eligible_tickers"].append(ticker)
            if ticker not in invalid_tickers and clear_count >= minimum: summary["crises"][key]["identity_clear_pre_crisis_eligible_tickers"].append(ticker)
        coverage_rows.append(row)
        daily_frames.append(daily)
    coverage = pd.DataFrame(coverage_rows)
    flags = pd.concat(daily_frames, ignore_index=True).sort_values(["date", "ticker"]).reset_index(drop=True)
    events_frame = pd.DataFrame(events, columns=["ticker", "date", "event_type", "description", "source_url", "observed_return", "review_required"])
    if not events_frame.empty:
        events_frame = events_frame.sort_values(["date", "ticker", "event_type"]).reset_index(drop=True)
    summary["status_counts"] = {key: int(value) for key, value in coverage.status.value_counts().items()}
    summary["point_in_time_investability_policy"] = "No date is certified PIT-investable from current provider prices alone; explicit availability and identity flags are separate from historical constituent membership."
    return coverage, flags, events_frame, summary
