from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys

from environment_common import (
    DEV_LOCK_REL,
    RUNTIME_LOCK_REL,
    current_interpreter_is_repo_venv,
    current_python_version,
    display_venv_python,
    python_version_matches,
    read_expected_python,
    repo_root,
    resolve_repo_venv_target,
    venv_python,
)


def _fail(message: str) -> int:
    print(f"ERROR: {message}")
    return 1


def _run(args: list[str], repo: Path) -> None:
    print(f"+ {' '.join(args)}")
    subprocess.run(args, cwd=repo, check=True)


def _install_from_locks(repo: Path, *, dev_mode: bool) -> str:
    py = venv_python(repo)
    if dev_mode:
        dev_lock = repo / DEV_LOCK_REL
        if dev_lock.exists():
            _run([str(py), "-m", "pip", "install", "-r", DEV_LOCK_REL.as_posix()], repo)
            return DEV_LOCK_REL.as_posix()
        _run([str(py), "-m", "pip", "install", "-e", ".[dev]"], repo)
        return "project metadata fallback (-e .[dev])"

    runtime_lock = repo / RUNTIME_LOCK_REL
    dev_lock = repo / DEV_LOCK_REL
    if runtime_lock.exists():
        _run([str(py), "-m", "pip", "install", "-r", RUNTIME_LOCK_REL.as_posix()], repo)
        return RUNTIME_LOCK_REL.as_posix()
    if dev_lock.exists():
        _run([str(py), "-m", "pip", "install", "-c", DEV_LOCK_REL.as_posix(), "-e", "."], repo)
        return f"constraint fallback ({DEV_LOCK_REL.as_posix()})"
    _run([str(py), "-m", "pip", "install", "-e", "."], repo)
    return "project metadata fallback (-e .)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create or refresh the local reproducible .venv.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dev", action="store_true", help="Install the development environment (default).")
    mode.add_argument("--runtime-only", action="store_true", help="Install only runtime dependencies.")
    parser.add_argument("--recreate", action="store_true", help="Delete and recreate the repo-local .venv.")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    repo = repo_root()
    expected_python = read_expected_python(repo)
    current_python = current_python_version()
    if not python_version_matches(current_python, expected_python):
        return _fail(
            f"bootstrap_env.py must be run with Python {expected_python}; current interpreter is {current_python}. "
            "See .python-version and artifacts/baseline_shadow_stack_v1/baseline_manifest.json."
        )

    dev_mode = not args.runtime_only
    target_venv = resolve_repo_venv_target(repo)
    if args.recreate and current_interpreter_is_repo_venv(repo):
        return _fail("Refusing to recreate .venv while running from the repo-local .venv. Use the system Python instead.")

    if args.recreate and target_venv.exists():
        print(f"Removing existing virtual environment: {target_venv}")
        shutil.rmtree(target_venv)

    if not target_venv.exists():
        print(f"Creating virtual environment: {target_venv}")
        _run([sys.executable, "-m", "venv", str(target_venv)], repo)

    py = venv_python(repo)
    if not py.exists():
        return _fail(f"Expected venv interpreter not found: {py}")

    _run([str(py), "-m", "pip", "install", "--upgrade", "pip"], repo)
    install_source = _install_from_locks(repo, dev_mode=dev_mode)

    print("")
    print("Environment bootstrap complete.")
    print(f"- mode: {'dev' if dev_mode else 'runtime-only'}")
    print(f"- python: {expected_python}")
    print(f"- venv: {target_venv}")
    print(f"- install source: {install_source}")
    print("")
    print("Next commands:")
    print(f"- {display_venv_python()} -m pytest -q")
    print(f"- {display_venv_python()} scripts/verify_environment.py")
    print(f"- {display_venv_python()} scripts/verify_baseline.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
