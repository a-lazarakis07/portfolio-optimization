# Universe V2 Execution Report

Execution date: November 7, 2026 (America/Toronto).

The active universe is `v2-long-history-60`: the exact 60 project-owner supplied candidates across 11 sectors, selected manually as a Long-History Diversified Research Universe. It is not an IVV-weight selection or a historical index constituent universe. No Phase 3 Covariance Engine is implemented.

## Download and coverage results

- Full Refresh: 60 successful downloads, zero failures, 474,549 valid price rows.
- Requested start: January 1, 1995. Observed range: January 3, 1995 through November 6, 2026.
- Wide matrices: 8,016 exchange sessions by 60 tickers; existing numeric schemas are preserved.
- Fifty-three series reach the first requested exchange session. Later starts: FCX (1995-07-10), BRK-B (1996-05-09), AMZN (1997-05-15), AMT (1998-02-27), NVDA (1999-01-22), GS (1999-05-04), GOOG (2004-08-19).
- All five added company profiles were fetched successfully: CMCSA, LOW, HON, PSA, SPG.
- No pre-listing prices or returns were invented, forward filled, or replaced with another issuer's history.

| Sector | Stocks |
| --- | ---: |
| Communication | 5 |
| Consumer Discretionary | 5 |
| Consumer Staples | 5 |
| Energy | 4 |
| Financials | 8 |
| Health Care | 8 |
| Industrials | 6 |
| Information Technology | 10 |
| Materials | 3 |
| Real Estate | 3 |
| Utilities | 3 |

| Crisis | At least one return | >=95% crisis sessions | >=504 observations in previous 756 sessions | Identity/action-screened >=504 |
| --- | ---: | ---: | ---: | ---: |
| Dot-com decline (2000-03-10 to 2002-10-09) | 59 | 59 | 57 | 52 |
| GFC (2007-10-09 to 2009-03-09) | 60 | 60 | 60 | 57 |
| COVID crash (2020-02-19 to 2020-03-23) | 60 | 60 | 60 | 60 |
| Inflation shock (2022-01-03 to 2022-10-12) | 60 | 60 | 60 | 60 |

## History audit limitations

The audit retains all 60 candidates: 36 Eligible, 24 Limited, zero Ineligible. Limited is a research warning, not a failed download or automatic exclusion. The full per-stock reasons appear in `outputs/universe_history_coverage.csv` and `docs/universe_v2_history_audit.md`.

Limited tickers: AAPL, ABT, AMD, AMT, AMZN, BRK-B, C, CMCSA, COP, ETN, FCX, GOOG, GS, HON, IBM, JNJ, MRK, MS, MSFT, NVDA, PFE, T, VLO, VZ.

Important identity reviews cover T/SBC, VZ/Bell Atlantic, HON/AlliedSignal, CMCSA/legacy Comcast, GOOG's earlier share-class proxy, and VLO's restructuring. Known separations and four extreme-return observations are retained as review flags. HON's provider action factor on June 29, 2026 differs from Nasdaq's legal reverse-split ratio; this is explicitly flagged, and no speculative adjustment is applied. The discrepancy alone does not establish that all Adjusted Close returns are incorrect. GE and GEV remain inactive and are not used as proxy histories. No candidate requires automatic replacement; no unverified peer is substituted.

The 480,960 per-date/ticker rows in `data/processed/universe_history_flags.parquet` separate observed availability, predecessor/share-class mappings, and action review windows. Historical point-in-time investability is explicitly unverified. The manually selected surviving candidates and current historical factor vintage do not eliminate Survivorship Bias, Hindsight Bias, or Look-Ahead Bias.

## Phase 2 results

- Sixty successful regressions, zero failures, each using 756 complete observations with a minimum of 504.
- Effective current model date: September 30, 2026. Estimation dates: September 26, 2023 through September 30, 2026.
- Stock observations reach November 6, 2026, but the downloaded official complete seven-field factor history ends September 30, 2026. The HTML's September date is the correct common-data endpoint, not evidence that new stock histories were omitted.
- Historical `as_of_date=2000-03-09` validation: 57 successful estimates; GOOG has zero observations, GS has 215, and NVDA has 285, below the 504 minimum. The historical check did not replace current outputs.
- Independent NumPy least-squares calculations verify all 60 current Alpha/Beta estimates and R-Squared values. Maximum coefficient difference: 2.886579864025407e-15.
- Current model calculations retain observed provider returns, including flagged action periods; corporate-action completeness remains a research limitation.
- The standalone Dashboard displays 60 of 60 stocks and zero failures. AAPL/HON profile interaction was checked in the browser, with no JavaScript console errors; `reports/factor_dashboard_preview.jpg` was refreshed.

## Verification evidence

- Complete pytest suite: **95 passed, 1 skipped**. The skip is the optional live Yahoo smoke test; the actual 60-stock download was completed separately.
- Saved raw/processed Data Validation: **PASS**.
- Daily Returns independently match consecutive Adjusted Close ratios, with no missing-value fill.
- `data/metadata/universe_v2_numerical_validation.json`: matrix schema and all-current-regression checks, plus historical as-of results.
- `data/metadata/universe_v2_restore_validation.json`: successful recovery rehearsal of the 100-stock/99-regression prior state.
- `data/metadata/universe_v2_tests.xml`: complete test-suite evidence.
- `data/metadata/universe_history_audit.json`: input hashes, source profiles, policy, and output hashes.

## Recovery and version control

Local recovery snapshot: `backups/universe_v1_100_stocks_20261107_161922/`. All 219 copied original files were hash-verified. A temporary restoration loaded 100 configured stocks, 99 historical successful regressions, and passed saved-data validation. All five original Papers files remain byte-identical. See the snapshot's `RESTORE.md` and `snapshot_manifest.json` before recovery.

The user subsequently authorized updating the existing GitHub repository. Publication is scoped to V2 code, configuration, documentation, active data, current factor source snapshot, and validation evidence. The local backup and unrelated pre-existing inactive-ticker changes are excluded. No reset, clean, forced push, or Papers modification is performed.

## Repeat the update

From the project root, using the existing virtual environment:

```bash
.venv/bin/python scripts/update_prices.py
.venv/bin/python scripts/run_phase2.py
.venv/bin/python scripts/audit_universe_history.py
.venv/bin/python scripts/validate_data.py
.venv/bin/python -m pytest
```

Use `--full-refresh` for an intentional full-history restatement after preserving a new recovery snapshot. Historical analysis can use `scripts/run_phase2.py --as-of-date YYYY-MM-DD`; this replaces the canonical Phase 2 outputs, so preserve the current run first. A date cutoff does not reconstruct a historical factor publication vintage.
