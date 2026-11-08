# Phase 1 Delivery and Validation Report

Validated: 2026-10-31 18:22:49 EDT

## Result

- Phase 1 only; no factor regression, optimization, or backtesting engine implemented.
- Python: 3.13.7; package: 0.1.0.
- Configured universe: 100 equities across 11 sectors.
- Initial price download: 100 successful, 0 failed; 402,537 observations.
- Actual aggregate coverage: 2010-01-04 through 2026-10-30.
- Adjusted Close matrix: 4,233 sessions by 100 tickers.
- Daily Returns matrix: 4,233 sessions by 100 tickers.
- Company metadata: 100 successful, 0 failed; all eight requested fields populated.
- Automated tests: 49 passed, 1 opt-in integration test skipped. Separate live two-ticker smoke test passed.
- Saved raw schemas, processed values, reconstructed Daily Returns, and publication hashes: PASS.
- Two repeated no-new-session updates: both exit 0, 100 skipped, 0 downloads, 0 failures.
- SHA-256 hashes for all 100 raw and 3 processed Parquet files were unchanged by both updates.
- Independent review completed; reproduced issues were fixed and covered by regression tests.
- Original research papers: all five SHA-256 checksums unchanged.
- Maintained source, tests, configuration, and documentation are in English.

## Data quality warnings requiring review

The pipeline retained these four extreme return observations; they were not independently adjudicated or removed. The configured review threshold is an absolute daily return greater than 50%.

| Date | Ticker | Daily Return (decimal) |
| --- | --- | ---: |
| 2012-05-07 | VRTX | 0.55359527 |
| 2013-04-19 | VRTX | 0.61906564 |
| 2016-04-22 | AMD | 0.52290083 |
| 2016-07-05 | DHR | 0.61218459 |

The following 12 securities have provider-confirmed listing histories starting after the configured beginning; their earlier observations and returns remain NaN:

ABBV, ANET, CEG, CRWD, DELL, GEV, META, MPC, PANW, PLTR, SNDK, TSLA.

There were no missing-session, currency-mismatch, duplicate, non-positive-price, or missing-required-field errors in the final price validation. Passing structural validation does not establish that every Yahoo observation is economically correct. Current-universe survivorship bias, current-only company metadata, historical provider corrections, and complex corporate actions remain research limitations.

## Generated outputs

- `data/raw/<TICKER>.parquet`: 100 normalized provider files.
- `data/processed/prices.parquet`
- `data/processed/adjusted_close.parquet`
- `data/processed/daily_returns.parquet`
- `data/metadata/company_metadata.parquet`
- `data/metadata/initial_download_manifest.json`: preserved evidence of the full initial run.
- `data/metadata/dataset_manifest.json`: current publication marker and hashes.
- `data/metadata/data_quality_report.json`
- `data/metadata/download_failures.json`
- `data/metadata/saved_data_validation.json`
- `data/metadata/metadata_refresh_report.json`
- `data/metadata/idempotence_report.json` and two update logs.
- `data/smoke/`: isolated AAPL/MSFT history and validation outputs.

## Commands

Run from the project root:

```bash
source .venv/bin/activate
python -m pytest
python scripts/update_prices.py
python scripts/validate_data.py
python scripts/update_prices.py --full-refresh
python scripts/download_metadata.py
```

The local environment and data files already exist. Other team members should create their own `.venv` and run `python -m pip install -e ".[dev]"`. GitHub Actions has been configured but has not been run remotely. No repository was initialized and no remote publication was performed.

## Created collaboration and source files

- `.github/workflows/tests.yml`
- `.gitignore`
- `.vscode/extensions.json`
- `README.md`
- `config/settings.yaml`
- `config/universe.csv`
- `config/universe_manifest.json`
- `docs/execution_report.md`
- `docs/implementation_plan.md`
- `docs/papers_integrity.json`
- `docs/universe_source_holdings.csv`
- `pyproject.toml`
- `requirements-lock.txt`
- `scripts/download_metadata.py`
- `scripts/download_prices.py`
- `scripts/update_prices.py`
- `scripts/validate_data.py`
- `src/portfolio_backtester/__init__.py`
- `src/portfolio_backtester/cli.py`
- `src/portfolio_backtester/config.py`
- `src/portfolio_backtester/data/__init__.py`
- `src/portfolio_backtester/data/calendar.py`
- `src/portfolio_backtester/data/pipeline.py`
- `src/portfolio_backtester/data/provider.py`
- `src/portfolio_backtester/data/storage.py`
- `src/portfolio_backtester/data/transform.py`
- `src/portfolio_backtester/data/universe.py`
- `src/portfolio_backtester/data/validation.py`
- `src/portfolio_backtester/data/verify.py`
- `src/portfolio_backtester/data/yahoo_provider.py`
- `tests/conftest.py`
- `tests/test_config_calendar.py`
- `tests/test_data.py`
- `tests/test_pipeline.py`
- `tests/test_verify_cli.py`
- `tests/test_yahoo.py`
