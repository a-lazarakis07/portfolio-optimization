# Phase 2 Execution Report

Validated: 2026-11-01 16:59:31 EST

## Delivered result

- Official daily Fama-French five-factor, Momentum, and RF snapshots downloaded and validated.
- Same-date excess-return panel, bounded-window six-factor OLS engine, result exports, and self-contained Plotly dashboard implemented.
- No Expected Return Forecasting, Covariance Optimization, Portfolio Optimization, or Portfolio Backtesting implemented.
- Existing `.venv`, configuration/path resolution, atomic storage, calendar helpers, logging, CLI entry point, and writer locks reused.

## Actual official coverage

| Dataset | Observations | Start | End |
| --- | ---: | --- | --- |
| ff5 | 15,918 | 1963-07-01 | 2026-09-30 |
| momentum | 26,237 | 1926-11-03 | 2026-09-30 |

Complete seven-field factor coverage: **1963-07-01 through 2026-09-30**.

A second full official refresh detected 0 revised dates, 0 added dates, and 0 removed dates relative to the first downloaded release. Both exact source releases and their manifests remain archived. The absence of revisions on this repeated request does not imply that future releases cannot revise history.

## Actual regression results

- Configured stocks: 100.
- Successful regressions: 99.
- Failed/skipped regressions: 1.
- Candidate window: 2023-09-26 through 2026-09-30, 756 dates.
- Effective analysis date: 2026-09-30.
- Standardized panel rows: 421,100.
- Median R-Squared: 0.298701.
- Stock dates without complete published factors: 22; the stock file extends through 2026-10-30.
- GEV has 629 valid observations and qualifies; other successful securities have 756 observations.

| Skipped ticker | Reason | Valid observations | Required |
| --- | --- | ---: | ---: |
| SNDK | insufficient_valid_observations | 408 | 504 |

The window was not extended and missing IPO returns were not filled. The completed workflow exits `1` to signal the explicit skipped stock, while still generating the dashboard and all successful results.

## Independent real-data checks

The requested five securities were fitted from actual Phase 1 returns and official factor inputs. Coefficients were independently recomputed with `numpy.linalg.lstsq`; all maximum absolute differences were below 1.3e-15. No expected result was hardcoded.

| Ticker | Observations | Market Beta | R-Squared | Historical Annualized Alpha |
| --- | ---: | ---: | ---: | ---: |
| AAPL | 756 | 1.222895 | 0.439666 | 0.080898 |
| MSFT | 756 | 0.963166 | 0.481609 | 0.045343 |
| NVDA | 756 | 1.822444 | 0.618574 | 0.302077 |
| GOOGL | 756 | 1.097586 | 0.409029 | 0.191112 |
| JPM | 756 | 1.082021 | 0.511534 | 0.026270 |

Alpha values are decimals and represent linear annualization of a fitted daily intercept, not realized or predicted investment returns.

## Automated and browser verification

- Offline test suite: **86 passed, 1 optional integration test skipped, 0 failures/errors**.
- Existing Phase 1 tests remain passing; all Phase 2 tests use synthetic fixtures or mocks, not network requests.
- The separate official download and full refresh were executed against the real primary source.
- The combined `run_phase2.py --skip-factor-download` workflow completed using the validated real snapshot and produced the final HTML.
- `compileall` completed and `pip check` found no broken dependencies.
- Protected-file SHA-256 verification: **108 unchanged** (100 raw stock files, three Phase 1 processed files, five papers).
- The real HTML was inspected in a browser: 99 table records, six exposure bars, NVDA/AAPL stock selection, Momentum comparison, MSFT ticker filtering, numeric Market Beta sorting, and SNDK failure reason display verified.
- Browser JavaScript console: no errors observed. External script tags: zero. Plotly, styles, and result records are embedded.
- A browser screenshot is saved at `reports/factor_dashboard_preview.jpg`.
- Independent code review completed. Reproduced window back-extension, malformed-source truncation, protected-path, and stale-generation issues were fixed with regression tests.

## Created and modified files

New modules under `src/portfolio_backtester/factors/`: `__init__.py`, `french.py`, `download.py`, `alignment.py`, `regression.py`, `run.py`, `dashboard.py`, and `cli.py`.

New scripts: `scripts/download_factors.py`, `scripts/update_factors.py`, `scripts/run_factor_regression.py`, `scripts/generate_factor_report.py`, and `scripts/run_phase2.py`.

New tests: `tests/test_factors.py`, `tests/test_factor_download.py`, `tests/test_regression.py`, `tests/test_factor_run.py`, and `tests/test_factor_dashboard.py`. Extended `tests/test_config_calendar.py` with protected-output tests.

Updated `src/portfolio_backtester/config.py`, `src/portfolio_backtester/cli.py`, `src/portfolio_backtester/__init__.py`, `config/settings.yaml`, `pyproject.toml`, `requirements-lock.txt`, `.gitignore`, and `README.md`.

New documentation: `docs/phase2_implementation_plan.md`, `docs/phase2_factor_model.md`, and this report.

## Generated research outputs

- `data/raw/factors/ff5_daily.csv` and `momentum_daily.csv` (exact source percentage CSVs).
- `data/raw/factors/snapshots/<run_id>/` (exact ZIP/CSV archives and manifests).
- `data/processed/factors_daily.parquet` (decimal daily factors).
- `data/processed/regression_panel.parquet`.
- `data/processed/factor_regression_results.parquet`.
- `outputs/factor_regression_results.csv`.
- `data/metadata/factor_manifest.json` and `regression_report.json`.
- `data/metadata/phase2/` (test XML, protected-file checksums, real-data validation, dashboard manifest, workflow log).
- `reports/factor_dashboard.html` and `factor_dashboard_preview.jpg`.

## Remaining research limitations

- SNDK cannot meet the default 504-observation requirement from available history. This is an explicit data limitation, not an imputed regression.
- Official factors currently stop at September 30, 2026. The 22 later stock sessions are not supplied with fabricated factors.
- Both source/calendar reconciliations flag 56 dates in 1963–1969 as calendar gaps, including known historical holidays; these are source/calendar convention discrepancies requiring review, not verified erroneous source returns. They do not occur in the current estimation window.
- Earlier Momentum dates are preserved without modern-weekmask verification; all unmatched source coverage is recorded.
- Factor history may be revised after CRSP changes. The current archived release and `as_of_date` truncation do not establish a historically point-in-time information set or eliminate Look-Ahead Bias.
- Phase 1 Yahoo-price limitations, current-universe survivorship bias, and conventional OLS inference assumptions remain. No forward-looking forecast is produced.

## Run and view

From the project root in VS Code:

```bash
source .venv/bin/activate
python scripts/run_phase2.py
open reports/factor_dashboard.html
```

To repeat the analysis without new network requests:

```bash
python scripts/run_phase2.py --skip-factor-download
```

The final HTML is self-contained and can be opened directly in a browser; no server is needed. Detailed setup and methodology are in `README.md` and `docs/phase2_factor_model.md`.
