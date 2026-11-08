# Universe V2 Historical Coverage and Security Audit

## Scope and provenance

Universe V2 is the exact 60 manually curated Long-History Diversified Research Universe candidates supplied by the project owner. It is not selected by IVV weight and is not historical S&P 500 membership. No automatic security replacement or manual predecessor/spin-off data splice was performed.

Requested exchange-session range: 1995-01-03 through 2026-11-06.

The prior 100-stock configuration, complete data, manifests, regression outputs, dashboard, and source are hash-verified under the local `backups/universe_v1_100_stocks_20261107_161922/` snapshot. Its restore instructions and snapshot manifest are included. Paper files were read only for integrity checks.

## Coverage policy

Data Coverage Percentage uses all requested exchange sessions as its denominator, including unavailable pre-listing dates; Lifespan Coverage Percentage separately measures sessions between the first and last observed valid price. Total Valid Observations counts finite positive Close and Adjusted Close rows. No missing prices or returns were filled.

Crisis availability means at least one observed return in the event interval. Full crisis coverage requires at least 95% of every expected crisis session, including dates outside a truncated input file. Pre-crisis estimation eligibility requires at least 504 complete stock/factor observations inside exactly the previous 756 exchange sessions, strictly before the event start. It does not imply unchanged security identity or a completed historical backtest.

| Crisis | Defined interval | Any data | Full coverage | >=504 pre-crisis observations | Identity/action-screened >=504 |
| --- | --- | ---: | ---: | ---: | ---: |
| Dot-com decline | 2000-03-10 to 2002-10-09 | 59 | 59 | 57 | 52 |
| Global Financial Crisis | 2007-10-09 to 2009-03-09 | 60 | 60 | 60 | 57 |
| COVID crash | 2020-02-19 to 2020-03-23 | 60 | 60 | 60 | 60 |
| 2022 inflation and rates shock | 2022-01-03 to 2022-10-12 | 60 | 60 | 60 | 60 |

## Per-security review

| Ticker | Company | Sector | First date | Last date | Valid prices | Coverage % | Status |
| --- | --- | --- | --- | --- | ---: | ---: | --- |
| AAPL | Apple Inc. | Information Technology | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Limited |
| ABT | Abbott Laboratories | Health Care | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Limited |
| AEP | American Electric Power Company, Inc. | Utilities | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| AMAT | Applied Materials, Inc. | Information Technology | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| AMD | Advanced Micro Devices, Inc. | Information Technology | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Limited |
| AMGN | Amgen Inc. | Health Care | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| AMT | American Tower Corporation | Real Estate | 1998-02-27 | 2026-11-06 | 7219 | 90.06 | Limited |
| AMZN | Amazon.com, Inc. | Consumer Discretionary | 1997-05-15 | 2026-11-06 | 7417 | 92.53 | Limited |
| AXP | American Express Company | Financials | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| BA | The Boeing Company | Industrials | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| BAC | Bank of America Corporation | Financials | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| BRK-B | Berkshire Hathaway Inc. | Financials | 1996-05-09 | 2026-11-06 | 7674 | 95.73 | Limited |
| C | Citigroup Inc. | Financials | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Limited |
| CAT | Caterpillar Inc. | Industrials | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| CMCSA | Comcast Corporation | Communication | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Limited |
| COP | ConocoPhillips | Energy | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Limited |
| COST | Costco Wholesale Corporation | Consumer Staples | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| CSCO | Cisco Systems, Inc. | Information Technology | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| CVX | Chevron Corporation | Energy | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| DE | Deere & Company | Industrials | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| DIS | The Walt Disney Company | Communication | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| DUK | Duke Energy Corporation | Utilities | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| ETN | Eaton Corporation plc | Industrials | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Limited |
| FCX | Freeport-McMoRan Inc. | Materials | 1995-07-10 | 2026-11-06 | 7886 | 98.38 | Limited |
| GILD | Gilead Sciences, Inc. | Health Care | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| GOOG | Alphabet Inc. | Communication | 2004-08-19 | 2026-11-06 | 5591 | 69.75 | Limited |
| GS | The Goldman Sachs Group, Inc. | Financials | 1999-05-04 | 2026-11-06 | 6922 | 86.35 | Limited |
| HD | The Home Depot, Inc. | Consumer Discretionary | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| HON | Honeywell International Inc. | Industrials | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Limited |
| IBM | International Business Machines Corporation | Information Technology | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Limited |
| INTC | Intel Corporation | Information Technology | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| JNJ | Johnson & Johnson | Health Care | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Limited |
| JPM | JPMorgan Chase & Co. | Financials | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| KO | The Coca-Cola Company | Consumer Staples | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| LLY | Eli Lilly and Company | Health Care | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| LOW | Lowe's Companies, Inc. | Consumer Discretionary | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| MCD | McDonald's Corporation | Consumer Discretionary | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| MRK | Merck & Co., Inc. | Health Care | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Limited |
| MS | Morgan Stanley | Financials | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Limited |
| MSFT | Microsoft Corporation | Information Technology | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Limited |
| NEM | Newmont Corporation | Materials | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| NVDA | NVIDIA Corporation | Information Technology | 1999-01-22 | 2026-11-06 | 6992 | 87.23 | Limited |
| ORCL | Oracle Corporation | Information Technology | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| PEP | PepsiCo, Inc. | Consumer Staples | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| PFE | Pfizer Inc. | Health Care | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Limited |
| PG | The Procter & Gamble Company | Consumer Staples | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| PSA | Public Storage | Real Estate | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| QCOM | QUALCOMM Incorporated | Information Technology | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| SHW | The Sherwin-Williams Company | Materials | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| SO | The Southern Company | Utilities | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| SPG | Simon Property Group, Inc. | Real Estate | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| T | AT&T Inc. | Communication | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Limited |
| TJX | The TJX Companies, Inc. | Consumer Discretionary | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| UNH | UnitedHealth Group Incorporated | Health Care | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| UNP | Union Pacific Corporation | Industrials | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| VLO | Valero Energy Corporation | Energy | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Limited |
| VZ | Verizon Communications Inc. | Communication | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Limited |
| WFC | Wells Fargo & Company | Financials | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| WMT | Walmart Inc. | Consumer Staples | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |
| XOM | ExxonMobil Holdings Corporation | Energy | 1995-01-03 | 2026-11-06 | 8016 | 100.00 | Eligible |

Eligible means sufficient current observations with no flagged coverage/known-history issue under this audit, not certified PIT-investability. Limited retains late starts or review flags without automatic exclusion. Ineligible retains candidates with unusable or insufficient current data and records the reason. The CSV includes all crisis and pre-crisis fields.

## Coverage and corporate-action limitations

- **AAPL:** 1 extreme returns and 0 adjustment ratio jumps require review
- **ABT:** The AbbVie separation changes Abbott's economic mix; no AbbVie series is appended to the parent history.
- **AMD:** 1 extreme returns and 0 adjustment ratio jumps require review
- **AMT:** Provider series begins 1998-02-27; earlier observations remain unavailable
- **AMZN:** Provider series begins 1997-05-15; earlier observations remain unavailable
- **BRK-B:** Provider series begins 1996-05-09; earlier observations remain unavailable
- **C:** 1 extreme returns and 0 adjustment ratio jumps require review
- **CMCSA:** Pre-November-2002 provider series maps legacy Comcast into the combined AT&T Broadband/Comcast issuer. Versant separation changes the current economic mix; no separate spun-off history is manually appended.
- **COP:** Earlier provider observations include integrated-company and predecessor exposure; the May 2012 Phillips 66 separation creates the current independent E&P focus. The review boundary is not a claim that the COP share lineage first existed in 2012.
- **ETN:** 0 extreme returns and 1 adjustment ratio jumps require review
- **FCX:** Provider series begins 1995-07-10; earlier observations remain unavailable
- **GOOG:** Yahoo maps Google history back to its 2004 IPO, but the current Class C shares were distributed in April 2014. Earlier rows are a flagged provider share-class/predecessor proxy, not evidence that Class C was independently tradable in 2004. | Provider series begins 2004-08-19; earlier observations remain unavailable
- **GS:** Provider series begins 1999-05-04; earlier observations remain unavailable
- **HON:** Earlier provider lineage predates the AlliedSignal/Honeywell combination. Solstice and Aerospace distributions change business exposure; current HON is the automation parent, not GE or HONA. Yahoo corporate-action factors must not be interpreted as verified share-conversion ratios.
- **IBM:** The Kyndryl distribution changes business composition and requires provider adjustment review.
- **JNJ:** The Kenvue split-off used an exchange offer, not a universal pro-rata cash dividend or ordinary stock split. Economic exposure changed; provider adjustments require review.
- **MRK:** The Organon distribution changes Merck's business composition; provider total-return adjustment requires review.
- **MS:** 1 extreme returns and 1 adjustment ratio jumps require review
- **MSFT:** 0 extreme returns and 1 adjustment ratio jumps require review
- **NVDA:** Provider series begins 1999-01-22; earlier observations remain unavailable
- **PFE:** Upjohn's separation and combination with Mylan into Viatris changes Pfizer's economic mix.
- **T:** Current T follows the SBC legal/share lineage before 2005; it must not be confused with the separate legacy AT&T Corp series. WarnerMedia distribution changes business exposure and requires distribution-adjustment review.
- **VLO:** The issuer describes a 1997-1998 gas-business merger and refinery spin-off. Pre-1998 rows are conservatively marked predecessor-review proxies; the January 1 boundary is an audit convention, not a claimed exact listing date. | 0 extreme returns and 1 adjustment ratio jumps require review
- **VZ:** Pre-July-2000 provider history represents Bell Atlantic/predecessor lineage, not an unchanged Verizon economic entity. VZ began NYSE trading after the Bell Atlantic/GTE combination.

### HON action-field discrepancy

Nasdaq documents a one-for-two reverse split on June 29, 2026, alongside the HONA distribution. Yahoo reports `Stock Splits = 0.9535` on that date and `1.061` on the 2025 Solstice date. These provider factors are not verified legal share-conversion ratios. They are retained and flagged; this discrepancy alone does not prove every Adjusted Close return is wrong. No fabricated correction, HONA backfill, or reconstructed combined shareholder wealth series is supplied.

### GE and replacement interpretation

GE and GEV are not active V2 candidates. HON is a separately selected issuer, not a synthetic substitute for GE and not a recipient of GE historical observations. GE's 2024 Vernova separation changes its own economic scope; its inactive raw files are preserved and never copied into HON. Any future peer replacement requires separate issuer and history validation.

### Automatic screens and limitations

The event review CSV contains 178 provider/known-action records, including 4 extreme returns. Returns above 50% and adjustment-factor ratio changes above 10% are review flags, not automatic deletions. Ordinary splits are retained, and known distribution windows are separately flagged. Targeted profiles include major known separations for ABT, IBM, MRK, PFE, and JNJ; the catalog remains non-exhaustive.

No candidate is silently removed. If a current series becomes Ineligible, potential same-sector candidates require independent verification before substitution; the current live audit has no automatic replacement mechanism. A genuine IPO or share-class inception cannot be solved by inventing pre-listing history.

## Daily availability and investability flags

`data/processed/universe_history_flags.parquet` has one row for every requested exchange session and active ticker. It separates price/return availability, predecessor/share-class mapping, known corporate-action windows, adjustment jumps, extreme returns, and provider splits. `point_in_time_investability_verified` is false on every row: observed prices alone do not establish historical index membership, liquidity, delisting completeness, or legal-security continuity. `research_return_available_identity_clear` is an audit screen, not a claim that hindsight or survivorship bias has been eliminated.

The existing long prices and wide Adjusted Close/Daily Returns schemas are unchanged. Flags are separate from the numeric return matrix. No Covariance Engine, optimization, or backtest is implemented. Current risk regressions keep the configured recent 756-session window and 504 minimum; the longer data history is not fitted as one constant current Beta.

## Primary sources for reviewed security histories

- **ABT:** [Issuer/exchange source 1](https://abbottinvestor.gcs-web.com/stock-info/dividend-split-history)
- **CMCSA:** [Issuer/exchange source 1](https://corporate.comcast.com/news-information/news-feed/comcast-completes-att-broadband-transaction); [Issuer/exchange source 2](https://cmcsa.gcs-web.com/news-releases/news-release-details/comcast-announces-completion-separation-versant-media-group-inc)
- **COP:** [Issuer/exchange source 1](https://www.conocophillips.com/about-us/our-history/)
- **GOOG:** [Issuer/exchange source 1](https://ir.nasdaq.com/node/81631)
- **HON:** [Issuer/exchange source 1](https://www.honeywell.com/us/en/company/history); [Issuer/exchange source 2](https://www.nasdaqtrader.com/TraderNews.aspx?id=ECA2026-399)
- **IBM:** [Issuer/exchange source 1](https://www.ibm.com/investor/services/faqs-about-the-kyndryl-holdings-inc-distribution)
- **JNJ:** [Issuer/exchange source 1](https://www.jnj.com/media-center/press-releases/johnson-johnson-announces-final-results-of-exchange-offer-and-finalizes-separation-of-kenvue-inc)
- **MRK:** [Issuer/exchange source 1](https://www.merck.com/news/merck-announces-completion-of-organon-co-spinoff/)
- **PFE:** [Issuer/exchange source 1](https://www.pfizer.com/news/press-release/press-release-detail/pfizer-completes-transaction-combine-its-upjohn-business)
- **T:** [Issuer/exchange source 1](https://investors.att.com/stockholder-services/cost-basis-guide/worksheet/att-corp); [Issuer/exchange source 2](https://investors.att.com/stock-information/historical-stock-information/historical-quote/att-inc)
- **VLO:** [Issuer/exchange source 1](https://www.valero.com/about/our-history)
- **VZ:** [Issuer/exchange source 1](https://www.verizon.com/about/sites/default/files/Verizon_Corporate_History.pdf)
- **GE context:** [GE Aerospace completion of the Vernova separation](https://www.geaerospace.com/news/press-releases/ge-aerospace-launches-independent-investment-grade-public-company-following-0).

## Reproduction

```bash
python scripts/audit_universe_history.py
python scripts/validate_data.py
python scripts/run_phase2.py --skip-factor-download
python -m pytest
```

Current official factor snapshots can be revised. `as_of_date` limits observation dates, but does not reproduce a historical publication vintage or eliminate Look-Ahead Bias.
