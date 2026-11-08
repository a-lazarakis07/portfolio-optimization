import numpy as np
import pandas as pd
import pytest

from conftest import prices
from portfolio_backtester.data.storage import atomic_parquet, merge_prices
from portfolio_backtester.data.transform import build_datasets
from portfolio_backtester.data.validation import validate_prices

SESSIONS = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])


def test_returns_use_adjusted_close_without_double_counting_actions():
    raw = prices()
    raw["close"] = [200.0, 210.0, 220.0]
    raw["dividends"] = [0.0, 2.0, 0.0]
    raw["stock_splits"] = [0.0, 2.0, 0.0]
    long, wide, returns = build_datasets(raw, ["AAA"], SESSIONS)
    assert list(long.columns) == ["date", "ticker", "open", "high", "low", "close", "adjusted_close", "volume"]
    assert returns.AAA.iloc[1] == pytest.approx(0.1)
    assert np.isnan(returns.AAA.iloc[0])
    assert wide.index.name == "date"


def test_missing_session_breaks_returns_and_missing_security_stays_nan():
    raw = prices(values=(100.0, 121.0), dates=["2024-01-02", "2024-01-04"])
    _, wide, returns = build_datasets(raw, ["AAA", "BBB"], SESSIONS)
    assert np.isnan(wide.AAA.iloc[1])
    assert returns.AAA.isna().all()
    assert returns.BBB.isna().all()


def test_bad_adjusted_price_does_not_create_infinite_returns():
    raw = prices(values=(0.0, 100.0, 110.0))
    _, _, returns = build_datasets(raw, ["AAA"], SESSIONS)
    assert np.isnan(returns.AAA.iloc[1])
    assert returns.AAA.iloc[2] == pytest.approx(0.1)


def test_merge_replaces_overlap_and_is_idempotent():
    old = prices()
    new = prices(values=(115.0, 125.0), dates=["2024-01-03", "2024-01-04"])
    merged = merge_prices(old, new)
    assert merged.adjusted_close.tolist() == [100.0, 115.0, 125.0]
    pd.testing.assert_frame_equal(merge_prices(merged, new), merged)
    _, _, returns = build_datasets(merged, ["AAA"], SESSIONS)
    assert returns.AAA.iloc[1] == pytest.approx(0.15)


def test_duplicate_input_is_rejected_by_transform():
    raw = pd.concat([prices(), prices().iloc[:1]], ignore_index=True)
    with pytest.raises(ValueError, match="Duplicate"):
        build_datasets(raw, ["AAA"], SESSIONS)


@pytest.mark.parametrize("mutation,code", [
    (lambda d: pd.concat([d, d.iloc[:1]], ignore_index=True), "duplicate_observations"),
    (lambda d: d.iloc[::-1], "chronological_order"),
    (lambda d: d.assign(close=-1.0), "non_positive_prices"),
    (lambda d: d.assign(currency="CAD"), "currency_mismatch"),
    (lambda d: d.drop(columns="adjusted_close"), "missing_columns"),
    (lambda d: d.assign(adjusted_close=np.inf), "non_finite_prices"),
    (lambda d: d.assign(adjusted_close=np.nan), "unavailable_adjusted_close"),
    (lambda d: d.iloc[:0], "empty_dataset"),
])
def test_validation_reports_errors(mutation, code):
    report = validate_prices(mutation(prices()), "AAA", SESSIONS, "USD", 0.5)
    assert code in [issue["code"] for issue in report["issues"]]
    assert not report["valid"]


def test_extreme_return_is_flagged_without_discarding():
    raw = prices(values=(100.0, 200.0, 201.0))
    report = validate_prices(raw, "AAA", SESSIONS, "USD", 0.5)
    assert report["valid"]
    assert "extreme_returns" in [i["code"] for i in report["issues"]]
    assert len(raw) == 3


def test_validation_identifies_internal_gaps_and_incomplete_end():
    raw = prices(values=(100.0,), dates=["2024-01-02"])
    report = validate_prices(raw, "AAA", SESSIONS, "USD", 0.5)
    assert "incomplete_end" in [i["code"] for i in report["issues"]]


def test_atomic_write_failure_preserves_original(tmp_path, monkeypatch):
    path = tmp_path / "AAA.parquet"
    atomic_parquet(prices(), path)
    original = path.read_bytes()
    def fail(*args, **kwargs):
        raise OSError("Disk full")
    monkeypatch.setattr(pd.DataFrame, "to_parquet", fail)
    with pytest.raises(OSError):
        atomic_parquet(prices(), path)
    assert path.read_bytes() == original
    assert not list(tmp_path.glob("*.tmp"))
