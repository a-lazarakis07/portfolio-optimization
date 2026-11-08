"""Run the official factor refresh, historical regression, and dashboard workflow."""

import sys
from portfolio_backtester.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["phase2", *sys.argv[1:]]))
