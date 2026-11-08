from pathlib import Path

import pandas as pd
import pytest

from test_factors import FF5, MOM
from portfolio_backtester.factors.download import download_factors


def test_download_uses_both_official_sources_and_saves_provenance(settings, monkeypatch):
    import io
    import zipfile
    def fetch(url, config):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("daily.csv", FF5 if "5_Factors" in url else MOM)
        return buffer.getvalue(), {"last_modified": "test release"}
    monkeypatch.setattr("portfolio_backtester.factors.download.fetch_official_zip", fetch)
    manifest = download_factors(settings)
    assert manifest["status"] == "complete"
    assert set(manifest["sources"]) == {"ff5", "momentum"}
    assert len(manifest["sources"]["ff5"]["zip_sha256"]) == 64
    assert settings.path("factor_data_path").exists()
    frame = pd.read_parquet(settings.path("factor_data_path"))
    assert frame.loc["2024-01-03", "mom"] == 0.025
    repeated = download_factors(settings)
    assert repeated["revisions"]["revised_dates"] == []
    assert repeated["revisions"]["added_dates"] == []


def test_failed_factor_fetch_does_not_overwrite_existing_price_data(settings, monkeypatch):
    marker = settings.path("processed_data_path") / "daily_returns.parquet"
    marker.parent.mkdir(parents=True)
    marker.write_bytes(b"protected stock data")
    def fail(*args):
        raise RuntimeError("Official source unavailable")
    monkeypatch.setattr("portfolio_backtester.factors.download.fetch_official_zip", fail)
    with pytest.raises(RuntimeError):
        download_factors(settings)
    assert marker.read_bytes() == b"protected stock data"
