"""Download complete official releases and audit historical factor revisions."""

import hashlib
from importlib.metadata import version
import json
import logging
import time
import uuid

from curl_cffi import requests
import pandas as pd

from portfolio_backtester import __version__
from portfolio_backtester.config import Settings, validate_phase2_paths
from portfolio_backtester.data.storage import atomic_json, atomic_parquet, atomic_target, pipeline_lock
from .french import combine_factors, extract_csv, parse_daily_csv, revision_summary, validate_factor_data

LOGGER = logging.getLogger(__name__)


def file_hash(path) -> str:
    """Return the SHA-256 content identity of a local artifact."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch_official_zip(url: str, settings: Settings) -> tuple[bytes, dict]:
    """Fetch an official ZIP with bounded requests and capped exponential retries."""
    for attempt in range(settings.retry_attempts):
        try:
            time.sleep(settings.pacing_seconds)
            response = requests.get(url, timeout=settings.timeout_seconds, impersonate="chrome")
            response.raise_for_status()
            body = response.content
            if len(body) > 32_000_000 or not body.startswith(b"PK"):
                raise ValueError("Official factor endpoint did not return an acceptable ZIP archive")
            return body, {"last_modified": response.headers.get("last-modified"), "etag": response.headers.get("etag")}
        except Exception as error:
            if attempt + 1 == settings.retry_attempts:
                raise RuntimeError(f"Official factor download failed for {url}: {error}") from error
            delay = min(settings.backoff_seconds * 2 ** attempt, settings.max_backoff_seconds)
            LOGGER.warning("Factor request failed (%d/%d): %s; retrying in %.1fs", attempt + 1, settings.retry_attempts, error, delay)
            time.sleep(delay)
    raise RuntimeError("Factor download retry loop ended unexpectedly")


def _save_bytes(body: bytes, path) -> None:
    with atomic_target(path) as temporary:
        temporary.write_bytes(body)


def download_factors(settings: Settings) -> dict:
    """Re-fetch both full releases; preserve immutable source snapshots and metadata."""
    validate_phase2_paths(settings)
    manifest_path = settings.path("factor_manifest_path")
    with pipeline_lock(manifest_path.parent / ".factors.lock"):
        run_id = uuid.uuid4().hex
        downloaded_at = pd.Timestamp.now(tz="UTC").isoformat()
        snapshot = settings.path("factor_raw_data_path") / "snapshots" / run_id
        snapshot.mkdir(parents=True, exist_ok=False)
        manifest = {"run_id": run_id, "status": "downloading", "downloaded_at": downloaded_at,
                    "provider": "Kenneth R. French Data Library", "schema_version": "1.0.0",
                    "package_version": __version__, "data_version": "See exact source headers, HTTP metadata, and SHA-256 hashes",
                    "source_units": "percent per daily observation", "processed_units": "decimal daily returns",
                    "sources": {}, "dependencies": {name: version(name) for name in ["pandas", "numpy", "pyarrow"]},
                    "limitations": ["Historical releases can be revised after CRSP corrections and methodology changes.",
                                    "An archived current historical release is not a complete point-in-time database.",
                                    "NYSE calendar verification begins in July 1963; earlier source dates are retained without modern-weekmask rejection."]}
        source_frames = {}
        try:
            for dataset, url in [("ff5", settings.ff5_url), ("momentum", settings.momentum_url)]:
                body, http_metadata = fetch_official_zip(url, settings)
                csv_body, member = extract_csv(body)
                archive_path = snapshot / f"{dataset}_daily.zip"
                csv_path = snapshot / f"{dataset}_daily.csv"
                _save_bytes(body, archive_path)
                _save_bytes(csv_body, csv_path)
                frame, notes = parse_daily_csv(csv_body, dataset)
                quality = validate_factor_data(frame)
                manifest["sources"][dataset] = {"url": url, "downloaded_at": downloaded_at,
                    "zip_sha256": file_hash(archive_path), "csv_sha256": file_hash(csv_path),
                    "archive_path": str(archive_path.relative_to(settings.root)),
                    "csv_snapshot_path": str(csv_path.relative_to(settings.root)), "zip_member": member,
                    "source_notes": notes, "http_metadata": http_metadata, "quality": quality}
                if not quality["valid"]:
                    raise ValueError(f"{dataset} official source failed validation: {quality['errors']}")
                source_frames[dataset] = frame
                LOGGER.info("%s: %d daily observations, %s through %s", dataset, len(frame), frame.index.min().date(), frame.index.max().date())
            combined, alignment = combine_factors(source_frames["ff5"], source_frames["momentum"])
            output = settings.path("factor_data_path")
            old = pd.read_parquet(output) if output.exists() else None
            manifest["revisions"] = revision_summary(old, combined)
            manifest["alignment"] = alignment
            manifest["complete_start_date"] = alignment["complete_start_date"]
            manifest["complete_end_date"] = alignment["complete_end_date"]
            manifest["status"] = "running"
            atomic_json(manifest, manifest_path)
            for dataset in source_frames:
                source = snapshot / f"{dataset}_daily.csv"
                _save_bytes(source.read_bytes(), settings.path("factor_raw_data_path") / f"{dataset}_daily.csv")
            atomic_parquet(combined, output, index=True)
            manifest["processed_path"] = str(output.relative_to(settings.root))
            manifest["processed_sha256"] = file_hash(output)
            manifest["status"] = "complete"
            manifest["completed_at"] = pd.Timestamp.now(tz="UTC").isoformat()
            atomic_json(manifest, snapshot / "manifest.json")
            atomic_json(manifest, manifest_path)
            atomic_json({"status": "complete", "run_id": run_id}, manifest_path.parent / "factor_last_attempt.json")
            return manifest
        except Exception as error:
            manifest["status"] = "failed"
            manifest["error"] = f"{type(error).__name__}: {error}"
            atomic_json(manifest, snapshot / "manifest.json")
            atomic_json(manifest, manifest_path.parent / "factor_last_attempt.json")
            # A failed attempt before publication leaves a previous complete snapshot usable.
            if manifest_path.exists():
                current = json.loads(manifest_path.read_text())
                if current.get("run_id") == run_id:
                    atomic_json(manifest, manifest_path)
            raise
