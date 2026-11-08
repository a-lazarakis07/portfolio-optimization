"""Render validated saved estimates as a self-contained offline HTML dashboard."""

import sys
from portfolio_backtester.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["factor-report", *sys.argv[1:]]))
