"""Audit every active security's history, crisis samples, and corporate actions."""

import sys
from portfolio_backtester.config import load_settings
from portfolio_backtester.data.history_report import publish_history_audit

if __name__ == "__main__":
    try:
        report=publish_history_audit(load_settings())
        print(f"History audit: COMPLETE; stocks={len(report['configured_tickers'])}; status counts={report['status_counts']}")
        for key,event in report['crises'].items():
            print(f"{key}: available={len(event['available_tickers'])}; full={len(event['full_coverage_tickers'])}; pre-crisis eligible={len(event['pre_crisis_estimation_eligible_tickers'])}")
    except Exception as error:
        print(f"History audit failed: {type(error).__name__}: {error}",file=sys.stderr)
        raise SystemExit(2)
