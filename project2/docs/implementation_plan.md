# Phase 1 Implementation Plan

**Goal:** Deliver a reusable daily US stock data pipeline inside this project, preserving all existing papers.

**Architecture:** A provider protocol returns normalized price observations and independent company metadata. Configuration, exchange sessions, validation, atomic storage, transformations, and orchestration remain separate. The CLI shares the same pipeline as future analytics consumers.

**Tech stack:** Python 3.11+, pandas, numpy, yfinance, pyarrow, PyYAML, exchange-calendars, pytest.

## Execution checklist

- [x] Inspect the existing directory and record SHA-256 paper checksums.
- [x] Write offline tests for return gaps, schemas, validation, updates, failures, configuration, and the exchange calendar; observe failures before implementation.
- [x] Implement `config.py` and `data/{calendar,provider,yahoo_provider,universe,storage,transform,validation,pipeline}.py` against those tests.
- [x] Add download, update, metadata, and saved-dataset validation CLI commands and English team documentation.
- [x] Freeze 100 cross-sector large-cap tickers and store dated source provenance separately.
- [x] Install editable package and dependencies in `.venv`; run and repair all offline tests.
- [x] Run a separate two-ticker real-data smoke test before the full initial download.
- [x] Attempt all 100 tickers; record actual successes, failures, date coverage, data quality, and installed versions.
- [x] Independently review the implementation, run targeted regression tests, and verify preserved paper checksums.

## Acceptance commands

```bash
.venv/bin/python -m pytest
.venv/bin/python scripts/download_prices.py --tickers AAPL MSFT --smoke
.venv/bin/python scripts/download_prices.py
.venv/bin/python scripts/validate_data.py
.venv/bin/python scripts/update_prices.py
```

Returns must use only Adjusted Close with no filling. Incremental writes replace overlap dates, preserve older history, and recompute all returns. A full refresh replaces a ticker's complete history. Invalid new observations must be retained for inspection and must not overwrite valid cached history. Each incomplete run must exit nonzero and record separate download failures.
