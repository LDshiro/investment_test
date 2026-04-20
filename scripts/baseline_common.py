from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import shlex
import subprocess
from typing import Any


BASELINE_NAME = "baseline_shadow_stack_v1"
BASELINE_BRANCH = "ops/step01-baseline-freeze"
BASELINE_TAG = "baseline-shadow-stack-v1"
ARTIFACT_ROOT_REL = Path("artifacts") / BASELINE_NAME

CANONICAL_PROFILES = [
    "configs/profiles/backtest_corrected_local.yaml",
    "configs/profiles/shadow_corrected_local.yaml",
    "configs/profiles/shadow_corrected_batch_local.yaml",
    "configs/profiles/shadow_corrected_batch_20d_local.yaml",
    "configs/review/weekly_rules_shadow_default.yaml",
]

AUXILIARY_PROFILES = [
    "configs/profiles/shadow_corrected_local_mntdata.yaml",
    "configs/profiles/shadow_corrected_batch_local_mntdata.yaml",
    "configs/profiles/shadow_corrected_batch_20d_local_mntdata.yaml",
]

DATA_FILE_MAP = {
    "returns_cc": "returns_cc.csv",
    "returns_oc_jp": "returns_oc_jp.csv",
    "close_prices_adj": "close_prices_adj.csv",
    "open_prices_adj": "open_prices_adj.csv",
    "common_dates_core": "common_dates_core.csv",
    "common_dates_full": "common_dates_full.csv",
    "ff3_japan_daily": "ff3_japan_daily.csv",
    "mom_japan_daily": "mom_japan_daily.csv",
    "carhart4_japan_daily": "carhart4_japan_daily.csv",
}

OPTIONAL_DATA_FILES = {
    "patch_table": "patch_table.csv",
}

REQUIRED_MANIFEST_KEYS = [
    "baseline_name",
    "created_at_utc",
    "git",
    "environment",
    "canonical_profiles",
    "auxiliary_profiles",
    "config_hashes",
    "data_hashes",
    "reference_commands",
    "reference_artifacts",
    "acceptance_checks",
    "notes",
]

REQUIRED_ARTIFACT_FILES = [
    "README.md",
    "baseline_manifest.json",
    "baseline_manifest.md",
    "config_hashes.json",
    "data_hashes.json",
    "reference_commands.md",
    "sha256_manifest.txt",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(blob: bytes) -> str:
    return sha256(blob).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def iso_utc_from_timestamp(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def render_command(args: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(args)
    return shlex.join(args)


def file_record(path: Path, *, root: Path | None = None) -> dict[str, Any]:
    exists = path.exists()
    record: dict[str, Any] = {
        "path": path.relative_to(root).as_posix() if root is not None else str(path),
        "exists": exists,
    }
    if exists:
        stat = path.stat()
        record.update(
            {
                "size_bytes": stat.st_size,
                "mtime_utc": iso_utc_from_timestamp(stat.st_mtime),
                "sha256": sha256_file(path),
            }
        )
    else:
        record.update(
            {
                "size_bytes": None,
                "mtime_utc": None,
                "sha256": None,
            }
        )
    return record


def build_sha256_manifest_lines(root: Path, *, exclude: set[str] | None = None) -> list[str]:
    exclude = set() if exclude is None else set(exclude)
    lines: list[str] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        if rel in exclude:
            continue
        lines.append(f"{sha256_file(path)}  {rel}")
    return lines


def write_sha256_manifest(root: Path) -> list[str]:
    rel = "sha256_manifest.txt"
    lines = build_sha256_manifest_lines(root, exclude={rel})
    write_text(root / rel, "\n".join(lines) + ("\n" if lines else ""))
    return lines
