from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
import subprocess
import sys


def file_sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def required_directory_checks(repo_root: Path, required_directories: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for relative in required_directories:
        path = (repo_root / relative).resolve(strict=False)
        rows.append(
            {
                "relative_path": relative,
                "path": str(path),
                "exists": path.exists(),
                "is_dir": path.is_dir(),
            }
        )
    return rows


def python_version_status(repo_root: Path, version_file: str) -> dict[str, Any]:
    path = (repo_root / version_file).resolve(strict=False)
    expected = path.read_text(encoding="utf-8").strip() if path.exists() else None
    return {
        "path": str(path),
        "exists": path.exists(),
        "expected_version": expected,
        "current_version": sys.version.split()[0],
        "python_executable": sys.executable,
    }


def timezone_status(expected_timezone: str) -> dict[str, Any]:
    now_local = datetime.now().astimezone()
    local_zone_name = getattr(now_local.tzinfo, "key", None) or str(now_local.tzinfo)
    info: dict[str, Any] = {
        "expected_timezone": expected_timezone,
        "local_timezone_name": local_zone_name,
        "local_time": now_local.isoformat(),
        "local_utc_offset": str(now_local.utcoffset()),
        "matches_expected": False,
    }
    try:
        expected_zone = ZoneInfo(expected_timezone)
        expected_now = datetime.now(expected_zone)
        info["expected_utc_offset"] = str(expected_now.utcoffset())
        info["matches_expected"] = now_local.utcoffset() == expected_now.utcoffset()
    except Exception as exc:  # pragma: no cover - defensive fallback
        info["expected_utc_offset"] = None
        info["error"] = repr(exc)
    return info


def git_status_lines(repo_root: Path) -> dict[str, Any]:
    proc = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    return {
        "available": proc.returncode == 0,
        "returncode": proc.returncode,
        "lines": lines,
        "stderr": proc.stderr.strip() or None,
        "dirty": bool(lines),
    }


def tracked_secret_files(repo_root: Path, patterns: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        ["git", "ls-files", "--", *patterns],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    files = [line for line in proc.stdout.splitlines() if line.strip()]
    return {
        "available": proc.returncode == 0,
        "returncode": proc.returncode,
        "files": files,
        "stderr": proc.stderr.strip() or None,
    }


def runtime_flag_status(repo_root: Path, relative_path: str) -> dict[str, Any]:
    path = (repo_root / relative_path).resolve(strict=False)
    return {
        "relative_path": relative_path,
        "path": str(path),
        "exists": path.exists(),
        "is_file": path.is_file(),
        "parent_exists": path.parent.exists(),
    }
