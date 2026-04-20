from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
from typing import Any

from environment_common import (
    OPTIONAL_DEV_IMPORTS,
    RUNTIME_IMPORTS,
    SCRIPT_IMPORTS,
    artifact_root,
    baseline_python_version,
    choose_best_lock,
    current_python_version,
    display_venv_python,
    inside_virtualenv,
    overall_status,
    python_version_for_executable,
    python_version_matches,
    read_expected_python,
    repo_root,
    run_pip_freeze,
    target_python_for_verification,
    utc_now_iso,
    write_environment_sidecars,
)


def _python_check(python_exe: Path, code: str, repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(python_exe), "-c", code], cwd=repo, capture_output=True, text=True)


def _import_status(python_exe: Path, repo: Path, module_name: str, label: str) -> dict[str, Any]:
    proc = _python_check(python_exe, f"import {module_name}", repo)
    return {
        "name": label,
        "module": module_name,
        "status": "pass" if proc.returncode == 0 else "fail",
        "stderr": (proc.stderr or "").strip() or None,
    }


def _script_import_status(python_exe: Path, repo: Path, module_name: str) -> dict[str, Any]:
    code = (
        "from pathlib import Path; import sys; "
        f"sys.path.insert(0, str(Path(r'{str((repo / 'scripts').resolve())}'))); "
        f"import {module_name}"
    )
    proc = _python_check(python_exe, code, repo)
    return {
        "name": module_name,
        "module": module_name,
        "status": "pass" if proc.returncode == 0 else "fail",
        "stderr": (proc.stderr or "").strip() or None,
    }


def build_report_md(report: dict[str, Any]) -> str:
    lines = ["# Environment Verification", ""]
    lines.append(f"- generated_at_utc: `{report['generated_at_utc']}`")
    lines.append(f"- overall_status: `{report['overall_status']}`")
    lines.append(f"- expected_python: `{report['expected_python']}`")
    lines.append(f"- current_python: `{report['current_python']}`")
    lines.append(f"- verification_python: `{report['verification_python']}`")
    lines.append(f"- selected_lock: `{report['selected_lock'] or 'n/a'}`")
    lines.append("")
    if report["failures"]:
        lines.append("## Failures")
        lines.append("")
        for item in report["failures"]:
            lines.append(f"- {item}")
        lines.append("")
    if report["warnings"]:
        lines.append("## Warnings")
        lines.append("")
        for item in report["warnings"]:
            lines.append(f"- {item}")
        lines.append("")
    lines.append("## Lock Comparison")
    lines.append("")
    lines.append(f"- exact_match: `{report['lock_match_exact']}`")
    lines.append(f"- missing_count: `{len(report['lock_missing'])}`")
    lines.append(f"- extra_count: `{len(report['lock_extra'])}`")
    lines.append("")
    lines.append("## Import Checks")
    lines.append("")
    for item in report["imports"] + report["scripts"]:
        lines.append(f"- {item['name']}: `{item['status']}`")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the local reproducible execution environment.")
    parser.add_argument("--artifact-root", default=str(artifact_root(repo_root())), help="Where to write environment artifacts.")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    repo = repo_root()
    out = Path(args.artifact_root)
    out.mkdir(parents=True, exist_ok=True)

    expected_python = read_expected_python(repo)
    current_python = current_python_version()
    verification_python = target_python_for_verification(repo)
    verification_python_version = python_version_for_executable(verification_python)
    current_in_venv = inside_virtualenv()

    failures: list[str] = []
    warnings: list[str] = []

    if not current_in_venv:
        warnings.append(
            f"Current interpreter is not running inside a virtual environment; verification is using {verification_python}."
        )

    if not python_version_matches(verification_python_version, expected_python):
        failures.append(
            f"Verification interpreter version mismatch: expected {expected_python}, got {verification_python_version}."
        )

    baseline_version = baseline_python_version(repo)
    if baseline_version and not python_version_matches(baseline_version, expected_python):
        warnings.append(
            f"Baseline Python version {baseline_version} does not match current pin {expected_python}."
        )

    current_freeze_text, normalized_freeze = run_pip_freeze(verification_python, repo)
    selected_lock, comparisons = choose_best_lock(repo, normalized_freeze)
    if selected_lock is None:
        failures.append("No lock files found. Expected requirements.lock.txt and requirements-dev.lock.txt.")
        lock_match_exact = False
        lock_missing: list[str] = []
        lock_extra: list[str] = []
        selected_lock_path = None
    else:
        selected_lock_path = selected_lock.lock_path
        lock_match_exact = selected_lock.exact_match
        lock_missing = selected_lock.missing
        lock_extra = selected_lock.extra
        if not lock_match_exact:
            failures.append(f"Current pip freeze does not exactly match {selected_lock.lock_path}.")

    imports: list[dict[str, Any]] = []
    for module_name, label in RUNTIME_IMPORTS:
        status = _import_status(verification_python, repo, module_name, label)
        imports.append(status)
        if status["status"] != "pass":
            failures.append(f"Required import failed: {label}")

    optional_imports: list[dict[str, Any]] = []
    for module_name, label in OPTIONAL_DEV_IMPORTS:
        status = _import_status(verification_python, repo, module_name, label)
        optional_imports.append(status)
        if status["status"] != "pass":
            warnings.append(f"Optional dev import unavailable: {label}")

    leadlag_cli = _import_status(verification_python, repo, "leadlag.cli", "leadlag.cli")
    script_imports: list[dict[str, Any]] = [leadlag_cli]
    if leadlag_cli["status"] != "pass":
        failures.append("leadlag.cli could not be imported.")

    for module_name in SCRIPT_IMPORTS:
        status = _script_import_status(verification_python, repo, module_name)
        script_imports.append(status)
        if status["status"] != "pass":
            failures.append(f"Script module import failed: {module_name}")

    report = {
        "environment_name": "environment_repro_v1",
        "generated_at_utc": utc_now_iso(),
        "overall_status": overall_status(failures=failures, warnings=warnings),
        "expected_python": expected_python,
        "current_python": current_python,
        "verification_python": verification_python_version,
        "current_interpreter": str(Path(sys.executable).resolve(strict=False)),
        "verification_interpreter": str(verification_python.resolve(strict=False)),
        "inside_virtualenv": current_in_venv,
        "baseline_python": baseline_version,
        "selected_lock": selected_lock_path,
        "lock_match_exact": lock_match_exact,
        "lock_missing": lock_missing,
        "lock_extra": lock_extra,
        "lock_comparisons": [
            {
                "lock_path": item.lock_path,
                "exact_match": item.exact_match,
                "missing": item.missing,
                "extra": item.extra,
            }
            for item in comparisons
        ],
        "imports": imports + optional_imports,
        "scripts": script_imports,
        "warnings": warnings,
        "failures": failures,
    }
    report_md = build_report_md(report)
    python_version_text = (
        f"expected={expected_python}\n"
        f"current={current_python}\n"
        f"verification={verification_python_version}\n"
        f"verification_python={verification_python}\n"
    )
    outputs = write_environment_sidecars(
        repo,
        report_json=report,
        report_md=report_md,
        python_version_text=python_version_text,
        current_freeze_text=current_freeze_text,
        output_root=out,
    )

    print(f"environment verification: {report['overall_status']}")
    print(f"- expected python: {expected_python}")
    print(f"- verification python: {verification_python_version} ({verification_python})")
    print(f"- selected lock: {selected_lock_path or 'n/a'}")
    print(f"- artifacts: {out}")
    if warnings:
        for item in warnings:
            print(f"WARN: {item}")
    if failures:
        for item in failures:
            print(f"FAIL: {item}")
        return 1

    print("Next commands:")
    print(f"- {display_venv_python()} -m pytest -q")
    print(f"- {display_venv_python()} scripts/verify_baseline.py")
    for key, value in outputs.items():
        print(f"- {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
