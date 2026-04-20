from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping
import argparse
import json
import os
import socket

from leadlag.runtime.host_checks import (
    file_sha256,
    git_status_lines,
    python_version_status,
    required_directory_checks,
    runtime_flag_status,
    tracked_secret_files,
    timezone_status,
)
from leadlag.security import (
    DuplicateKeyError,
    RuntimeSecurityConfigError,
    collect_sensitive_values,
    load_execution_host_config,
    load_runtime_security_policy,
    load_secrets_inventory,
    redact_value,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
REPORT_FILENAMES = [
    "runtime_safety_report.json",
    "runtime_safety_report.md",
    "redacted_environment_snapshot.json",
]
BACKUP_DOCS = [
    "docs/security_and_host_policy_v1.md",
    "docs/execution_host_setup_v1.md",
]


@dataclass(slots=True)
class RuntimeSafetyIssue:
    severity: str
    code: str
    message: str
    details: dict[str, Any] | None = None


@dataclass(slots=True)
class RuntimeSafetyResult:
    status: str
    passed: bool
    issues: list[RuntimeSafetyIssue] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    output_paths: dict[str, str] = field(default_factory=dict)

    def issue_counts(self) -> dict[str, int]:
        counts = {"ERROR": 0, "WARN": 0, "INFO": 0}
        for issue in self.issues:
            counts[issue.severity] = counts.get(issue.severity, 0) + 1
        return counts


def _parse_env_example(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _is_sensitive_env_key(name: str, patterns: list[str], inventory_names: set[str]) -> bool:
    lowered = name.lower()
    return name in inventory_names or any(pattern.lower() in lowered for pattern in patterns)


def _build_environment_snapshot(
    prefixes: list[str],
    env: Mapping[str, str],
    *,
    repo_root: Path,
    timezone_info: dict[str, Any],
    python_info: dict[str, Any],
    kill_switch: dict[str, Any],
    trading_disabled: dict[str, Any],
) -> dict[str, Any]:
    captured = {
        key: value
        for key, value in env.items()
        if any(key.startswith(prefix) for prefix in prefixes)
    }
    return {
        "environment": captured,
        "host": {
            "hostname": socket.gethostname(),
            "repo_root": str(repo_root),
            "current_working_directory": str(Path.cwd()),
            "python_version": python_info.get("current_version"),
            "python_executable": python_info.get("python_executable"),
            "local_time": timezone_info.get("local_time"),
            "local_timezone_name": timezone_info.get("local_timezone_name"),
            "local_utc_offset": timezone_info.get("local_utc_offset"),
        },
        "runtime_flags": {
            "kill_switch": kill_switch,
            "trading_disabled": trading_disabled,
        },
    }


def _status_from_issues(issues: list[RuntimeSafetyIssue]) -> str:
    if any(issue.severity == "ERROR" for issue in issues):
        return "FAIL"
    if any(issue.severity == "WARN" for issue in issues):
        return "WARN"
    return "PASS"


def _report_payload(
    *,
    status: str,
    issues: list[RuntimeSafetyIssue],
    summary: dict[str, Any],
    output_paths: dict[str, str],
) -> dict[str, Any]:
    counts = {"ERROR": 0, "WARN": 0, "INFO": 0}
    for issue in issues:
        counts[issue.severity] = counts.get(issue.severity, 0) + 1
    return {
        "status": status,
        "passed": status != "FAIL",
        "issue_counts": counts,
        "issues": [asdict(issue) for issue in issues],
        "summary": summary,
        "output_paths": output_paths,
    }


def _build_markdown_report(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    issue_counts = payload["issue_counts"]
    config_files = summary.get("config_files", {})
    timezone_summary = summary.get("timezone", {})
    python_summary = summary.get("python_version", {})
    git_summary = summary.get("git", {})
    forbidden_summary = summary.get("forbidden_secret_files", {})
    kill_switch_summary = summary.get("kill_switch", {})
    trading_disabled_summary = summary.get("trading_disabled", {})
    lines = [
        "# Runtime Safety Report",
        "",
        f"- status: `{payload['status']}`",
        f"- errors: `{issue_counts.get('ERROR', 0)}`",
        f"- warnings: `{issue_counts.get('WARN', 0)}`",
        f"- infos: `{issue_counts.get('INFO', 0)}`",
        "",
        "## Configs",
        "",
    ]
    for label, item in summary.get("config_files", {}).items():
        lines.append(f"- {label}: `{item['path']}` sha256=`{item['sha256']}`")
    lines.extend(
        [
            "",
            "## Host Checks",
            "",
            f"- timezone expected: `{timezone_summary.get('expected_timezone')}`",
            f"- timezone detected: `{timezone_summary.get('local_timezone_name')}`",
            f"- timezone match: `{timezone_summary.get('matches_expected')}`",
            f"- python version file exists: `{python_summary.get('exists')}`",
            f"- python current version: `{python_summary.get('current_version')}`",
            f"- git dirty: `{git_summary.get('dirty')}`",
            f"- tracked secret files: `{forbidden_summary.get('tracked_files')}`",
            "",
            "## Runtime Flags",
            "",
            f"- kill switch file exists: `{kill_switch_summary.get('exists')}`",
            f"- trading disabled file exists: `{trading_disabled_summary.get('exists')}`",
            "",
            "## Directory Checks",
            "",
        ]
    )
    if not summary.get("directory_checks"):
        lines.append("- No directory checks recorded.")
    for item in summary.get("directory_checks", []):
        lines.append(f"- `{item['relative_path']}` exists=`{item['exists']}` is_dir=`{item['is_dir']}`")
    lines.extend(["", "## Issues", ""])
    if payload["issues"]:
        for issue in payload["issues"]:
            lines.append(f"- `{issue['severity']}` `{issue['code']}`: {issue['message']}")
    else:
        lines.append("- No issues detected.")
    lines.extend(
        [
            "",
            "## Output Paths",
            "",
        ]
    )
    for key, value in payload["output_paths"].items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    return "\n".join(lines)


def _collect_leak_candidates(
    raw_snapshot: dict[str, Any],
    env_example: dict[str, str],
    patterns: list[str],
    inventory_names: set[str],
    replacement: str,
) -> set[str]:
    candidates = {
        value
        for key, value in env_example.items()
        if value and _is_sensitive_env_key(key, patterns, inventory_names)
    }
    for item in collect_sensitive_values(raw_snapshot, patterns):
        if item and item != replacement:
            candidates.add(item)
    return {item for item in candidates if item and item != replacement}


def _find_unredacted_candidates(output_paths: list[Path], candidates: set[str]) -> list[str]:
    leaked: list[str] = []
    for path in output_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for candidate in candidates:
            if candidate and candidate in text:
                leaked.append(f"{path.name}:{candidate}")
    return leaked


def run_runtime_safety_check(
    security_config: Path | str,
    secrets_inventory: Path | str,
    host_config: Path | str,
    output_dir: Path | str,
    *,
    repo_root: Path | str | None = None,
    environment: Mapping[str, str] | None = None,
) -> RuntimeSafetyResult:
    repo_path = Path(repo_root).resolve() if repo_root is not None else REPO_ROOT
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    output_paths = {
        "runtime_safety_report_json": str((out_dir / "runtime_safety_report.json").resolve()),
        "runtime_safety_report_md": str((out_dir / "runtime_safety_report.md").resolve()),
        "redacted_environment_snapshot_json": str((out_dir / "redacted_environment_snapshot.json").resolve()),
    }
    issues: list[RuntimeSafetyIssue] = []

    try:
        policy = load_runtime_security_policy(security_config)
        inventory = load_secrets_inventory(secrets_inventory)
        host = load_execution_host_config(host_config)
    except DuplicateKeyError as exc:
        issues.append(RuntimeSafetyIssue("ERROR", "duplicate_yaml_key", str(exc)))
        status = _status_from_issues(issues)
        result = RuntimeSafetyResult(status=status, passed=False, issues=issues, summary={}, output_paths=output_paths)
        payload = _report_payload(status=status, issues=issues, summary=result.summary, output_paths=output_paths)
        Path(output_paths["runtime_safety_report_json"]).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        Path(output_paths["runtime_safety_report_md"]).write_text(_build_markdown_report(payload), encoding="utf-8")
        return result
    except RuntimeSecurityConfigError as exc:
        issues.append(RuntimeSafetyIssue("ERROR", "config_load_failed", str(exc)))
        status = _status_from_issues(issues)
        result = RuntimeSafetyResult(status=status, passed=False, issues=issues, summary={}, output_paths=output_paths)
        payload = _report_payload(status=status, issues=issues, summary=result.summary, output_paths=output_paths)
        Path(output_paths["runtime_safety_report_json"]).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        Path(output_paths["runtime_safety_report_md"]).write_text(_build_markdown_report(payload), encoding="utf-8")
        return result

    patterns = list(policy["secret_redaction"]["redact_patterns"])
    replacement = str(policy["secret_redaction"]["replacement"])
    inventory_names = {entry["name"] for entry in inventory["secrets"]}

    env_source = dict(environment or os.environ)
    env_example_path = repo_path / ".env.example"
    env_example: dict[str, str] = {}
    if not env_example_path.exists():
        issues.append(
            RuntimeSafetyIssue(
                "ERROR",
                "missing_env_example",
                ".env.example is required for placeholder-only secret handling.",
                details={"path": str(env_example_path)},
            )
        )
    else:
        env_example = _parse_env_example(env_example_path)
        unsafe_example_keys = [
            key
            for key, value in env_example.items()
            if value and _is_sensitive_env_key(key, patterns, inventory_names)
        ]
        if unsafe_example_keys:
            issues.append(
                RuntimeSafetyIssue(
                    "ERROR",
                    "unsafe_env_example_value",
                    ".env.example contains non-empty secret-like placeholder values.",
                    details={"keys": sorted(unsafe_example_keys)},
                )
            )

    directory_rows = required_directory_checks(repo_path, list(host["expected"]["required_directories"]))
    for row in directory_rows:
        if not row["exists"] or not row["is_dir"]:
            issues.append(
                RuntimeSafetyIssue(
                    "WARN",
                    "missing_required_directory",
                    f"Required directory is missing or not a directory: {row['relative_path']}",
                    details={"path": row["path"]},
                )
            )

    timezone_info = timezone_status(str(host["expected"]["timezone"]))
    if not timezone_info.get("matches_expected", False):
        issues.append(
            RuntimeSafetyIssue(
                "WARN",
                "timezone_mismatch",
                "Local timezone does not match the expected Asia/Tokyo operating timezone.",
                details={
                    "expected_timezone": timezone_info.get("expected_timezone"),
                    "local_timezone_name": timezone_info.get("local_timezone_name"),
                    "local_utc_offset": timezone_info.get("local_utc_offset"),
                },
            )
        )

    python_info = python_version_status(repo_path, str(host["expected"]["python_version_file"]))
    if not python_info["exists"]:
        issues.append(
            RuntimeSafetyIssue(
                "WARN",
                "missing_python_version_file",
                "The configured python version file is missing.",
                details={"path": python_info["path"]},
            )
        )

    tracked_files = tracked_secret_files(
        repo_path,
        list(policy["forbidden_secret_files"])
        + [
            str(policy["runtime_flags"]["kill_switch_file"]),
            str(policy["runtime_flags"]["trading_disabled_file"]),
        ],
    )
    if tracked_files["files"]:
        issues.append(
            RuntimeSafetyIssue(
                "ERROR",
                "tracked_secret_file",
                "Tracked local secret or control files were detected in git.",
                details={"files": tracked_files["files"]},
            )
        )

    git_state = git_status_lines(repo_path)
    if git_state["dirty"]:
        issues.append(
            RuntimeSafetyIssue(
                "WARN",
                "git_dirty_state",
                "Git worktree is dirty.",
                details={"lines": git_state["lines"]},
            )
        )

    kill_switch = runtime_flag_status(repo_path, str(policy["runtime_flags"]["kill_switch_file"]))
    trading_disabled = runtime_flag_status(repo_path, str(policy["runtime_flags"]["trading_disabled_file"]))

    if policy["backups"]["require_daily_artifact_backup_plan"] or policy["backups"]["require_restore_test_plan"]:
        missing_docs = [
            relative
            for relative in BACKUP_DOCS
            if not (repo_path / relative).exists()
        ]
        if missing_docs:
            issues.append(
                RuntimeSafetyIssue(
                    "WARN",
                    "backup_docs_missing",
                    "Backup or restore guidance docs are missing.",
                    details={"missing_docs": missing_docs},
                )
            )

    raw_snapshot = _build_environment_snapshot(
        list(policy["environment_snapshot_prefixes"]),
        env_source,
        repo_root=repo_path,
        timezone_info=timezone_info,
        python_info=python_info,
        kill_switch=kill_switch,
        trading_disabled=trading_disabled,
    )
    redacted_snapshot = redact_value(raw_snapshot, patterns, replacement)
    snapshot_path = Path(output_paths["redacted_environment_snapshot_json"])
    snapshot_path.write_text(json.dumps(redacted_snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    config_files = {
        "security_config": {
            "path": policy["_config_path"],
            "sha256": file_sha256(Path(policy["_config_path"])),
        },
        "secrets_inventory": {
            "path": inventory["_config_path"],
            "sha256": file_sha256(Path(inventory["_config_path"])),
        },
        "host_config": {
            "path": host["_config_path"],
            "sha256": file_sha256(Path(host["_config_path"])),
        },
    }
    summary = {
        "config_files": config_files,
        "directory_checks": directory_rows,
        "kill_switch": kill_switch,
        "trading_disabled": trading_disabled,
        "forbidden_secret_files": {
            "patterns": list(policy["forbidden_secret_files"]),
            "tracked_files": tracked_files["files"],
        },
        "python_version": python_info,
        "timezone": timezone_info,
        "git": {
            "dirty": git_state["dirty"],
            "status_lines": git_state["lines"],
        },
        "environment_snapshot_path": str(snapshot_path),
        "env_example_path": str(env_example_path),
    }

    leak_candidates = _collect_leak_candidates(raw_snapshot, env_example, patterns, inventory_names, replacement)
    initial_status = _status_from_issues(issues)
    initial_payload = _report_payload(
        status=initial_status,
        issues=issues,
        summary=summary,
        output_paths=output_paths,
    )
    Path(output_paths["runtime_safety_report_json"]).write_text(
        json.dumps(initial_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    Path(output_paths["runtime_safety_report_md"]).write_text(
        _build_markdown_report(initial_payload),
        encoding="utf-8",
    )

    leaked = _find_unredacted_candidates(
        [Path(output_paths["runtime_safety_report_json"]), Path(output_paths["runtime_safety_report_md"]), snapshot_path],
        leak_candidates,
    )
    if leaked:
        issues.append(
            RuntimeSafetyIssue(
                "ERROR",
                "unredacted_secret_value_in_output",
                "Generated runtime safety artifacts contain unredacted secret-like values.",
                details={"matches": leaked},
            )
        )

    status = _status_from_issues(issues)
    payload = _report_payload(status=status, issues=issues, summary=summary, output_paths=output_paths)
    Path(output_paths["runtime_safety_report_json"]).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    Path(output_paths["runtime_safety_report_md"]).write_text(
        _build_markdown_report(payload),
        encoding="utf-8",
    )

    return RuntimeSafetyResult(
        status=status,
        passed=status != "FAIL",
        issues=issues,
        summary=summary,
        output_paths=output_paths,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run runtime safety and host-preparation checks.")
    parser.add_argument("--security-config", required=True, help="Runtime security policy YAML.")
    parser.add_argument("--secrets-inventory", required=True, help="Secrets inventory YAML.")
    parser.add_argument("--host-config", required=True, help="Execution host config YAML.")
    parser.add_argument("--output-dir", required=True, help="Directory for runtime safety artifacts.")
    args = parser.parse_args(argv)

    result = run_runtime_safety_check(
        security_config=args.security_config,
        secrets_inventory=args.secrets_inventory,
        host_config=args.host_config,
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {
                "status": result.status,
                "passed": result.passed,
                "issue_counts": result.issue_counts(),
                "summary": result.summary,
                "output_paths": result.output_paths,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.status != "FAIL" else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
