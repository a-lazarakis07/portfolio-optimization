"""Parse and validate official daily Kenneth French data without filling gaps."""

import csv
import io
import re
import zipfile

import numpy as np
import pandas as pd

from portfolio_backtester.data.calendar import trading_sessions
from . import ALL_COLUMNS

SOURCE_COLUMNS = {"ff5": ["mkt_rf", "smb", "hml", "rmw", "cma", "rf"], "momentum": ["mom"]}


def extract_csv(body: bytes) -> tuple[bytes, str]:
    """Read one CSV member without extracting paths onto the filesystem."""
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        files = [item for item in archive.infolist() if item.filename.lower().endswith(".csv") and not item.is_dir()]
        if len(files) != 1 or files[0].file_size > 32_000_000:
            raise ValueError("Official ZIP must contain one reasonably sized CSV file")
        return archive.read(files[0]), files[0].filename


def parse_daily_csv(body: bytes, dataset: str) -> tuple[pd.DataFrame, str]:
    """Extract the daily table and convert source percentage returns to decimals."""
    if dataset not in SOURCE_COLUMNS:
        raise ValueError(f"Unknown official factor dataset: {dataset}")
    text = body.decode("utf-8-sig")
    expected = SOURCE_COLUMNS[dataset]
    notes = []
    rows = []
    found_header = False
    for row in csv.reader(io.StringIO(text)):
        if not found_header:
            names = [cell.strip().lower().replace("-", "_") for cell in row[1:]]
            if names == expected:
                found_header = True
            else:
                notes.append(",".join(row))
            continue
        date = row[0].strip() if row else ""
        if not re.fullmatch(r"\d{8}", date):
            if rows:
                if not date or re.match(r"(?i)(annual|monthly|copyright)", date) or re.fullmatch(r"\d{4}|\d{6}", date):
                    break
                raise ValueError(f"Malformed or unexpected daily factor date: {date}")
            continue
        if len(row) != len(expected) + 1:
            raise ValueError(f"Unexpected daily factor field count at {date}")
        try:
            timestamp = pd.to_datetime(date, format="%Y%m%d", errors="raise")
            values = [float(cell.strip()) if cell.strip() else np.nan for cell in row[1:]]
        except ValueError as error:
            raise ValueError(f"Malformed daily factor observation at {date}") from error
        rows.append([timestamp, *[np.nan if value in {-99.99, -999.0} else value / 100 for value in values]])
    if not found_header or not rows:
        raise ValueError("Official daily factor table is missing or empty")
    frame = pd.DataFrame(rows, columns=["date", *expected]).set_index("date").astype("float64")
    if frame.index.has_duplicates:
        raise ValueError("Duplicate dates in official daily factor table")
    if not frame.index.is_monotonic_increasing:
        raise ValueError("Official factor dates are not chronologically ordered")
    return frame, "\n".join(notes).strip()


def validate_factor_data(frame: pd.DataFrame) -> dict:
    """Check source observations; pre-1963 calendar differences are retained for review."""
    report = {"valid": True, "rows": len(frame), "errors": [], "warnings": []}
    errors = report["errors"]
    if frame.empty:
        errors.append("Factor dataset is empty")
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.hasnans:
        errors.append("Factor index must contain valid daily dates")
        report["valid"] = False
        return report
    if frame.index.tz is not None or not frame.index.equals(frame.index.normalize()):
        errors.append("Factor dates must be timezone-naive daily session labels")
    if frame.index.has_duplicates:
        errors.append("Duplicate factor dates")
    if not frame.index.is_monotonic_increasing:
        errors.append("Factor dates are not chronological")
    if any(not pd.api.types.is_numeric_dtype(frame[column]) for column in frame):
        errors.append("Factor values must be numeric decimal returns")
        report["valid"] = False
        return report
    report["missing_values"] = {column: int(frame[column].isna().sum()) for column in frame}
    if frame.isna().any().any():
        errors.append("Missing source factor observations")
    if np.isinf(frame.to_numpy()).any():
        errors.append("Non-finite factor observations")
    extreme = frame.abs().gt(0.5)
    report["extreme_observations"] = int(extreme.sum().sum())
    if report["extreme_observations"]:
        report["warnings"].append("Absolute daily factor returns above 50% require review; retained unchanged")
    if not frame.empty:
        # XNYS uses a modern five-day weekmask; early CRSP daily history can include Saturdays.
        checked = frame.index[frame.index >= pd.Timestamp("1963-07-01")]
        if len(checked):
            expected = trading_sessions(checked.min(), checked.max())
            unexpected = checked.difference(expected)
            if len(unexpected):
                errors.append("Non-trading dates in factor history from July 1963 onward")
            report["non_trading_dates"] = [str(day.date()) for day in unexpected]
            missing = expected.difference(checked)
            report["missing_sessions"] = [str(day.date()) for day in missing]
            if len(missing):
                report["warnings"].append("Exchange sessions without factor rows are retained as gaps")
        report["legacy_calendar_dates_not_verified"] = int((frame.index < pd.Timestamp("1963-07-01")).sum())
        report["start_date"] = str(frame.index.min().date())
        report["end_date"] = str(frame.index.max().date())
    report["valid"] = not errors
    return report


def combine_factors(ff5: pd.DataFrame, momentum: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Outer-join exact source dates, recording unequal coverage without imputing."""
    if ff5.index.has_duplicates or momentum.index.has_duplicates:
        raise ValueError("Cannot merge factors with duplicate dates")
    combined = ff5.join(momentum, how="outer").reindex(columns=ALL_COLUMNS).sort_index()
    combined.index.name = "date"
    complete = combined.dropna()
    if complete.empty:
        raise ValueError("Official factor datasets have no common complete daily observations")
    report = {"rows": len(combined), "complete_dates": len(complete),
              "complete_start_date": str(complete.index.min().date()), "complete_end_date": str(complete.index.max().date()),
              "ff5_only_dates": [str(date.date()) for date in ff5.index.difference(momentum.index)],
              "momentum_only_dates": [str(date.date()) for date in momentum.index.difference(ff5.index)],
              "missing_values": {column: int(combined[column].isna().sum()) for column in ALL_COLUMNS}}
    return combined, report


def revision_summary(old: pd.DataFrame | None, new: pd.DataFrame) -> dict:
    """Compare the entire overlapping release, including historical revisions."""
    if old is None:
        return {"previous_snapshot": False, "revised_dates": [], "added_dates": [str(d.date()) for d in new.index], "removed_dates": []}
    common = old.index.intersection(new.index)
    columns = old.columns.intersection(new.columns)
    changed = ~np.isclose(old.loc[common, columns], new.loc[common, columns], rtol=0, atol=1e-14, equal_nan=True)
    revised = common[changed.any(axis=1)]
    return {"previous_snapshot": True, "revised_dates": [str(d.date()) for d in revised],
            "added_dates": [str(d.date()) for d in new.index.difference(old.index)],
            "removed_dates": [str(d.date()) for d in old.index.difference(new.index)]}
