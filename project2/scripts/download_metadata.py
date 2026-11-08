"""Refresh company information independently of price downloads."""

import sys
from portfolio_backtester.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["metadata", *sys.argv[1:]]))
