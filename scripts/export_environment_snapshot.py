from __future__ import annotations

import argparse
from pathlib import Path
import sys

from environment_common import (
    artifact_root,
    current_python_version,
    generate_dev_lock,
    generate_runtime_lock,
    python_version_matches,
    read_expected_python,
    repo_root,
    run_pip_freeze,
    target_python_for_verification,
    utc_now_iso,
    write_environment_sidecars,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export lock files and environment snapshot artifacts.")
    parser.add_argument("--refresh-locks", action="store_true", help="Regenerate requirements.lock.txt and requirements-dev.lock.txt.")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    repo = repo_root()
    expected_python = read_expected_python(repo)
    current_python = current_python_version()
    if not python_version_matches(current_python, expected_python):
        print(
            f"ERROR: export_environment_snapshot.py must be run with Python {expected_python}; current interpreter is {current_python}."
        )
        return 1

    lock_generation: dict[str, object] = {}
    if args.refresh_locks:
        lock_generation["requirements_dev"] = generate_dev_lock(repo)
        lock_generation["requirements_runtime"] = generate_runtime_lock(repo, Path(sys.executable).resolve(strict=False))

    verification_python = target_python_for_verification(repo)
    current_freeze_text, _normalized = run_pip_freeze(verification_python, repo)
    report = {
        "environment_name": "environment_repro_v1",
        "generated_at_utc": utc_now_iso(),
        "overall_status": "pass",
        "expected_python": expected_python,
        "current_python": current_python,
        "verification_python": str(verification_python.resolve(strict=False)),
        "lock_generation": lock_generation,
        "notes": [
            "Lock files are anchored to the Step 01 baseline pip freeze when available.",
            "requirements.lock.txt is generated from a clean temporary venv constrained by requirements-dev.lock.txt.",
        ],
    }
    report_md = (
        "# Environment Snapshot Export\n\n"
        f"- generated_at_utc: `{report['generated_at_utc']}`\n"
        f"- expected_python: `{expected_python}`\n"
        f"- current_python: `{current_python}`\n"
        f"- verification_python: `{verification_python}`\n"
    )
    python_version_text = (
        f"expected={expected_python}\n"
        f"current={current_python}\n"
        f"verification_python={verification_python}\n"
    )
    outputs = write_environment_sidecars(
        repo,
        report_json=report,
        report_md=report_md,
        python_version_text=python_version_text,
        current_freeze_text=current_freeze_text,
        output_root=artifact_root(repo),
    )

    print(f"environment snapshot written: {artifact_root(repo)}")
    for key, value in lock_generation.items():
        print(f"- {key}: {value}")
    for key, value in outputs.items():
        print(f"- {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
