"""English command-line entry points for the Phase 1 data pipeline."""

import argparse
from dataclasses import replace
import logging
from pathlib import Path
import sys

import pandas as pd

from .config import load_settings
from .data.calendar import latest_completed_session
from .data.pipeline import Pipeline
from .data.universe import load_universe, validate_tickers
from .data.verify import verify_saved


def main(argv: list[str] | None = None) -> int:
    """Run a data command; exit 1 for incomplete data and 2 for invalid usage."""
    argv = list(sys.argv[1:] if argv is None else argv)
    factor_commands = ["download-factors", "update-factors", "regress", "factor-report", "phase2"]
    if argv and argv[0] in factor_commands:
        from .factors.cli import main as factor_main
        return factor_main(argv)
    parser = argparse.ArgumentParser(description="SGC stock data and historical factor research pipelines")
    parser.add_argument("command", choices=["download", "update", "metadata", "validate", *factor_commands])
    parser.add_argument("--config", type=Path, help="Settings YAML (default: project config/settings.yaml)")
    parser.add_argument("--project-root", type=Path, help="Project root for all relative configured paths")
    parser.add_argument("--full-refresh", action="store_true", help="Replace complete ticker histories, including old adjustments")
    parser.add_argument("--tickers", nargs="+", help="Explicit symbols for an isolated --smoke run")
    parser.add_argument("--smoke", action="store_true", help="Use isolated data/smoke paths and explicit tickers")
    parser.add_argument("--start-date", help="ISO start date; requires --smoke or --full-refresh for price commands")
    parser.add_argument("--end-date", help="Inclusive ISO end date, capped at the latest completed session")
    parser.add_argument("--force", action="store_true", help="Force company metadata refresh regardless of age policy")
    parser.add_argument("--verbose", action="store_true", help="Enable diagnostic logging")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    try:
        if args.tickers and not args.smoke:
            raise ValueError("--tickers requires --smoke to protect the main universe datasets")
        if args.smoke and not args.tickers:
            raise ValueError("--smoke requires explicit --tickers")
        if args.start_date and args.command in {"download", "update"} and not (args.smoke or args.full_refresh):
            raise ValueError("Changing --start-date requires --smoke or --full-refresh")
        settings = load_settings(args.config, root=args.project_root)
        if args.start_date:
            start = pd.Timestamp(args.start_date)
            if pd.isna(start) or start.tz is not None or start != start.normalize():
                raise ValueError("--start-date must be a valid timezone-naive date")
            settings = replace(settings, start_date=start)
        tickers = validate_tickers(args.tickers) if args.tickers else load_universe(settings.path("universe_path"))
        if args.smoke:
            settings = replace(settings, raw_data_path="data/smoke/raw", processed_data_path="data/smoke/processed",
                               metadata_path="data/smoke/metadata", cache_path="data/smoke/cache")
        if args.command == "validate":
            report = verify_saved(settings, tickers)
            print(f"Saved dataset validation: {'PASS' if report['valid'] else 'FAIL'}")
            for error in report["errors"]:
                print(error, file=sys.stderr)
            return 0 if report["valid"] else 1
        from .data.yahoo_provider import YahooProvider
        pipeline = Pipeline(settings, YahooProvider(settings))
        if args.command == "metadata":
            report = pipeline.refresh_metadata(tickers, force=args.force)
            print(f"Metadata: {len(report['successful_tickers'])} refreshed, {len(report['skipped_tickers'])} skipped, {len(report['failed_tickers'])} failed")
            return 1 if report["failed_tickers"] else 0
        end = latest_completed_session(delay_minutes=settings.completion_delay_minutes)
        if settings.end_date_policy == "fixed":
            end = min(end, settings.end_date)
        if args.end_date:
            requested = pd.Timestamp(args.end_date)
            if pd.isna(requested) or requested.tz is not None or requested != requested.normalize():
                raise ValueError("--end-date must be a valid timezone-naive date")
            end = min(end, requested)
        manifest = pipeline.run(tickers, mode=args.command, full_refresh=args.full_refresh, end=end)
        print(f"Price pipeline: {manifest['status'].upper()}")
        print(f"Configured: {len(tickers)}; successful: {len(manifest['successful_tickers'])}; failed: {len(manifest['failed_tickers'])}; unchanged: {len(manifest['skipped_tickers'])}")
        print(f"Actual coverage: {manifest['actual_start_date']} through {manifest['actual_end_date']}; rows: {manifest['row_count']}")
        print(f"Processed data: {settings.path('processed_data_path')}")
        print(f"Quality report: {settings.path('metadata_path') / 'data_quality_report.json'}")
        return 0 if manifest["status"] == "complete" else 1
    except (ValueError, OSError, RuntimeError, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
