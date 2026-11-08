"""Download both complete official daily factor releases."""

import sys
from portfolio_backtester.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["download-factors", *sys.argv[1:]]))
