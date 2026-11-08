"""Estimate historical six-factor OLS regressions using saved research inputs."""

import sys
from portfolio_backtester.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["regress", *sys.argv[1:]]))
