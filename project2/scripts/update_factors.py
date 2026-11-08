"""Refresh complete official releases and audit historical factor revisions."""

import sys
from portfolio_backtester.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["update-factors", *sys.argv[1:]]))
