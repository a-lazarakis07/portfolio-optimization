"""Read deterministic, version-controlled ticker definitions."""

from pathlib import Path
import re

import pandas as pd


def validate_tickers(tickers: list[str]) -> list[str]:
    """Reject duplicates and unsafe symbols instead of silently changing identity."""
    if not tickers:
        raise ValueError("Stock universe is empty")
    if any(not isinstance(ticker, str) or not re.fullmatch(r"[A-Z][A-Z0-9-]{0,14}", ticker) for ticker in tickers):
        raise ValueError("Tickers must be explicit uppercase Yahoo symbols using letters, digits, or hyphens")
    if len(set(tickers)) != len(tickers):
        raise ValueError("Duplicate tickers in stock universe")
    return tickers


def load_universe(path: Path) -> list[str]:
    """Load the mandatory ticker column without implicit symbol substitutions."""
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    if "ticker" not in frame:
        raise ValueError("Universe CSV requires a ticker column")
    return validate_tickers(frame["ticker"].tolist())
