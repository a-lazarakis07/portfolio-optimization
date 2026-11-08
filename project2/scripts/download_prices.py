"""Initialize historical prices using the configured stock universe."""

import sys
from portfolio_backtester.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["download", *sys.argv[1:]]))
