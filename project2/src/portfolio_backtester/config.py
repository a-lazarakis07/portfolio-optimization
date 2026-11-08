"""Load validated settings with project-relative paths."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


@dataclass(frozen=True)
class Settings:
    root: Path
    start_date: pd.Timestamp = pd.Timestamp("2010-01-01")
    data_provider: str = "yahoo"
    end_date_policy: str = "latest_completed_session"
    end_date: pd.Timestamp | None = None
    frequency: str = "1d"
    market_calendar: str = "XNYS"
    expected_currency: str = "USD"
    completion_delay_minutes: int = 30
    universe_path: str = "config/universe.csv"
    universe_manifest_path: str = "config/universe_manifest.json"
    raw_data_path: str = "data/raw"
    processed_data_path: str = "data/processed"
    metadata_path: str = "data/metadata"
    cache_path: str = ".cache/yfinance"
    retry_attempts: int = 3
    backoff_seconds: float = 2.0
    max_backoff_seconds: float = 30.0
    timeout_seconds: float = 20.0
    pacing_seconds: float = 0.5
    batch_size: int = 10
    batch_pause_seconds: float = 2.0
    refresh_overlap_days: int = 10
    extreme_return_threshold: float = 0.5
    metadata_refresh_policy: str = "manual"
    metadata_max_age_days: int = 30
    factor_raw_data_path: str = "data/raw/factors"
    factor_data_path: str = "data/processed/factors_daily.parquet"
    factor_manifest_path: str = "data/metadata/factor_manifest.json"
    ff5_url: str = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip"
    momentum_url: str = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_daily_CSV.zip"
    regression_panel_path: str = "data/processed/regression_panel.parquet"
    regression_results_path: str = "data/processed/factor_regression_results.parquet"
    regression_report_path: str = "data/metadata/regression_report.json"
    regression_csv_path: str = "outputs/factor_regression_results.csv"
    dashboard_path: str = "reports/factor_dashboard.html"
    regression_window: int = 756
    minimum_valid_observations: int = 504
    annualization_factor: int = 252
    estimation_method: str = "OLS"

    def path(self, key: str) -> Path:
        """Resolve a configured relative path without leaving the project."""
        value = Path(getattr(self, key))
        target = (self.root / value).resolve()
        if value.is_absolute() or not target.is_relative_to(self.root.resolve()):
            raise ValueError(f"{key} must be a relative path inside the project")
        return target


def load_settings(path: str | Path | None = None, *, root: Path | None = None) -> Settings:
    """Load YAML settings; a supplied project root supports relocatable tests."""
    default_root = Path(__file__).resolve().parents[2]
    config_path = Path(path).resolve() if path else default_root / "config/settings.yaml"
    project_root = Path(root).resolve() if root else config_path.parent.parent
    data: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("Settings must be a YAML mapping")
    retry = data.pop("retry", {})
    if not isinstance(retry, dict) or set(retry) - {"max_attempts", "backoff_seconds", "max_backoff_seconds"}:
        raise ValueError("Invalid retry configuration")
    renames = {"request_timeout_seconds": "timeout_seconds", "request_pacing_seconds": "pacing_seconds"}
    data = {renames.get(key, key): value for key, value in data.items()}
    for key, target in [("max_attempts", "retry_attempts"), ("backoff_seconds", "backoff_seconds"),
                        ("max_backoff_seconds", "max_backoff_seconds")]:
        if key in retry:
            data[target] = retry[key]
    for key in ("start_date", "end_date"):
        if data.get(key) is not None:
            data[key] = pd.Timestamp(data[key])
            if pd.isna(data[key]) or data[key].tz is not None or data[key] != data[key].normalize():
                raise ValueError(f"{key} must be a valid timezone-naive date")
    try:
        settings = Settings(root=project_root, **data)
    except TypeError as error:
        raise ValueError(f"Unknown or invalid settings: {error}") from error
    if settings.data_provider != "yahoo" or settings.frequency != "1d" or settings.market_calendar != "XNYS":
        raise ValueError("Phase 1 supports yahoo, 1d, and the XNYS calendar")
    if settings.end_date_policy not in {"latest_completed_session", "fixed"}:
        raise ValueError("Unsupported end_date_policy")
    if settings.end_date_policy == "fixed" and settings.end_date is None:
        raise ValueError("fixed end_date_policy requires end_date")
    if settings.end_date is not None and settings.end_date < settings.start_date:
        raise ValueError("end_date must not precede start_date")
    if settings.metadata_refresh_policy not in {"manual", "missing", "stale"}:
        raise ValueError("metadata_refresh_policy must be manual, missing, or stale")
    for key in ("batch_size", "retry_attempts", "metadata_max_age_days", "regression_window",
                "minimum_valid_observations", "annualization_factor"):
        value = getattr(settings, key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{key} must be a positive integer")
    for key in ("refresh_overlap_days", "completion_delay_minutes"):
        value = getattr(settings, key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{key} must be a nonnegative integer")
    for key in ("timeout_seconds", "extreme_return_threshold", "pacing_seconds", "backoff_seconds",
                "max_backoff_seconds", "batch_pause_seconds"):
        value = getattr(settings, key)
        if not isinstance(value, (float, int)) or pd.isna(value) or value < 0:
            raise ValueError(f"{key} must be a nonnegative number")
    if settings.timeout_seconds == 0 or settings.extreme_return_threshold == 0:
        raise ValueError("Timeout and extreme return threshold must be positive")
    if settings.estimation_method != "OLS":
        raise ValueError("Phase 2 supports OLS estimation with an intercept")
    if not 8 <= settings.minimum_valid_observations <= settings.regression_window:
        raise ValueError("minimum_valid_observations must be between 8 and regression_window")
    for key in ("universe_path", "universe_manifest_path", "raw_data_path", "processed_data_path", "metadata_path", "cache_path"):
        settings.path(key)
    validate_phase2_paths(settings)
    return settings


def validate_phase2_paths(settings: Settings) -> None:
    """Keep Phase 2 writers separate from papers, stock data, and each other."""
    from urllib.parse import urlparse
    keys = ("factor_data_path", "factor_manifest_path", "regression_panel_path", "regression_results_path",
            "regression_report_path", "regression_csv_path", "dashboard_path")
    paths = [settings.path(key) for key in keys]
    protected = [settings.path("processed_data_path") / name for name in
                 ("prices.parquet", "adjusted_close.parquet", "daily_returns.parquet")]
    protected += [settings.path("metadata_path") / name for name in
                  ("dataset_manifest.json", "data_quality_report.json", "download_failures.json", "company_metadata.parquet",
                   "initial_download_manifest.json", "saved_data_validation.json", "metadata_refresh_report.json", "idempotence_report.json")]
    implicit = [settings.path("factor_manifest_path").parent / name for name in ("factor_last_attempt.json", ".factors.lock")]
    implicit += [settings.path("regression_report_path").parent / ".regression.lock",
                 settings.path("regression_report_path").parent / "phase2/regression_last_attempt.json",
                 settings.path("regression_report_path").parent / "phase2/dashboard_manifest.json"]
    managed = [settings.root / name for name in ("config", "src", "scripts", "tests", "docs", ".venv", ".git", ".github", ".vscode")]
    papers = settings.root / "Papers"
    raw_root = settings.path("raw_data_path")
    factor_raw = settings.path("factor_raw_data_path")
    if len(set(paths + implicit)) != len(paths + implicit) or any(path in protected for path in paths):
        raise ValueError("Phase 2 output paths must be distinct and must not overwrite Phase 1 outputs")
    if any(path.is_relative_to(directory) for path in paths + [factor_raw] for directory in managed):
        raise ValueError("Phase 2 outputs must not overwrite project source, configuration, or development files")
    if any(path.is_dir() for path in paths):
        raise ValueError("Phase 2 file paths must not point to directories")
    if any(path.is_relative_to(papers) for path in paths + [factor_raw]) or any(path.parent == raw_root for path in paths):
        raise ValueError("Phase 2 output paths must not modify Papers or individual stock raw files")
    if factor_raw == raw_root or factor_raw.is_file() or any(path.is_relative_to(factor_raw) for path in paths):
        raise ValueError("Factor source directory must be separate from stock files and Phase 2 result files")
    for url in (settings.ff5_url, settings.momentum_url):
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "mba.tuck.dartmouth.edu" or parsed.username or parsed.password:
            raise ValueError("Factor sources must use the official HTTPS Kenneth French Data Library host")
