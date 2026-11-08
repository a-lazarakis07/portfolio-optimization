"""NYSE session dates and completion times, including holidays and early closes."""

import exchange_calendars as xcals
import pandas as pd


def trading_sessions(start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex:
    """Return inclusive, timezone-naive US equity session labels."""
    if start > end:
        return pd.DatetimeIndex([], name="date")
    calendar = xcals.get_calendar("XNYS", start=start - pd.Timedelta(days=10),
                                  end=end + pd.Timedelta(days=10))
    sessions = calendar.sessions_in_range(start, end)
    return pd.DatetimeIndex(sessions).tz_localize(None).rename("date")


def latest_completed_session(now: pd.Timestamp | None = None, *, delay_minutes: int = 30) -> pd.Timestamp:
    """Find the last session whose official close plus publication delay passed."""
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    now = now.tz_localize("UTC") if now.tz is None else now.tz_convert("UTC")
    today = now.tz_convert("America/New_York").tz_localize(None).normalize()
    calendar = xcals.get_calendar("XNYS", start=today - pd.Timedelta(days=30),
                                  end=today + pd.Timedelta(days=2))
    schedule = calendar.schedule
    completed = schedule.loc[schedule["close"] <= now - pd.Timedelta(minutes=delay_minutes)]
    if completed.empty:
        raise ValueError("No completed exchange session available")
    return pd.Timestamp(completed.index[-1]).tz_localize(None).normalize()
