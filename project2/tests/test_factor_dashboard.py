import re

import pandas as pd

from test_factor_run import saved_inputs
from portfolio_backtester.factors.run import run_factor_regression, load_regression_artifacts
from portfolio_backtester.factors.dashboard import render_dashboard, generate_factor_report


def test_dashboard_is_self_contained_and_includes_all_research_controls(settings):
    saved_inputs(settings)
    run_factor_regression(settings, tickers=["AAA", "MISSING"])
    results, report = load_regression_artifacts(settings)
    html = render_dashboard(results, report)
    assert "Historical factor regression estimates. Not forward-looking return forecasts." in html
    assert "stock-select" in html and "comparison-metric" in html
    assert "result-filter" in html and "export-csv" in html
    assert "Plotly.newPlot" in html
    assert "MISSING" in html and "insufficient_valid_observations" in html
    assert not re.search(r'<script[^>]+src\s*=', html, re.I)
    assert not re.search(r'<link[^>]+href\s*=\s*[\"\']https?://', html, re.I)
    path = generate_factor_report(settings)
    assert path == settings.path("dashboard_path")
    assert path.read_text().startswith("<!DOCTYPE html>")


def test_programmatic_dashboard_paths_cannot_overwrite_stock_inputs(settings):
    from dataclasses import replace
    import pytest
    saved_inputs(settings)
    run_factor_regression(settings, tickers=["AAA"])
    path = settings.path("processed_data_path") / "daily_returns.parquet"
    original = path.read_bytes()
    changed = replace(settings, dashboard_path="data/processed/daily_returns.parquet")
    with pytest.raises(ValueError):
        generate_factor_report(changed)
    assert path.read_bytes() == original
