"""Historical in-sample OLS estimates for Fama-French five factors plus Momentum."""

import logging

import numpy as np
import pandas as pd
import statsmodels.api as sm

from portfolio_backtester.config import Settings
from . import FACTOR_COLUMNS, MODEL_VERSION

LOGGER = logging.getLogger(__name__)
BETA_COLUMNS = ["beta_mkt", "beta_smb", "beta_hml", "beta_rmw", "beta_cma", "beta_mom"]
RESULT_COLUMNS = ["ticker", "alpha_daily", "alpha_annualized", *BETA_COLUMNS,
                  "r_squared", "adjusted_r_squared", "residual_volatility_annualized",
                  "alpha_t_stat", "alpha_p_value", "observations", "regression_start_date",
                  "regression_end_date", "as_of_date", "model_version"]


def fit_regressions(panel: pd.DataFrame, tickers: list[str], candidate_dates: pd.DatetimeIndex,
                    settings: Settings, as_of_date: pd.Timestamp) -> tuple[pd.DataFrame, dict]:
    """Fit each security on complete cases inside the same bounded candidate dates."""
    if len(candidate_dates) > settings.regression_window:
        raise ValueError("Candidate window exceeds configured regression_window")
    if candidate_dates.has_duplicates or not candidate_dates.is_monotonic_increasing or (candidate_dates > as_of_date).any():
        raise ValueError("Invalid or future regression candidate dates")
    if panel.duplicated(["date", "ticker"]).any():
        raise ValueError("Regression panel contains duplicate ticker-date records")
    selected = panel.loc[panel.date.isin(candidate_dates)]
    results, failures = [], {}
    for ticker in tickers:
        sample = selected.loc[selected.ticker.eq(ticker)].dropna(subset=["excess_return", *FACTOR_COLUMNS]).sort_values("date")
        observations = len(sample)
        if observations < settings.minimum_valid_observations:
            failures[ticker] = {"reason": "insufficient_valid_observations", "observations": observations,
                                "minimum_required": settings.minimum_valid_observations}
            continue
        x = sm.add_constant(sample[FACTOR_COLUMNS], has_constant="add")
        y = sample.excess_return
        if not np.isfinite(x.to_numpy()).all() or not np.isfinite(y.to_numpy()).all():
            failures[ticker] = {"reason": "non_finite_regression_data", "observations": observations}
            continue
        rank = np.linalg.matrix_rank(x.to_numpy())
        if rank != len(FACTOR_COLUMNS) + 1:
            failures[ticker] = {"reason": "rank_deficient_design", "observations": observations,
                                "rank": int(rank), "required_rank": len(FACTOR_COLUMNS) + 1}
            continue
        try:
            model = sm.OLS(y, x, missing="raise", hasconst=True).fit()
            alpha = float(model.params["const"])
            values = {"ticker": ticker, "alpha_daily": alpha,
                      "alpha_annualized": alpha * settings.annualization_factor,
                      **{target: float(model.params[source]) for source, target in zip(FACTOR_COLUMNS, BETA_COLUMNS)},
                      "r_squared": float(model.rsquared), "adjusted_r_squared": float(model.rsquared_adj),
                      "residual_volatility_annualized": float(model.resid.std(ddof=1) * np.sqrt(settings.annualization_factor)),
                      "alpha_t_stat": float(model.tvalues["const"]), "alpha_p_value": float(model.pvalues["const"]),
                      "observations": observations, "regression_start_date": sample.date.min(),
                      "regression_end_date": sample.date.max(), "as_of_date": pd.Timestamp(as_of_date), "model_version": MODEL_VERSION}
            numeric = [value for key, value in values.items() if key not in {"ticker", "regression_start_date", "regression_end_date", "as_of_date", "model_version"}]
            if not np.isfinite(numeric).all():
                failures[ticker] = {"reason": "non_finite_model_diagnostics", "observations": observations}
                continue
            results.append(values)
            LOGGER.info("%s: OLS complete, n=%d, R-squared=%.3f", ticker, observations, model.rsquared)
        except (ValueError, np.linalg.LinAlgError) as error:
            failures[ticker] = {"reason": "ols_estimation_failed", "observations": observations, "detail": str(error)}
    frame = pd.DataFrame(results, columns=RESULT_COLUMNS)
    for column in ("regression_start_date", "regression_end_date", "as_of_date"):
        frame[column] = pd.to_datetime(frame[column])
    frame["observations"] = frame.observations.astype("int64")
    for column in ["alpha_daily", "alpha_annualized", *BETA_COLUMNS, "r_squared", "adjusted_r_squared",
                   "residual_volatility_annualized", "alpha_t_stat", "alpha_p_value"]:
        frame[column] = frame[column].astype("float64")
    return frame.sort_values("ticker").reset_index(drop=True), failures
