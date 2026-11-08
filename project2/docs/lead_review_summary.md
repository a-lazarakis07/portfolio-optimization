# Project 2 — Risk & Backtesting Tool: Lead Review

**Status date:** November 8, 2026

**Owner:** SGC Optimization Team, Project 2

**Current scope:** Research-grade data infrastructure and historical factor analytics. Portfolio backtesting and the covariance/risk engine are not yet implemented.

## What has been delivered

| Milestone | Status | Evidence |
| --- | --- | --- |
| Phase 1 — Equity data pipeline | Complete | 60 currently selected US equities, daily adjusted-price and return datasets, quality manifests, incremental update tooling |
| Phase 2 — Six-factor research | Complete | Official daily Fama–French five factors, Momentum and RF, same-date excess-return alignment, 60 stock OLS regressions, local offline dashboard |
| Universe V2 — Long-history coverage | Complete with research caveats | 60 manually curated securities across 11 sectors; requested price start 1995-01-01; actual coverage 1995-01-03 to 2026-11-06 |
| Phase 3 — Covariance and risk engine | Not started | Planned factor-implied covariance, sample and shrinkage benchmarks, portfolio risk contribution |
| Walk-forward backtesting and stress testing | Not started | Planned point-in-time strategy adapter, rebalancing, costs, historical scenario and risk/performance attribution |

The current factor observations end on September 30, 2026, so the latest six-factor regressions use a 756-session window ending that date (with a 504-observation minimum). These dates must not be confused with the more recent stock price horizon.

## Verified outputs and where to review them

1. **Research dashboard:** `reports/factor_dashboard.html` (download and open in a local browser; HTML includes Plotly).
2. **Regression table:** `outputs/factor_regression_results.csv` (60 fitted securities).
3. **Source and methodology:** `docs/phase2_factor_model.md`.
4. **Universe history audit:** `docs/universe_v2_history_audit.md` and `outputs/universe_history_coverage.csv`.
5. **Reproducibility evidence:** `docs/universe_v2_execution_report.md` and `data/metadata/` manifests.

The existing offline test suite was run on November 8, 2026: **99 passed, 1 optional live Yahoo test skipped**. The prior published Universe V2 validation reported 60/60 successful downloads, 60/60 successful current OLS regressions, and a successful restore rehearsal of the earlier 100-stock snapshot.

## Local developer quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest
python scripts/validate_data.py
python scripts/run_phase2.py --skip-factor-download
open reports/factor_dashboard.html
```

The factor-only regression run requires the previously saved factor and stock datasets. When cloning a code-only copy without these files, download market prices and official factor data first following the main `README.md`. The source-data providers' redistribution terms must be respected.

## How this fits the team's repository

The lead's `portfolio-optimization` repository defines:

- **Project 1:** Given forecasts, build a tradable optimized portfolio (including potential Black–Litterman).
- **Project 2:** Given any portfolio, explain its risks, backtest results, and potential improvements.

**Proposed integration boundary:** Project 1 returns dated target portfolio weights and model/constraint metadata; Project 2 provides historical risk inputs, executes an out-of-sample walk-forward simulation, accounts for turnover and trading costs, and compares performance and factor risks against baselines. Historical weights must be generated only from information available at each decision time; current-day optimized weights must not be retroactively applied as if known in prior periods.

This submission places the validated source, configuration, tests and project documentation under `project2/` on the `p2/phase1-phase2-universe-v2` feature branch for team review. The private standalone development repository remains the source of generated market datasets. Full market data, research PDFs, virtual environments and personal backups are intentionally excluded from the public team repository.

## Limitations requiring explicit disclosure

- The 60-stock universe is manually selected from surviving companies. It is **not** a point-in-time historical investment universe; survivorship/hindsight bias remains.
- Availability of a historical price is not proof that an issuer, share class or ticker identity is directly comparable across decades. Corporate-action and mapping warnings remain flagged.
- Official factor files can be historically revised; observation-date truncation alone does not reconstruct publication vintages.
- Historical OLS alpha/beta and in-sample R-squared do **not** constitute future expected returns or a verified profitable strategy.
- A cross-crisis coverage audit is **not** equivalent to a completed walk-forward portfolio backtest.

## Next milestone

Implement Phase 3's well-tested `Covariance & Portfolio Risk Engine` using factor-implied `B Sigma_F B^T + D`, and compare against sample and Ledoit–Wolf covariance estimates. Define the dated strategy/target-weights interface with Project 1 before Phase 4's walk-forward backtester.
