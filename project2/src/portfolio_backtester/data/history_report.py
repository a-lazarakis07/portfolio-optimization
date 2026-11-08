"""Publish source-backed Universe V2 history and corporate-action review artifacts."""

import json
from pathlib import Path

import pandas as pd
import yaml

from portfolio_backtester.config import Settings
from portfolio_backtester.data.storage import atomic_json, atomic_parquet, atomic_target
from portfolio_backtester.factors.run import input_locks, _read_inputs
from portfolio_backtester.factors.download import file_hash
from .history_audit import audit_universe_history


def publish_history_audit(settings: Settings) -> dict:
    """Use raw action fields and validated source snapshots, leaving model schemas intact."""
    root = settings.root
    policy_path = root / "config/history_audit.yaml"
    profile_path = root / "config/security_history_profiles.yaml"
    policy = yaml.safe_load(policy_path.read_text())
    profiles = yaml.safe_load(profile_path.read_text()) or {}
    outputs = {}
    protected = {settings.path("processed_data_path") / name for name in
                 ("prices.parquet", "adjusted_close.parquet", "daily_returns.parquet", "factors_daily.parquet", "regression_panel.parquet", "factor_regression_results.parquet")}
    protected |= {settings.path("metadata_path") / name for name in ("dataset_manifest.json", "factor_manifest.json", "regression_report.json")}
    for key, name in policy["outputs"].items():
        path = (root / name).resolve()
        if Path(name).is_absolute() or not path.is_relative_to(root) or path in protected:
            raise ValueError("History audit outputs must be separate project-relative artifacts")
        if any(path.is_relative_to(root / folder) for folder in ("Papers", "config", "src", "scripts", "tests", ".git", ".venv", "data/raw")):
            raise ValueError("History audit output would overwrite a protected source or paper")
        outputs[key] = path
    if len(set(outputs.values())) != len(outputs):
        raise ValueError("History audit output paths must be distinct")
    with input_locks(settings):
        returns, factors, provenance = _read_inputs(settings)
        universe = pd.read_csv(settings.path("universe_path"))
        metadata_path = settings.path("metadata_path") / "company_metadata.parquet"
        if metadata_path.exists():
            names = pd.read_parquet(metadata_path).set_index("ticker").company_name
            universe["company_name"] = universe.ticker.map(names).fillna(universe.company_name)
        raw_paths = [settings.path("raw_data_path") / f"{ticker}.parquet" for ticker in universe.ticker]
        raw = pd.concat([pd.read_parquet(path) for path in raw_paths if path.exists()], ignore_index=True)
        quality = json.loads((settings.path("metadata_path") / "data_quality_report.json").read_text())
        invalid = {ticker for ticker, report in quality["tickers"].items() if not report["valid"]}
        coverage, flags, events, summary = audit_universe_history(raw, returns, universe, factors, policy,
            window=settings.regression_window, minimum=settings.minimum_valid_observations,
            profiles=profiles, invalid_tickers=invalid)
        summary.update(generated_at=pd.Timestamp.now(tz="UTC").isoformat(), status="running",
            input_provenance=provenance, policy_sha256=file_hash(policy_path), profiles_sha256=file_hash(profile_path),
            raw_file_sha256={str(path.relative_to(root)):file_hash(path) for path in raw_paths if path.exists()},
            sector_counts={key:int(value) for key,value in universe.groupby("sector").size().items()},
            source_profiles=profiles, limitations=["Current manually selected universe retains survivorship and hindsight selection bias.",
                "Available Yahoo rows are not proof of unchanged economic identity or PIT investability.",
                "Targeted issuer profiles and automatic action screens are not a complete security master.",
                "Official factor snapshots are revised historical data, not a complete PIT database."])
        atomic_json(summary, outputs["metadata_json"])
        for frame,key in [(coverage,"coverage_csv"),(events,"corporate_actions_csv")]:
            with atomic_target(outputs[key]) as temporary:
                frame.to_csv(temporary,index=False,date_format="%Y-%m-%d")
        atomic_parquet(flags, outputs["daily_flags"])
        report = _markdown_report(coverage, events, summary, policy)
        with atomic_target(outputs["report_md"]) as temporary:
            temporary.write_text(report,encoding="utf-8")
        summary["outputs"] = {key:{"path":str(path.relative_to(root)),"sha256":file_hash(path)}
                              for key,path in outputs.items() if key!="metadata_json"}
        summary["status"] = "complete"
        atomic_json(summary, outputs["metadata_json"])
        return summary


def _markdown_report(coverage: pd.DataFrame, events: pd.DataFrame, summary: dict, policy: dict) -> str:
    lines = ["# Universe V2 Historical Coverage and Security Audit", "",
        "## Scope and provenance", "", "Universe V2 is the exact 60 manually curated Long-History Diversified Research Universe candidates supplied by the project owner. It is not selected by IVV weight and is not historical S&P 500 membership. No automatic security replacement or manual predecessor/spin-off data splice was performed.", "",
        f"Requested exchange-session range: {summary['requested_first_session']} through {summary['last_session']}.",
        "", "The prior 100-stock configuration, complete data, manifests, regression outputs, dashboard, and source are hash-verified under the local `backups/universe_v1_100_stocks_20261107_161922/` snapshot. Its restore instructions and snapshot manifest are included. Paper files were read only for integrity checks.",
        "", "## Coverage policy", "", "Data Coverage Percentage uses all requested exchange sessions as its denominator, including unavailable pre-listing dates; Lifespan Coverage Percentage separately measures sessions between the first and last observed valid price. Total Valid Observations counts finite positive Close and Adjusted Close rows. No missing prices or returns were filled.",
        "", "Crisis availability means at least one observed return in the event interval. Full crisis coverage requires at least 95% of every expected crisis session, including dates outside a truncated input file. Pre-crisis estimation eligibility requires at least 504 complete stock/factor observations inside exactly the previous 756 exchange sessions, strictly before the event start. It does not imply unchanged security identity or a completed historical backtest.",
        "", "| Crisis | Defined interval | Any data | Full coverage | >=504 pre-crisis observations | Identity/action-screened >=504 |",
        "| --- | --- | ---: | ---: | ---: | ---: |"]
    for key,event in summary["crises"].items():
        lines.append(f"| {event['label']} | {event['start']} to {event['end']} | {len(event['available_tickers'])} | {len(event['full_coverage_tickers'])} | {len(event['pre_crisis_estimation_eligible_tickers'])} | {len(event['identity_clear_pre_crisis_eligible_tickers'])} |")
    lines += ["", "## Per-security review", "", "| Ticker | Company | Sector | First date | Last date | Valid prices | Coverage % | Status |", "| --- | --- | --- | --- | --- | ---: | ---: | --- |"]
    for r in coverage.itertuples(index=False):
        first = str(pd.Timestamp(r.first_available_date).date()) if pd.notna(r.first_available_date) else "Unavailable"
        last = str(pd.Timestamp(r.last_available_date).date()) if pd.notna(r.last_available_date) else "Unavailable"
        lines.append(f"| {r.ticker} | {r.company_name} | {r.sector} | {first} | {last} | {r.total_valid_observations} | {r.data_coverage_percentage:.2f} | {r.status} |")
    lines += ["", "Eligible means sufficient current observations with no flagged coverage/known-history issue under this audit, not certified PIT-investability. Limited retains late starts or review flags without automatic exclusion. Ineligible retains candidates with unusable or insufficient current data and records the reason. The CSV includes all crisis and pre-crisis fields.",
        "", "## Coverage and corporate-action limitations", ""]
    for r in coverage.loc[coverage.status.ne("Eligible")].itertuples(index=False):
        lines.append(f"- **{r.ticker}:** {r.corporate_action_ticker_history_warnings or 'Insufficient or invalid current observations.'}")
    lines += ["", "### HON action-field discrepancy", "", "Nasdaq documents a one-for-two reverse split on June 29, 2026, alongside the HONA distribution. Yahoo reports `Stock Splits = 0.9535` on that date and `1.061` on the 2025 Solstice date. These provider factors are not verified legal share-conversion ratios. They are retained and flagged; this discrepancy alone does not prove every Adjusted Close return is wrong. No fabricated correction, HONA backfill, or reconstructed combined shareholder wealth series is supplied.",
        "", "### GE and replacement interpretation", "", "GE and GEV are not active V2 candidates. HON is a separately selected issuer, not a synthetic substitute for GE and not a recipient of GE historical observations. GE's 2024 Vernova separation changes its own economic scope; its inactive raw files are preserved and never copied into HON. Any future peer replacement requires separate issuer and history validation.",
        "", "### Automatic screens and limitations", "", f"The event review CSV contains {len(events)} provider/known-action records, including {int((events.event_type=='extreme_return').sum()) if not events.empty else 0} extreme returns. Returns above 50% and adjustment-factor ratio changes above 10% are review flags, not automatic deletions. Ordinary splits are retained, and known distribution windows are separately flagged. Targeted profiles include major known separations for ABT, IBM, MRK, PFE, and JNJ; the catalog remains non-exhaustive.",
        "", "No candidate is silently removed. If a current series becomes Ineligible, potential same-sector candidates require independent verification before substitution; the current live audit has no automatic replacement mechanism. A genuine IPO or share-class inception cannot be solved by inventing pre-listing history.",
        "", "## Daily availability and investability flags", "", "`data/processed/universe_history_flags.parquet` has one row for every requested exchange session and active ticker. It separates price/return availability, predecessor/share-class mapping, known corporate-action windows, adjustment jumps, extreme returns, and provider splits. `point_in_time_investability_verified` is false on every row: observed prices alone do not establish historical index membership, liquidity, delisting completeness, or legal-security continuity. `research_return_available_identity_clear` is an audit screen, not a claim that hindsight or survivorship bias has been eliminated.",
        "", "The existing long prices and wide Adjusted Close/Daily Returns schemas are unchanged. Flags are separate from the numeric return matrix. No Covariance Engine, optimization, or backtest is implemented. Current risk regressions keep the configured recent 756-session window and 504 minimum; the longer data history is not fitted as one constant current Beta.",
        "", "## Primary sources for reviewed security histories", ""]
    for ticker,profile in sorted(summary["source_profiles"].items()):
        lines.append(f"- **{ticker}:** " + "; ".join(f"[Issuer/exchange source {i+1}]({url})" for i,url in enumerate(profile.get("sources",[]))))
    lines += ["- **GE context:** [GE Aerospace completion of the Vernova separation](https://www.geaerospace.com/news/press-releases/ge-aerospace-launches-independent-investment-grade-public-company-following-0).", "", "## Reproduction", "", "```bash", "python scripts/audit_universe_history.py", "python scripts/validate_data.py", "python scripts/run_phase2.py --skip-factor-download", "python -m pytest", "```", "", "Current official factor snapshots can be revised. `as_of_date` limits observation dates, but does not reproduce a historical publication vintage or eliminate Look-Ahead Bias."]
    return "\n".join(lines)+"\n"
