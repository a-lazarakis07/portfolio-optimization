# Phase 2 Implementation Plan

**Goal:** Add official daily Fama-French five-factor and Momentum data, reproducible six-factor OLS estimates, and an offline interactive research dashboard without changing Phase 1 stock datasets or papers.

**Architecture:** Reuse `Settings`, project-relative paths, exchange calendar helpers, atomic writes, and CLI dispatch. Keep official downloads/parsing, alignment, OLS estimation, persisted run manifests, and HTML presentation in separate modules. Price and factor updates remain independent.

## Work sequence

- [x] Inspect Phase 1 and record SHA-256 checksums for protected stock files and papers.
- [x] Test and implement official ZIP/CSV parsing and factor quality checks.
- [x] Download the actual official releases and archive exact source bytes with hashes and source notes.
- [x] Test and implement same-date excess-return alignment and explicit as-of truncation.
- [x] Test and implement bounded-window, complete-case OLS with rank and diagnostic checks.
- [x] Publish panel, results, CSV, run provenance, and per-ticker failure reasons independently of Phase 1 outputs.
- [x] Implement an embedded-Plotly HTML dashboard with selection, comparison, sortable/filterable results, and CSV export.
- [x] Extend CLI entry points and provide a one-command Phase 2 workflow.
- [x] Run offline tests, real official-data updates, and actual regressions including AAPL, MSFT, NVDA, GOOGL, and JPM.
- [x] Review code independently, inspect the rendered HTML in a browser, and fix actionable findings.
- [x] Update English team documentation and record final results and protected-file integrity.

## Core policies

- Official inputs remain in percent in exact raw CSV snapshots; processed values are decimals.
- Missing factor dates are recorded without filling. Regression candidates are the last configured number of common dates before any per-stock complete-case filtering.
- Each regression includes an intercept, uses at most 756 candidate dates by default, and requires 504 valid observations and a full-rank design matrix.
- Alpha is linearly annualized daily intercept; residual volatility uses sample residual standard deviation. Estimates are historical in-sample relationships, never forecasts.
- A current revised historical factor snapshot is not a point-in-time database, even when observations are cut off with `as_of_date`.
- Input/output hashes and publication status prevent silently displaying stale, mismatched results.
