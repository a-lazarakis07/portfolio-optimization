"""Phase 2 command handlers shared by scripts and the sgc-data entry point."""

import argparse
import logging
from pathlib import Path
import sys

import pandas as pd

from portfolio_backtester.config import load_settings

COMMANDS = ["download-factors", "update-factors", "regress", "factor-report", "phase2"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SGC Phase 2 factor data, historical OLS, and offline reporting")
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--as-of-date", help="Inclusive observation-date cutoff (YYYY-MM-DD)")
    parser.add_argument("--tickers", nargs="+", help="Explicit regression universe; default: configured universe")
    parser.add_argument("--skip-factor-download", action="store_true", help="Use the validated cached official snapshot for a Phase 2 run")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        settings = load_settings(args.config, root=args.project_root)
        if args.command in {"download-factors", "update-factors"} or (args.command == "phase2" and not args.skip_factor_download):
            from .download import download_factors
            manifest = download_factors(settings)
            print(f"Factor data: COMPLETE; {manifest['complete_start_date']} through {manifest['complete_end_date']}; historical revised dates: {len(manifest['revisions']['revised_dates'])}")
            if args.command in {"download-factors", "update-factors"}:
                return 0
        report = None
        if args.command in {"regress", "phase2"}:
            from .run import run_factor_regression
            report = run_factor_regression(settings, tickers=args.tickers,
                as_of_date=pd.Timestamp(args.as_of_date) if args.as_of_date else None)
            print(f"Regression: {report['status'].upper()}; successful: {len(report['successful_tickers'])}; failed/skipped: {len(report['failed_tickers'])}")
            print(f"Analysis as of: {report['alignment']['as_of_date']}; window: {report['alignment']['candidate_window_start']} through {report['alignment']['candidate_window_end']}")
            for ticker, failure in report["failed_tickers"].items():
                print(f"{ticker}: {failure['reason']}; observations={failure['observations']}")
            print(f"Results: {settings.path('regression_results_path')}")
        if args.command == "factor-report" or (args.command == "phase2" and report["successful_tickers"]):
            from .dashboard import generate_factor_report
            output = generate_factor_report(settings)
            print(f"Offline HTML dashboard: {output}")
        return 1 if report is not None and report["failed_tickers"] else 0
    except Exception as error:
        print(f"Phase 2 failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 2
