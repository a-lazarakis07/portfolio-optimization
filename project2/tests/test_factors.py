from dataclasses import replace
import io
import zipfile

import numpy as np
import pandas as pd
import pytest

from portfolio_backtester.factors.french import parse_daily_csv, extract_csv, combine_factors, validate_factor_data, revision_summary


FF5 = b"""This file was created using the 202609 CRSP database.\nReturns are in percent.\n,Mkt-RF,SMB,HML,RMW,CMA,RF\n20240102,1.25,-0.2,0.3,0.4,-0.5,0.02\n20240103,-1.0,0.1,0.2,0.3,0.4,0.02\n\nAnnual Factors: January-December\n2024,8,9,10,11,12,3\n202401,1,2,3,4,5,6\nCopyright French\n"""
MOM = b"""Momentum daily returns\n, Mom   \n20240103, 2.50\n20240104,-1.25\n"""


def test_official_parser_uses_only_daily_rows_and_converts_percent():
    frame, notes = parse_daily_csv(FF5, "ff5")
    assert list(frame.columns) == ["mkt_rf", "smb", "hml", "rmw", "cma", "rf"]
    assert frame.index.tolist() == [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")]
    assert frame.loc["2024-01-02", "mkt_rf"] == pytest.approx(0.0125)
    assert "202609" in notes


def test_zip_extraction_retains_exact_csv_bytes():
    body = io.BytesIO()
    with zipfile.ZipFile(body, "w") as archive:
        archive.writestr("F-F_Research_Data_5_Factors_2x3_daily.csv", FF5)
    csv, name = extract_csv(body.getvalue())
    assert csv == FF5
    assert name.endswith("daily.csv")


@pytest.mark.parametrize("content", [
    FF5.replace(b"20240103", b"20240102"),
    FF5.replace(b"20240103", b"20240230"),
    FF5.replace(b"20240103,-1.0", b"20240103,not-a-number"),
    b"No factor table found",
])
def test_malformed_or_duplicate_daily_data_is_rejected(content):
    with pytest.raises(ValueError):
        parse_daily_csv(content, "ff5")


def test_missing_sentinels_remain_missing_and_fail_source_validation():
    frame, _ = parse_daily_csv(FF5.replace(b"1.25", b"-99.99"), "ff5")
    assert np.isnan(frame.mkt_rf.iloc[0])
    report = validate_factor_data(frame)
    assert not report["valid"]
    assert report["missing_values"]["mkt_rf"] == 1


def test_non_trading_date_and_nonfinite_factor_are_rejected():
    frame, _ = parse_daily_csv(FF5.replace(b"20240103", b"20240106"), "ff5")
    assert not validate_factor_data(frame)["valid"]
    frame, _ = parse_daily_csv(FF5, "ff5")
    frame.iloc[0, 0] = np.inf
    assert not validate_factor_data(frame)["valid"]


def test_ff5_momentum_join_uses_actual_dates_without_filling():
    ff5, _ = parse_daily_csv(FF5, "ff5")
    mom, _ = parse_daily_csv(MOM, "momentum")
    combined, report = combine_factors(ff5, mom)
    assert list(combined.columns) == ["mkt_rf", "smb", "hml", "rmw", "cma", "mom", "rf"]
    assert np.isnan(combined.loc["2024-01-02", "mom"])
    assert np.isnan(combined.loc["2024-01-04", "rf"])
    assert combined.loc["2024-01-03", "mom"] == pytest.approx(0.025)
    assert report["complete_dates"] == 1


def test_revision_detection_covers_old_dates_removed_and_added():
    old, _ = parse_daily_csv(FF5, "ff5")
    new = old.copy()
    new.iloc[0, 0] += 0.01
    summary = revision_summary(old, new)
    assert summary["revised_dates"] == ["2024-01-02"]
    summary = revision_summary(old, new.iloc[:1])
    assert summary["removed_dates"] == ["2024-01-03"]


def test_malformed_interior_date_cannot_silently_truncate_daily_table():
    broken = FF5.replace(b"20240103,-1.0", b"2024-01-03,-1.0")
    with pytest.raises(ValueError, match="Malformed|Unexpected"):
        parse_daily_csv(broken, "ff5")
