# Phase 2: Daily Six-Factor Historical Regression

## Purpose and boundaries

Phase 2 adds official daily factor data, standardized regression inputs, historical OLS estimates, and a self-contained HTML dashboard. Portfolio optimization, Covariance Optimization, Expected Return Forecasting, and Portfolio Backtesting are not implemented.

## Official sources and snapshots

The downloader uses the [Kenneth R. French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html), directly retrieving these official ZIP/CSV releases:

- [Fama/French 5 Factors (2x3), Daily](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip): `Mkt-RF`, `SMB`, `HML`, `RMW`, `CMA`, `RF`.
- [Momentum Factor, Daily](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_daily_CSV.zip): `Mom`.

Each attempt archives exact downloaded ZIP and CSV bytes under `data/raw/factors/snapshots/<run_id>/`. Validated current source CSV files are also available at `data/raw/factors/ff5_daily.csv` and `data/raw/factors/momentum_daily.csv`. These raw files retain official explanatory text and percentage units. A snapshot manifest records retrieval time, source URLs, HTTP metadata, source headers/version notes, SHA-256 hashes, validation details, and dates.

`data/processed/factors_daily.parquet` has a timezone-naive daily `date` index and columns `mkt_rf`, `smb`, `hml`, `rmw`, `cma`, `mom`, `rf`. Values are decimal daily returns: an official `1.25` becomes `0.0125`.

Updates retrieve both full official releases and compare all overlapping historical observations. Added, revised, and removed dates are recorded in `data/metadata/factor_manifest.json`. Updates do not assume that only the newest rows change. Invalid attempts are archived and reported separately without replacing a previously complete publication before validated output writing starts.

The parser identifies the expected daily header, accepts only valid eight-digit daily observation dates, and rejects malformed/duplicate/unordered observations. Monthly and annual tables are excluded. Missing-value sentinels remain missing and cause source validation errors; no interpolation or zero filling is performed. Extreme factor observations are retained and flagged.

Momentum history starts earlier than FF5. Their outer date join preserves unequal coverage explicitly, so early Momentum-only rows have missing FF5/RF fields. The manifest separately identifies the complete seven-field coverage used for research. Missing fields from unequal histories are not fabricated.

Calendar checking uses the project's XNYS calendar from July 1963 onward. Earlier Momentum dates are retained without applying the modern five-day weekmask, because early daily market history may include Saturday sessions. Even after 1963, historical source/calendar differences can occur, including 1960s holiday or exchange-closure conventions; reported calendar gaps require review and are not filled. The current 2010-onward stock sample and estimation window are checked separately.

## Factor definitions

| Field | Interpretation |
| --- | --- |
| `mkt_rf` | Market return minus the daily risk-free return |
| `smb` | Small-company minus large-company factor |
| `hml` | High book-to-market minus low book-to-market, commonly called value |
| `rmw` | Robust minus weak operating profitability |
| `cma` | Conservative minus aggressive investment |
| `mom` | High prior-return minus low prior-return portfolios, using the provider's prior 2–12 month momentum construction |
| `rf` | The provider's daily risk-free return; subtracted from each same-date stock return |

See the official [five-factor description](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/f-f_5_factors_2x3.html) and [daily Momentum description](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_mom_factor_daily.html). `rf` is used as supplied in the daily release; it is not divided by 252 again. The market factor is already an excess return; RF is not subtracted from `mkt_rf` again.

## Alignment and observation-date cutoff

The analysis reads the existing, hash-verified Phase 1 `data/processed/daily_returns.parquet`. It never invokes a stock download or rewrites stock prices, returns, company metadata, or papers.

Stock and factor observations are joined on the exact same exchange date. The standardized `data/processed/regression_panel.parquet` contains:

```text
date, ticker, stock_return, rf, excess_return,
mkt_rf, smb, hml, rmw, cma, mom
```

`excess_return = stock_return - rf`, with both inputs in daily decimal units. Missing stock cells, including pre-listing dates, remain missing. Missing factor dates and dates after the factor publication horizon are recorded in the regression report and are not shifted, carried forward, or replaced with zero.

`--as-of-date YYYY-MM-DD` sets an inclusive observation-date ceiling, additionally bounded by the latest completed exchange session. The effective analysis date is the latest complete factor date with a matching stock-date label at or before that ceiling. By default this is the latest complete common date. Individual stock missing values cannot rewind this shared endpoint.

The shared candidate window is selected first from the last configured number of matching date labels. Each stock then uses complete observations within that fixed window. An interior missing factor value reduces that stock's usable sample; it does not enlarge the window. Missing source dates are excluded by the exact-date join and explicitly recorded. A recent IPO may use fewer than 756 observations, but at least 504 are required by default. An older stock with too much missing data also fails this minimum rather than reaching further backward.

## Estimation and diagnostics

For each security:

```text
excess_return = alpha_daily
             + beta_mkt * mkt_rf
             + beta_smb * smb
             + beta_hml * hml
             + beta_rmw * rmw
             + beta_cma * cma
             + beta_mom * mom
             + residual
```

The implementation uses [statsmodels OLS](https://www.statsmodels.org/stable/generated/statsmodels.regression.linear_model.OLS.html), explicitly adding an intercept. It requires seven full-rank design columns and finite data. Per-security failures include insufficient complete observations, rank deficiency, non-finite values/diagnostics, or estimation errors; no failed security is silently discarded.

Defaults are editable in `config/settings.yaml`:

```yaml
regression_window: 756
minimum_valid_observations: 504
estimation_method: OLS
annualization_factor: 252
```

- **Alpha:** The fitted daily intercept. `alpha_annualized = alpha_daily * annualization_factor` is a linear annualization approximation, not a realized annual investment return or forecast.
- **Beta:** Historical conditional exposure to each factor over the sample, holding the other factors in the regression. A negative beta is an estimated opposite exposure, not a guarantee of hedging behavior.
- **R-Squared:** In-sample explanatory fit. Adjusted R-Squared accounts for the number of regressors. A high R-Squared does not establish future predictive performance.
- **Residual Volatility:** Sample standard deviation of fitted residuals, `ddof=1`, multiplied by `sqrt(annualization_factor)`. This convention is explicit and differs from the regression residual standard error based on residual degrees of freedom.
- **Alpha t-Statistic and p-Value:** Conventional, nonrobust OLS statistics. These do not correct for heteroskedasticity, serial correlation, or testing many securities. They should not be interpreted as trading signals.

The results include all requested coefficients/diagnostics, the actual per-stock estimation dates and observation count, effective `as_of_date`, and a model version. Numerical results are deterministic for fixed input bytes, settings, and compatible package versions. Run timestamps and snapshot identifiers are audit information and may change when repeating a run.

## Outputs and publication integrity

- `data/processed/regression_panel.parquet`: standardized same-date input panel.
- `data/processed/factor_regression_results.parquet`: successful estimates.
- `outputs/factor_regression_results.csv`: all successful estimates with the same schema.
- `data/metadata/regression_report.json`: settings, input snapshot identities, hashes, full failure map, date alignment and missingness, output hashes, and research limitations.
- `reports/factor_dashboard.html`: embedded result data, JavaScript, styles, and Plotly.
- `data/metadata/phase2/dashboard_manifest.json`: HTML hash and the referenced regression run.

Existing stock and factor writer locks are acquired in stock-then-factor order for snapshot reads. Input identities are verified against their manifests and checked again after reads. Regression writers have a separate lock. Dashboard generation verifies saved output hashes and current source identities, then holds source locks through final publication. An active writer causes a clear error; it does not supply a partially updated dataset. Local files are atomically replaced, and a `running` report is not a completed publication. There is no distributed database transaction; consumers must check publication status and hashes.

## Running in VS Code

Open this project root and select its existing `.venv` interpreter:

```bash
source .venv/bin/activate
python -m pip install -e '.[dev]'

# Individual steps.
python scripts/download_factors.py
python scripts/run_factor_regression.py
python scripts/generate_factor_report.py

# Complete workflow; refreshes official factor data first.
python scripts/run_phase2.py

# Reuse a validated downloaded snapshot without network requests.
python scripts/run_phase2.py --skip-factor-download

# Historical observation cutoff; still uses the selected revised snapshot.
python scripts/run_factor_regression.py --as-of-date 2025-12-31
python scripts/generate_factor_report.py

# Complete official release refresh and historical-revision check.
python scripts/update_factors.py

python -m pytest
```

The installed entry point supports `sgc-data download-factors`, `sgc-data update-factors`, `sgc-data regress`, `sgc-data factor-report`, and `sgc-data phase2`. `--config` and `--project-root` follow Phase 1 path conventions. `--tickers AAPL MSFT NVDA GOOGL JPM` can restrict a regression intentionally; this replaces Phase 2 analytical outputs for that selected universe and leaves all Phase 1 data intact.

Exit `0` means all requested work completed without skipped regressions, exit `1` means one or more requested stocks failed/were skipped, and exit `2` means invalid inputs or an operational failure. **The one-command workflow still generates the dashboard when some securities fail and others succeed.** Review the explicit failure list rather than treating an expected insufficient-history skip as a missing HTML report.

## Viewing the dashboard

Double-click `reports/factor_dashboard.html` in Finder, or open it in a browser. On macOS:

```bash
open reports/factor_dashboard.html
```

No local server, CDN, external font, or Python process is required for viewing. The dashboard embeds Plotly and its data, so the file is several megabytes. It provides overview cards, a stock selector, six Beta bars, Alpha/model-fit diagnostics, multi-stock comparison controls, filterable/sortable complete results, a CSV download, and skipped-stock reasons. Generated files are local research outputs, not a deployed website or a model API.

## Research limitations

**Historical factor regression estimates. Not forward-looking return forecasts.**

Kenneth French historical returns can change after CRSP corrections, revisions, and construction changes. The library changed from CRSP FIZ to CIZ research production starting with the January 2025 release; the exact downloaded release must be identified. Archiving a current release supports reproducing this analysis, but does not reconstruct every historically available vintage or publication date.

An `as_of_date` cutoff removes future observation dates from the regression. It does **not** turn current revised data into point-in-time data or establish when those factor observations were available to a historical investor. Do not place these results directly into a historical strategy backtest and claim that Look-Ahead Bias has been eliminated.

Phase 1 retains current-universe survivorship bias and Yahoo adjusted-price/corporate-action limitations. Daily factor and stock calendars can differ; publication lags are real. Estimates depend on the chosen window, missing-data rules, factor specification, and statistical assumptions. No Expected Return Forecasting, Covariance Optimization, or Portfolio Backtesting is provided in Phase 2.
