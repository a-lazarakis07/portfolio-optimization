"""Atomic local file writes and deterministic incremental merging."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile
from collections.abc import Iterator

import pandas as pd


@contextmanager
def atomic_target(path: Path) -> Iterator[Path]:
    """Replace a single destination only after a successful same-directory write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        yield temporary
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_parquet(frame: pd.DataFrame, path: Path, *, index: bool = False) -> None:
    """Write Parquet without exposing partially written files."""
    with atomic_target(path) as temporary:
        frame.to_parquet(temporary, engine="pyarrow", index=index)


def atomic_json(value: dict, path: Path) -> None:
    """Write strict JSON; unavailable values must be null rather than NaN."""
    with atomic_target(path) as temporary:
        temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


@contextmanager
def pipeline_lock(path: Path) -> Iterator[None]:
    """Prevent simultaneous writers; an interrupted process may leave a stale lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise RuntimeError(f"Pipeline already running or stale lock exists: {path}. Verify no writer is active before removing it.") from error
    try:
        with os.fdopen(descriptor, "w") as handle:
            handle.write(str(os.getpid()))
        yield
    finally:
        path.unlink(missing_ok=True)


def merge_prices(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """Prefer the latest fetched row for each overlap date, preserving old history."""
    frames = [frame for frame in (old, new) if not frame.empty]
    if not frames:
        return old.copy()
    merged = pd.concat(frames, ignore_index=True)
    return (merged.drop_duplicates(["ticker", "date"], keep="last")
            .sort_values(["date", "ticker"]).reset_index(drop=True))
