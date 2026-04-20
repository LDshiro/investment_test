from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import json
import os
import platform
import shutil
import subprocess
import sys
from typing import Any

from baseline_common import (
    ARTIFACT_ROOT_REL,
    AUXILIARY_PROFILES,
    BASELINE_BRANCH,
    BASELINE_NAME,
    BASELINE_TAG,
    CANONICAL_PROFILES,
    DATA_FILE_MAP,
    OPTIONAL_DATA_FILES,
    REQUIRED_ARTIFACT_FILES,
    file_record,
    read_json,
    render_command,
    sha256_bytes,
    sha256_file,
    utc_now_iso,
    write_json,
    write_sha256_manifest,
    write_text,
)


ENV_FLAG = "LEADLAG_BASELINE_IN_VENV"


@dataclass
class CommandResult:
    name: str
    requested_command: str
    actual_command: str
    substitution_note: str | None
    exit_code: int
    stdout_path: str
    stderr_path: str
    output_artifacts: list[str]
    resolved_output_path: str | None = None

    def to_manifest(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "requested_command": self.requested_command,
            "actual_command": self.actual_command,
            "substitution_note": self.substitution_note,
            "exit_code": self.exit_code,
            "stdout_path": self.stdout_path,
            "stderr_path": self.stderr_path,
            "resolved_output_path": self.resolved_output_path,
            "output_artifacts": self.output_artifacts,
        }


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def venv_python(repo: Path) -> Path:
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    exe_name = "python.exe" if os.name == "nt" else "python"
    return repo / ".venv" / scripts_dir / exe_name


def ensure_venv_ready(repo: Path) -> Path:
    py = venv_python(repo)
    if not py.exists():
        subprocess.run([sys.executable, "-m", "venv", str(repo / ".venv")], cwd=repo, check=True)

    probe = subprocess.run(
        [
            str(py),
            "-c",
            "import leadlag, pytest, yaml, pydantic, tabulate; print('ok')",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        subprocess.run([str(py), "-m", "pip", "install", "-e", ".[dev]"], cwd=repo, check=True)
    return py


def reexec_into_venv_if_needed(argv: list[str]) -> int | None:
    repo = repo_root()
    py = ensure_venv_ready(repo)
    current = Path(sys.executable).resolve()
    if os.environ.get(ENV_FLAG) == "1" and current == py.resolve():
        return None
    env = os.environ.copy()
    env[ENV_FLAG] = "1"
    proc = subprocess.run([str(py), str(Path(__file__).resolve()), *argv], cwd=repo, env=env)
    return proc.returncode


def parse_json_from_output(text: str) -> dict[str, Any]:
    start = text.find("{")
    if start == -1:
        raise ValueError("JSON payload not found in command output")
    return json.loads(text[start:])


def import_runtime_helpers() -> tuple[Any, Any]:
    from leadlag.config.loader import load_app_config
    from leadlag.reporting.weekly_rules import load_rules_config

    return load_app_config, load_rules_config


def collect_git_metadata(repo: Path) -> dict[str, Any]:
    git = {
        "available": False,
        "requested_branch": BASELINE_BRANCH,
        "requested_tag": BASELINE_TAG,
        "commit": None,
        "branch": None,
        "dirty": None,
        "tag_target": None,
        "reason": None,
    }
    probe = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        git["reason"] = (probe.stderr or probe.stdout or "git unavailable").strip()
        return git

    git["available"] = True
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=repo, capture_output=True, text=True)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True)
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True)
    git.update(
        {
            "branch": branch.stdout.strip() or None,
            "commit": commit.stdout.strip() or None,
            "dirty": bool(dirty.stdout.strip()),
            "tag_target": None,
        }
    )
    return git


def collect_config_hashes(repo: Path) -> dict[str, Any]:
    load_app_config, load_rules_config = import_runtime_helpers()
    entries: list[dict[str, Any]] = []

    def resolved_hash_for(path: Path) -> tuple[str, str]:
        if path.name == "weekly_rules_shadow_default.yaml":
            payload = load_rules_config(path)
            return "ok", sha256_bytes(
                json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
            )
        cfg = load_app_config(path)
        payload = cfg.model_dump(mode="json") if hasattr(cfg, "model_dump") else cfg.dict()  # type: ignore[attr-defined]
        return "ok", sha256_bytes(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        )

    for rel in CANONICAL_PROFILES + AUXILIARY_PROFILES:
        path = repo / rel
        record = {
            "path": rel,
            "class": "rules_config" if path.name.startswith("weekly_rules_") else "app_config",
            "exists": path.exists(),
            "raw_sha256": sha256_file(path) if path.exists() else None,
            "load_status": "missing",
            "resolved_config_hash": None,
            "canonical": rel in CANONICAL_PROFILES,
        }
        if path.exists():
            try:
                load_status, resolved_hash = resolved_hash_for(path)
                record["load_status"] = load_status
                record["resolved_config_hash"] = resolved_hash
            except Exception as exc:  # pragma: no cover - defensive runtime path
                record["load_status"] = f"error:{type(exc).__name__}:{exc}"
        entries.append(record)

    payload = {
        "baseline_name": BASELINE_NAME,
        "generated_at_utc": utc_now_iso(),
        "entries": entries,
    }
    return payload


def collect_data_hashes(repo: Path) -> dict[str, Any]:
    data_root = repo / "data" / "normalized" / "corrected_bundle"
    entries: list[dict[str, Any]] = []
    for key, filename in DATA_FILE_MAP.items():
        record = file_record(data_root / filename, root=repo)
        record["key"] = key
        entries.append(record)

    optional: list[dict[str, Any]] = []
    for key, filename in OPTIONAL_DATA_FILES.items():
        record = file_record(data_root / filename, root=repo)
        record["key"] = key
        optional.append(record)

    return {
        "baseline_name": BASELINE_NAME,
        "generated_at_utc": utc_now_iso(),
        "data_root": data_root.relative_to(repo).as_posix(),
        "entries": entries,
        "optional_entries": optional,
    }


def run_and_record_command(
    *,
    name: str,
    requested_command: str,
    args: list[str],
    output_dir: Path,
    substitution_note: str | None = None,
) -> CommandResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(args, cwd=repo_root(), capture_output=True, text=True)
    stdout_path = output_dir / "stdout.txt"
    stderr_path = output_dir / "stderr.txt"
    stdout_path.write_text(proc.stdout, encoding="utf-8")
    stderr_path.write_text(proc.stderr, encoding="utf-8")
    return CommandResult(
        name=name,
        requested_command=requested_command,
        actual_command=render_command(args),
        substitution_note=substitution_note,
        exit_code=proc.returncode,
        stdout_path=stdout_path.relative_to(repo_root()).as_posix(),
        stderr_path=stderr_path.relative_to(repo_root()).as_posix(),
        output_artifacts=[],
    )


def expected_baseline_exists(artifact_root: Path) -> bool:
    return all((artifact_root / rel).exists() for rel in REQUIRED_ARTIFACT_FILES) and (artifact_root / "reference_results").exists()


def write_reference_commands_md(path: Path, results: list[CommandResult]) -> None:
    lines = ["# Reference Commands", ""]
    lines.append("| name | requested command | actual command | substitution note | exit code | output artifacts |")
    lines.append("|---|---|---|---|---:|---|")
    for result in results:
        outputs = ", ".join(f"`{item}`" for item in result.output_artifacts) if result.output_artifacts else ""
        lines.append(
            f"| {result.name} | `{result.requested_command}` | `{result.actual_command}` | {result.substitution_note or ''} | {result.exit_code} | {outputs} |"
        )
    write_text(path, "\n".join(lines) + "\n")


def build_manifest_md(manifest: dict[str, Any]) -> str:
    lines = [f"# {manifest['baseline_name']}", ""]
    lines.append(f"- created_at_utc: `{manifest['created_at_utc']}`")
    lines.append(f"- requested branch: `{manifest['git']['requested_branch']}`")
    lines.append(f"- requested tag: `{manifest['git']['requested_tag']}`")
    lines.append(f"- git available: `{manifest['git']['available']}`")
    lines.append(f"- dependency snapshot: `{manifest['environment']['dependency_snapshot']}`")
    lines.append("")
    lines.append("## Acceptance Checks")
    lines.append("")
    for item in manifest["acceptance_checks"]:
        lines.append(f"- {item['name']}: `{item['status']}`")
    lines.append("")
    lines.append("## Canonical Profiles")
    lines.append("")
    for item in manifest["canonical_profiles"]:
        lines.append(f"- `{item['path']}`")
    lines.append("")
    lines.append("## Data Hashes")
    lines.append("")
    for item in manifest["data_hashes"]["entries"]:
        lines.append(f"- `{item['path']}`: `{item['sha256']}`")
    if manifest["notes"]:
        lines.append("")
        lines.append("## Notes")
        lines.append("")
        for note in manifest["notes"]:
            lines.append(f"- {note}")
    return "\n".join(lines) + "\n"


def build_artifact_readme(manifest: dict[str, Any]) -> str:
    lines = [f"# {manifest['baseline_name']} artifacts", ""]
    lines.append("This directory is the frozen baseline artifact root for Step 01.")
    lines.append("")
    lines.append("## Contents")
    lines.append("")
    lines.append("- `baseline_manifest.json` / `baseline_manifest.md`: baseline metadata and summary")
    lines.append("- `config_hashes.json`: canonical and auxiliary config hashes")
    lines.append("- `data_hashes.json`: corrected-bundle file hashes")
    lines.append("- `reference_commands.md`: executed command log")
    lines.append("- `reference_results/`: frozen command outputs and copied summaries")
    lines.append("- `pip_freeze.txt`: dependency snapshot from the baseline venv")
    lines.append("- `sha256_manifest.txt`: SHA256 list for this artifact tree")
    lines.append("")
    lines.append("## Requested identifiers")
    lines.append("")
    lines.append(f"- branch label: `{BASELINE_BRANCH}`")
    lines.append(f"- tag label: `{BASELINE_TAG}`")
    return "\n".join(lines) + "\n"


def gather_previous_results(artifact_root: Path) -> list[CommandResult]:
    manifest_path = artifact_root / "baseline_manifest.json"
    if not manifest_path.exists():
        return []
    manifest = read_json(manifest_path)
    results: list[CommandResult] = []
    for item in manifest.get("reference_commands", []):
        results.append(
            CommandResult(
                name=item["name"],
                requested_command=item["requested_command"],
                actual_command=item["actual_command"],
                substitution_note=item.get("substitution_note"),
                exit_code=item["exit_code"],
                stdout_path=item["stdout_path"],
                stderr_path=item["stderr_path"],
                resolved_output_path=item.get("resolved_output_path"),
                output_artifacts=list(item.get("output_artifacts", [])),
            )
        )
    return results


def build_acceptance_checks(
    *,
    artifact_root: Path,
    command_results: list[CommandResult],
    config_hashes: dict[str, Any],
    data_hashes: dict[str, Any],
) -> list[dict[str, str]]:
    result_map = {item.name: item for item in command_results}

    def status(ok: bool, name: str) -> dict[str, str]:
        return {"name": name, "status": "pass" if ok else "fail"}

    checks = [
        status(result_map.get("tests", CommandResult("", "", "", None, 1, "", "", [])).exit_code == 0, "tests pass"),
        status(result_map.get("inspect_bundle", CommandResult("", "", "", None, 1, "", "", [])).exit_code == 0, "corrected bundle inspection succeeds"),
        status(result_map.get("historical_shadow", CommandResult("", "", "", None, 1, "", "", [])).exit_code == 0, "one historical shadow run succeeds"),
        status(result_map.get("batch_replay", CommandResult("", "", "", None, 1, "", "", [])).exit_code == 0, "one batch replay succeeds"),
        status(result_map.get("weekly_review", CommandResult("", "", "", None, 1, "", "", [])).exit_code == 0, "weekly review succeeds"),
        status(result_map.get("weekly_gates", CommandResult("", "", "", None, 1, "", "", [])).exit_code == 0, "weekly gates succeeds"),
        status(bool(config_hashes.get("entries")) and bool(data_hashes.get("entries")), "hashes recorded"),
        status(len(command_results) >= 6, "commands recorded"),
        status(expected_baseline_exists(artifact_root), "artifacts written under baseline root"),
    ]
    return checks


def ensure_success(result: CommandResult) -> None:
    if result.exit_code != 0:
        raise RuntimeError(f"{result.name} failed with exit code {result.exit_code}")


def execute_reference_commands(repo: Path, artifact_root: Path, py: Path) -> tuple[list[CommandResult], dict[str, Any]]:
    reference_root = artifact_root / "reference_results"
    results: list[CommandResult] = []
    artifacts: dict[str, Any] = {}

    tests = run_and_record_command(
        name="tests",
        requested_command=".venv/.../python -m pytest",
        args=[str(py), "-m", "pytest"],
        output_dir=reference_root / "tests",
    )
    tests.output_artifacts = [tests.stdout_path, tests.stderr_path]
    results.append(tests)
    ensure_success(tests)
    artifacts["tests"] = {
        "stdout": tests.stdout_path,
        "stderr": tests.stderr_path,
    }

    inspect = run_and_record_command(
        name="inspect_bundle",
        requested_command=".venv/.../python -m leadlag.cli inspect-bundle --config configs/profiles/backtest_corrected.yaml",
        args=[str(py), "-m", "leadlag.cli", "inspect-bundle", "--config", "configs/profiles/backtest_corrected.yaml"],
        output_dir=reference_root / "inspect_bundle",
        substitution_note="Executed with configs/profiles/backtest_corrected.yaml because backtest_corrected_local.yaml points to /mnt/data in this workspace.",
    )
    ensure_success(inspect)
    inspect_summary = parse_json_from_output((repo / inspect.stdout_path).read_text(encoding="utf-8"))
    summary_path = reference_root / "inspect_bundle" / "summary.json"
    write_json(summary_path, inspect_summary)
    inspect.output_artifacts = [
        summary_path.relative_to(repo).as_posix(),
        inspect.stdout_path,
        inspect.stderr_path,
    ]
    results.append(inspect)
    artifacts["inspect_bundle"] = {
        "summary_json": summary_path.relative_to(repo).as_posix(),
    }

    shadow = run_and_record_command(
        name="historical_shadow",
        requested_command=".venv/.../python -m leadlag.cli run --config configs/profiles/shadow_corrected_local.yaml",
        args=[str(py), "-m", "leadlag.cli", "run", "--config", "configs/profiles/shadow_corrected_local.yaml"],
        output_dir=reference_root / "shadow_run",
    )
    ensure_success(shadow)
    shadow_status = parse_json_from_output((repo / shadow.stdout_path).read_text(encoding="utf-8"))
    packet_dir = Path(shadow_status["packet_dir"])
    copied_packet_dir = reference_root / "shadow_run" / "packet"
    shutil.copytree(packet_dir, copied_packet_dir, dirs_exist_ok=True)
    write_text(reference_root / "shadow_run" / "resolved_packet_dir.txt", str(packet_dir.resolve()) + "\n")
    shadow.output_artifacts = [
        (reference_root / "shadow_run" / "resolved_packet_dir.txt").relative_to(repo).as_posix(),
        copied_packet_dir.relative_to(repo).as_posix(),
        shadow.stdout_path,
        shadow.stderr_path,
    ]
    shadow.resolved_output_path = str(packet_dir.resolve())
    results.append(shadow)
    artifacts["historical_shadow"] = {
        "source_packet_dir": str(packet_dir.resolve()),
        "copied_packet_dir": copied_packet_dir.relative_to(repo).as_posix(),
    }

    batch = run_and_record_command(
        name="batch_replay",
        requested_command=".venv/.../python -m leadlag.cli run-batch --config configs/profiles/shadow_corrected_batch_local.yaml",
        args=[str(py), "-m", "leadlag.cli", "run-batch", "--config", "configs/profiles/shadow_corrected_batch_local.yaml"],
        output_dir=reference_root / "batch_replay",
    )
    ensure_success(batch)
    batch_status = parse_json_from_output((repo / batch.stdout_path).read_text(encoding="utf-8"))
    batch_dir = Path(batch_status["batch_dir"])
    copied_batch_files: list[str] = []
    for name in ("batch_summary.csv", "batch_summary.json", "batch_summary.md"):
        src = batch_dir / name
        dst = reference_root / "batch_replay" / name
        if src.exists():
            shutil.copy2(src, dst)
            copied_batch_files.append(dst.relative_to(repo).as_posix())
    write_text(reference_root / "batch_replay" / "resolved_batch_dir.txt", str(batch_dir.resolve()) + "\n")
    copied_batch_files.append((reference_root / "batch_replay" / "resolved_batch_dir.txt").relative_to(repo).as_posix())
    batch.output_artifacts = copied_batch_files + [batch.stdout_path, batch.stderr_path]
    batch.resolved_output_path = str(batch_dir.resolve())
    results.append(batch)
    artifacts["batch_replay"] = {
        "source_batch_dir": str(batch_dir.resolve()),
        "copied_files": copied_batch_files,
    }

    review_out = artifact_root / "reference_results" / "weekly_review"
    weekly_review = run_and_record_command(
        name="weekly_review",
        requested_command=".venv/.../python -m leadlag.cli weekly-review --batch-dir <resolved_batch_dir> --output-dir artifacts/baseline_shadow_stack_v1/reference_results/weekly_review",
        args=[
            str(py),
            "-m",
            "leadlag.cli",
            "weekly-review",
            "--batch-dir",
            str(batch_dir),
            "--output-dir",
            str(review_out),
        ],
        output_dir=reference_root / "weekly_review_logs",
    )
    ensure_success(weekly_review)
    weekly_review_status = parse_json_from_output((repo / weekly_review.stdout_path).read_text(encoding="utf-8"))
    weekly_review.output_artifacts = [
        Path(weekly_review_status["daily_enriched_csv"]).relative_to(repo).as_posix(),
        Path(weekly_review_status["weekly_summary_csv"]).relative_to(repo).as_posix(),
        Path(weekly_review_status["weekly_summary_json"]).relative_to(repo).as_posix(),
        Path(weekly_review_status["weekly_summary_md"]).relative_to(repo).as_posix(),
        Path(weekly_review_status["weekly_nav_index_png"]).relative_to(repo).as_posix(),
        Path(weekly_review_status["weekly_status_counts_png"]).relative_to(repo).as_posix(),
        weekly_review.stdout_path,
        weekly_review.stderr_path,
    ]
    weekly_review.resolved_output_path = str(review_out.resolve())
    results.append(weekly_review)
    artifacts["weekly_review"] = weekly_review_status

    gates_out = artifact_root / "reference_results" / "weekly_gates"
    weekly_gates = run_and_record_command(
        name="weekly_gates",
        requested_command=".venv/.../python -m leadlag.cli weekly-gates --review-dir artifacts/baseline_shadow_stack_v1/reference_results/weekly_review --rules-config configs/review/weekly_rules_shadow_default.yaml --output-dir artifacts/baseline_shadow_stack_v1/reference_results/weekly_gates",
        args=[
            str(py),
            "-m",
            "leadlag.cli",
            "weekly-gates",
            "--review-dir",
            str(review_out),
            "--rules-config",
            "configs/review/weekly_rules_shadow_default.yaml",
            "--output-dir",
            str(gates_out),
        ],
        output_dir=reference_root / "weekly_gates_logs",
    )
    ensure_success(weekly_gates)
    weekly_gates_status = parse_json_from_output((repo / weekly_gates.stdout_path).read_text(encoding="utf-8"))
    weekly_gates.output_artifacts = [
        Path(weekly_gates_status["weekly_status_csv"]).relative_to(repo).as_posix(),
        Path(weekly_gates_status["weekly_status_json"]).relative_to(repo).as_posix(),
        Path(weekly_gates_status["promotion_assessment_json"]).relative_to(repo).as_posix(),
        Path(weekly_gates_status["promotion_assessment_md"]).relative_to(repo).as_posix(),
        weekly_gates.stdout_path,
        weekly_gates.stderr_path,
    ]
    weekly_gates.resolved_output_path = str(gates_out.resolve())
    results.append(weekly_gates)
    artifacts["weekly_gates"] = weekly_gates_status

    return results, artifacts


def write_manifest_bundle(
    *,
    repo: Path,
    artifact_root: Path,
    git_meta: dict[str, Any],
    config_hashes: dict[str, Any],
    data_hashes: dict[str, Any],
    command_results: list[CommandResult],
    reference_artifacts: dict[str, Any],
) -> dict[str, Any]:
    environment = {
        "python_version": sys.version.replace("\n", " "),
        "python_executable": str(Path(sys.executable).resolve()),
        "platform": platform.platform(),
        "cwd": str(repo.resolve()),
        "venv_path": str((repo / ".venv").resolve()),
        "dependency_snapshot": (artifact_root / "pip_freeze.txt").relative_to(repo).as_posix(),
    }

    notes = [
        f"Canonical baseline branch label: {BASELINE_BRANCH}",
        f"Canonical baseline tag label: {BASELINE_TAG}",
        "Inspect-bundle reference command uses configs/profiles/backtest_corrected.yaml because backtest_corrected_local.yaml is pinned to /mnt/data.",
    ]
    optional_patch = data_hashes.get("optional_entries", [])
    if optional_patch:
        patch_record = optional_patch[0]
        notes.append(
            "patch_table.csv present in corrected bundle."
            if patch_record.get("exists")
            else "patch_table.csv not present in corrected bundle."
        )

    manifest = {
        "baseline_name": BASELINE_NAME,
        "created_at_utc": utc_now_iso(),
        "git": git_meta,
        "environment": environment,
        "canonical_profiles": config_hashes["entries"][: len(CANONICAL_PROFILES)],
        "auxiliary_profiles": config_hashes["entries"][len(CANONICAL_PROFILES) :],
        "config_hashes": config_hashes,
        "data_hashes": data_hashes,
        "reference_commands": [item.to_manifest() for item in command_results],
        "reference_artifacts": reference_artifacts,
        "acceptance_checks": [],
        "notes": notes,
    }
    return manifest


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    reexec_code = reexec_into_venv_if_needed(argv)
    if reexec_code is not None:
        return reexec_code

    parser = argparse.ArgumentParser(description="Freeze the current repo baseline into artifacts/baseline_shadow_stack_v1.")
    parser.add_argument("--refresh", action="store_true", help="Re-run reference commands even if baseline artifacts already exist.")
    args = parser.parse_args(argv)

    repo = repo_root()
    py = venv_python(repo)
    artifact_root = repo / ARTIFACT_ROOT_REL
    artifact_root.mkdir(parents=True, exist_ok=True)
    reference_results = artifact_root / "reference_results"
    reference_results.mkdir(parents=True, exist_ok=True)

    pip_freeze = subprocess.run([str(py), "-m", "pip", "freeze"], cwd=repo, capture_output=True, text=True, check=True)
    write_text(artifact_root / "pip_freeze.txt", pip_freeze.stdout)

    config_hashes = collect_config_hashes(repo)
    data_hashes = collect_data_hashes(repo)
    write_json(artifact_root / "config_hashes.json", config_hashes)
    write_json(artifact_root / "data_hashes.json", data_hashes)

    git_meta = collect_git_metadata(repo)
    if args.refresh or not expected_baseline_exists(artifact_root):
        command_results, reference_artifacts = execute_reference_commands(repo, artifact_root, py)
    else:
        command_results = gather_previous_results(artifact_root)
        if not command_results:
            command_results, reference_artifacts = execute_reference_commands(repo, artifact_root, py)
        else:
            previous_manifest = read_json(artifact_root / "baseline_manifest.json")
            reference_artifacts = previous_manifest.get("reference_artifacts", {})

    manifest = write_manifest_bundle(
        repo=repo,
        artifact_root=artifact_root,
        git_meta=git_meta,
        config_hashes=config_hashes,
        data_hashes=data_hashes,
        command_results=command_results,
        reference_artifacts=reference_artifacts,
    )

    write_reference_commands_md(artifact_root / "reference_commands.md", command_results)
    write_text(artifact_root / "README.md", build_artifact_readme(manifest))
    write_text(artifact_root / "baseline_manifest.md", build_manifest_md(manifest))
    manifest["acceptance_checks"] = build_acceptance_checks(
        artifact_root=artifact_root,
        command_results=command_results,
        config_hashes=config_hashes,
        data_hashes=data_hashes,
    )
    write_text(artifact_root / "baseline_manifest.md", build_manifest_md(manifest))
    write_json(artifact_root / "baseline_manifest.json", manifest)
    write_sha256_manifest(artifact_root)
    manifest["acceptance_checks"] = build_acceptance_checks(
        artifact_root=artifact_root,
        command_results=command_results,
        config_hashes=config_hashes,
        data_hashes=data_hashes,
    )
    write_text(artifact_root / "baseline_manifest.md", build_manifest_md(manifest))
    write_json(artifact_root / "baseline_manifest.json", manifest)
    write_sha256_manifest(artifact_root)

    failed = [item for item in manifest["acceptance_checks"] if item["status"] != "pass"]
    print(f"baseline written: {artifact_root}")
    if failed:
        for item in failed:
            print(f"FAILED: {item['name']}")
        return 1
    print("acceptance checks: all pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
