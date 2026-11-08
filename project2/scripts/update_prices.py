"""Incrementally update historical prices with a correction overlap."""

import sys
from portfolio_backtester.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["update", *sys.argv[1:]]))
