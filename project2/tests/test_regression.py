from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from portfolio_backtester.factors import ALL_COLUMNS, FACTOR_COLUMNS
from portfolio_backtester.factors.alignment import build_regression_panel
from portfolio_backtester.factors.regression import fit_regressions, RESULT_COLUMNS
from portfolio_backtester.data.calendar import trading_sessions


def synthetic_data(n=850):
    dates = trading_sessions(pd.Timestamp("2021-01-04"), pd.Timestamp("2025-12-31"))[:n]
    generator = np.random.default_rng(42)
    factors = pd.DataFrame(generator.normal(0, 0.01, (n, 6)), index=dates, columns=FACTOR_COLUMNS)
    factors["rf"] = 0.0001
    beta = np.array([1.1, -0.2, 0.3, 0.4, -0.1, 0.6])
    excess = 0.0002 + factors[FACTOR_COLUMNS].to_numpy() @ beta
    returns = pd.DataFrame({"AAA": excess + factors.rf, "BBB": excess + factors.rf}, index=dates)
    returns.columns.name = "ticker"
    return returns, factors, beta


def test_excess_return_uses_same_date_rf_and_exact_join(settings):
    returns, factors, _ = synthetic_data()
    factors.loc[factors.index[30], "rf"] = 0.0004
    factors = factors.drop(factors.index[40])
    panel, report, dates = build_regression_panel(returns, factors, ["AAA"], settings)
    row = panel.loc[panel.date.eq(returns.index[30])].iloc[0]
    assert row.excess_return == pytest.approx(returns.AAA.iloc[30] - 0.0004)
    assert returns.index[40] not in panel.date.tolist()
    assert str(returns.index[40].date()) in report["stock_dates_without_complete_factors"]


def test_known_synthetic_alpha_and_betas_are_recovered(settings):
    returns, factors, beta = synthetic_data()
    panel, alignment, dates = build_regression_panel(returns, factors, ["AAA"], settings)
    results, failures = fit_regressions(panel, ["AAA"], dates, settings, pd.Timestamp(alignment["as_of_date"]))
    assert not failures
    assert list(results.columns) == RESULT_COLUMNS
    row = results.iloc[0]
    assert row.alpha_daily == pytest.approx(0.0002, abs=1e-12)
    assert row.alpha_annualized == pytest.approx(0.0002 * settings.annualization_factor)
    assert row[["beta_mkt", "beta_smb", "beta_hml", "beta_rmw", "beta_cma", "beta_mom"]].astype(float).to_numpy() == pytest.approx(beta)
    assert row.observations == 756
    assert row.r_squared == pytest.approx(1)


def test_window_does_not_expand_for_ipo_or_missing_returns(settings):
    returns, factors, _ = synthetic_data()
    returns.loc[returns.index[-756:-300], "BBB"] = np.nan
    panel, alignment, dates = build_regression_panel(returns, factors, ["AAA", "BBB", "MISSING"], settings)
    results, failures = fit_regressions(panel, ["AAA", "BBB", "MISSING"], dates, settings, dates[-1])
    assert len(dates) == 756
    assert results.ticker.tolist() == ["AAA"]
    assert failures["BBB"]["observations"] == 300
    assert failures["BBB"]["reason"] == "insufficient_valid_observations"
    assert failures["MISSING"]["observations"] == 0


def test_explicit_as_of_excludes_future_rows(settings):
    returns, factors, _ = synthetic_data()
    cutoff = returns.index[650]
    panel, alignment, dates = build_regression_panel(returns, factors, ["AAA"], settings, as_of_date=cutoff)
    assert panel.date.max() == cutoff
    assert max(dates) == cutoff
    assert alignment["as_of_date"] == str(cutoff.date())
    changed_returns = returns.copy()
    changed_returns.loc[changed_returns.index > cutoff] = 999.0
    changed_factors = factors.copy()
    changed_factors.loc[changed_factors.index > cutoff] = 999.0
    other, _, other_dates = build_regression_panel(changed_returns, changed_factors, ["AAA"], settings, as_of_date=cutoff)
    pd.testing.assert_frame_equal(panel, other)
    assert dates.equals(other_dates)


def test_default_end_is_last_complete_common_factor_day(settings):
    returns, factors, _ = synthetic_data()
    factors = factors.iloc[:-20]
    panel, report, dates = build_regression_panel(returns, factors, ["AAA"], settings)
    assert dates[-1] == factors.index[-1]
    assert len(report["stock_dates_without_complete_factors"]) == 20
    assert report["as_of_date"] == str(factors.index[-1].date())


def test_non_full_rank_design_is_recorded(settings):
    returns, factors, _ = synthetic_data()
    factors["hml"] = factors["smb"]
    panel, report, dates = build_regression_panel(returns, factors, ["AAA"], settings)
    results, failures = fit_regressions(panel, ["AAA"], dates, settings, dates[-1])
    assert results.empty
    assert failures["AAA"]["reason"] == "rank_deficient_design"


def test_interior_missing_factor_does_not_extend_candidate_window(settings):
    returns, factors, _ = synthetic_data()
    factors.loc[factors.index[-50], "mom"] = np.nan
    panel, _, dates = build_regression_panel(returns, factors, ["AAA"], settings)
    results, _ = fit_regressions(panel, ["AAA"], dates, settings, dates[-1])
    assert len(dates) == 756
    assert results.observations.iloc[0] == 755


def test_trailing_missing_stock_returns_do_not_rewind_window_endpoint(settings):
    returns, factors, _ = synthetic_data(n=1200)
    returns.loc[returns.index[-500:], "AAA"] = np.nan
    panel, report, dates = build_regression_panel(returns, factors, ["AAA"], settings)
    results, failures = fit_regressions(panel, ["AAA"], dates, settings, dates[-1])
    assert dates[-1] == factors.index[-1]
    assert failures["AAA"]["observations"] == 256
    assert results.empty


def test_residual_volatility_uses_sample_residual_standard_deviation(settings):
    returns, factors, _ = synthetic_data()
    returns["AAA"] += np.random.default_rng(5).normal(0, 0.003, len(returns))
    panel, _, dates = build_regression_panel(returns, factors, ["AAA"], settings)
    results, _ = fit_regressions(panel, ["AAA"], dates, settings, dates[-1])
    sample = panel.loc[panel.date.isin(dates)]
    row = results.iloc[0]
    beta = row[["beta_mkt", "beta_smb", "beta_hml", "beta_rmw", "beta_cma", "beta_mom"]].astype(float).to_numpy()
    residuals = sample.excess_return - row.alpha_daily - sample[FACTOR_COLUMNS].to_numpy() @ beta
    assert row.residual_volatility_annualized == pytest.approx(residuals.std(ddof=1) * np.sqrt(252))


@pytest.mark.parametrize("kind", ["duplicate_stock_date", "duplicate_factor_date", "missing_factor_column", "empty"])
def test_invalid_research_inputs_fail_clearly(settings, kind):
    returns, factors, _ = synthetic_data()
    if kind == "duplicate_stock_date":
        returns = pd.concat([returns, returns.iloc[:1]])
    elif kind == "duplicate_factor_date":
        factors = pd.concat([factors, factors.iloc[:1]])
    elif kind == "missing_factor_column":
        factors = factors.drop(columns="rf")
    else:
        returns = returns.iloc[:0]
    with pytest.raises(ValueError):
        build_regression_panel(returns, factors, ["AAA"], settings)
