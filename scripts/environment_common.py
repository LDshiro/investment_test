from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Iterable

from baseline_common import file_record, read_json, render_command, utc_now_iso, write_json, write_text


ENV_REPRO_NAME = "environment_repro_v1"
ENV_ARTIFACT_ROOT_REL = Path("artifacts") / ENV_REPRO_NAME
EXPECTED_PYTHON_REL = Path(".python-version")
RUNTIME_LOCK_REL = Path("requirements.lock.txt")
DEV_LOCK_REL = Path("requirements-dev.lock.txt")
BASELINE_ROOT_REL = Path("artifacts") / "baseline_shadow_stack_v1"
BASELINE_MANIFEST_REL = BASELINE_ROOT_REL / "baseline_manifest.json"
BASELINE_PIP_FREEZE_REL = BASELINE_ROOT_REL / "pip_freeze.txt"

RUNTIME_IMPORTS = [
    ("numpy", "numpy"),
    ("pandas", "pandas"),
    ("yaml", "PyYAML"),
    ("pydantic", "pydantic"),
    ("duckdb", "duckdb"),
    ("matplotlib", "matplotlib"),
    ("statsmodels", "statsmodels"),
    ("tabulate", "tabulate"),
]

OPTIONAL_DEV_IMPORTS = [
    ("pytest", "pytest"),
]

SCRIPT_IMPORTS = [
    "verify_baseline",
    "freeze_baseline",
]


@dataclass
class LockComparison:
    lock_path: str
    exact_match: bool
    missing: list[str]
    extra: list[str]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def artifact_root(repo: Path | None = None) -> Path:
    repo = repo_root() if repo is None else repo
    return repo / ENV_ARTIFACT_ROOT_REL


def venv_dir(repo: Path | None = None) -> Path:
    repo = repo_root() if repo is None else repo
    return repo / ".venv"


def venv_python(repo: Path | None = None) -> Path:
    base = venv_dir(repo)
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    exe_name = "python.exe" if os.name == "nt" else "python"
    return base / scripts_dir / exe_name


def display_venv_python() -> str:
    return r".venv\Scripts\python.exe" if os.name == "nt" else ".venv/bin/python"


def normalize_python_version(text: str) -> str:
    match = re.search(r"(\d+\.\d+\.\d+)", text)
    if not match:
        raise ValueError(f"Could not parse python version from: {text}")
    return match.group(1)


def parse_python_version(text: str) -> tuple[int, int, int]:
    token = normalize_python_version(text)
    major, minor, patch = token.split(".")
    return int(major), int(minor), int(patch)


def python_version_matches(current: str, expected: str) -> bool:
    return parse_python_version(current) == parse_python_version(expected)


def current_python_version() -> str:
    return ".".join(str(part) for part in sys.version_info[:3])


def python_version_for_executable(python_exe: Path) -> str:
    proc = subprocess.run(
        [str(python_exe), "-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"],
        capture_output=True,
        text=True,
        check=True,
    )
    return normalize_python_version(proc.stdout.strip())


def read_expected_python(repo: Path | None = None) -> str:
    repo = repo_root() if repo is None else repo
    path = repo / EXPECTED_PYTHON_REL
    if path.exists():
        return normalize_python_version(path.read_text(encoding="utf-8").strip())

    baseline = load_baseline_manifest(repo)
    if baseline:
        baseline_version = baseline_python_version(repo)
        if baseline_version:
            return baseline_version
    raise FileNotFoundError(f"Expected python pin not found: {path}")


def inside_virtualenv() -> bool:
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def load_baseline_manifest(repo: Path | None = None) -> dict[str, Any] | None:
    repo = repo_root() if repo is None else repo
    path = repo / BASELINE_MANIFEST_REL
    if not path.exists():
        return None
    return read_json(path)


def baseline_python_version(repo: Path | None = None) -> str | None:
    baseline = load_baseline_manifest(repo)
    if not baseline:
        return None
    env = baseline.get("environment", {})
    version = env.get("python_version")
    if not version:
        return None
    return normalize_python_version(version)


def normalize_editable_line(line: str, repo: Path) -> str:
    stripped = line.strip()
    if not stripped.lower().startswith("-e "):
        return stripped

    target = stripped[3:].strip().strip('"').strip("'")
    if target == ".":
        return "-e ."

    target_path = Path(target)
    target_resolved = target_path.resolve(strict=False)
    repo_resolved = repo.resolve(strict=False)
    if os.path.normcase(str(target_resolved)) == os.path.normcase(str(repo_resolved)):
        return "-e ."
    return stripped


def normalize_freeze_lines(lines: Iterable[str], repo: Path | None = None) -> list[str]:
    repo = repo_root() if repo is None else repo
    normalized: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        normalized.append(normalize_editable_line(stripped, repo))
    return sorted(dict.fromkeys(normalized), key=str.casefold)


def read_lock_lines(path: Path, repo: Path | None = None) -> list[str]:
    repo = repo_root() if repo is None else repo
    return normalize_freeze_lines(path.read_text(encoding="utf-8").splitlines(), repo)


def run_pip_freeze(python_exe: Path, repo: Path | None = None) -> tuple[str, list[str]]:
    repo = repo_root() if repo is None else repo
    proc = subprocess.run(
        [str(python_exe), "-m", "pip", "freeze"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout, normalize_freeze_lines(proc.stdout.splitlines(), repo)


def compare_lock_lines(current_lines: list[str], lock_lines: list[str], lock_path: Path, repo: Path | None = None) -> LockComparison:
    current = set(current_lines)
    target = set(lock_lines)
    return LockComparison(
        lock_path=lock_path.relative_to(repo_root() if repo is None else repo).as_posix(),
        exact_match=current == target,
        missing=sorted(target - current, key=str.casefold),
        extra=sorted(current - target, key=str.casefold),
    )


def choose_best_lock(repo: Path, current_lines: list[str]) -> tuple[LockComparison | None, list[LockComparison]]:
    comparisons: list[LockComparison] = []
    for rel in (DEV_LOCK_REL, RUNTIME_LOCK_REL):
        path = repo / rel
        if not path.exists():
            continue
        comparisons.append(compare_lock_lines(current_lines, read_lock_lines(path, repo), path, repo))

    if not comparisons:
        return None, []

    def score(item: LockComparison) -> tuple[int, int, int]:
        rel = item.lock_path
        return (
            0 if item.exact_match else 1,
            len(item.missing) + len(item.extra),
            0 if rel.endswith(DEV_LOCK_REL.as_posix()) else 1,
        )

    ordered = sorted(comparisons, key=score)
    return ordered[0], comparisons


def lock_hashes(repo: Path | None = None) -> dict[str, Any]:
    repo = repo_root() if repo is None else repo
    records: list[dict[str, Any]] = []
    for rel in (RUNTIME_LOCK_REL, DEV_LOCK_REL):
        record = file_record(repo / rel, root=repo)
        record["kind"] = rel.name
        records.append(record)
    return {
        "generated_at_utc": utc_now_iso(),
        "entries": records,
    }


def overall_status(*, failures: list[str], warnings: list[str]) -> str:
    if failures:
        return "fail"
    if warnings:
        return "warn"
    return "pass"


def resolve_repo_venv_target(repo: Path, candidate: Path | None = None) -> Path:
    expected = (repo / ".venv").resolve(strict=False)
    candidate = expected if candidate is None else candidate.resolve(strict=False)
    if os.path.normcase(str(candidate)) != os.path.normcase(str(expected)):
        raise ValueError(f"Refusing to operate on non-local venv target: {candidate}")
    return expected


def current_interpreter_is_repo_venv(repo: Path | None = None) -> bool:
    repo = repo_root() if repo is None else repo
    try:
        expected = resolve_repo_venv_target(repo)
    except ValueError:
        return False
    current = Path(sys.executable).resolve(strict=False)
    return os.path.normcase(str(current)).startswith(os.path.normcase(str(expected)))


def ensure_removed_tree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def write_lock_file(path: Path, *, lines: list[str], source_label: str) -> None:
    header = [
        "# Generated by scripts/export_environment_snapshot.py --refresh-locks",
        f"# source: {source_label}",
        "",
    ]
    write_text(path, "\n".join(header + lines) + "\n")


def select_dev_lock_source(repo: Path) -> tuple[str, list[str]]:
    baseline_freeze = repo / BASELINE_PIP_FREEZE_REL
    if baseline_freeze.exists():
        lines = normalize_freeze_lines(baseline_freeze.read_text(encoding="utf-8").splitlines(), repo)
        return baseline_freeze.relative_to(repo).as_posix(), lines

    current_venv_python = venv_python(repo)
    if current_venv_python.exists():
        _raw, lines = run_pip_freeze(current_venv_python, repo)
        return f"{display_venv_python()} -m pip freeze", lines

    raise FileNotFoundError("Could not determine a source for requirements-dev.lock.txt")


def generate_dev_lock(repo: Path) -> dict[str, Any]:
    source_label, lines = select_dev_lock_source(repo)
    write_lock_file(repo / DEV_LOCK_REL, lines=lines, source_label=source_label)
    return {
        "path": DEV_LOCK_REL.as_posix(),
        "source": source_label,
        "line_count": len(lines),
    }


def generate_runtime_lock(repo: Path, python_exe: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="leadlag_runtime_lock_") as tmp:
        temp_root = Path(tmp) / "venv"
        subprocess.run([str(python_exe), "-m", "venv", str(temp_root)], cwd=repo, check=True)
        temp_python = temp_root / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
        subprocess.run([str(temp_python), "-m", "pip", "install", "--upgrade", "pip"], cwd=repo, check=True)
        install_args = [str(temp_python), "-m", "pip", "install"]
        dev_lock = repo / DEV_LOCK_REL
        source_label = f"temporary venv via {python_exe.name}"
        if dev_lock.exists():
            constraint_path = Path(tmp) / "constraints.txt"
            constraint_lines = [line for line in read_lock_lines(dev_lock, repo) if not line.startswith("-e ")]
            write_text(constraint_path, "\n".join(constraint_lines) + ("\n" if constraint_lines else ""))
            install_args.extend(["-c", str(constraint_path)])
            source_label += f" constrained by {DEV_LOCK_REL.as_posix()}"
        install_args.extend(["-e", "."])
        subprocess.run(install_args, cwd=repo, check=True)
        _raw, lines = run_pip_freeze(temp_python, repo)

    write_lock_file(repo / RUNTIME_LOCK_REL, lines=lines, source_label=source_label)
    return {
        "path": RUNTIME_LOCK_REL.as_posix(),
        "source": source_label,
        "line_count": len(lines),
    }


def target_python_for_verification(repo: Path) -> Path:
    repo_venv_python = venv_python(repo)
    if repo_venv_python.exists():
        return repo_venv_python
    return Path(sys.executable).resolve(strict=False)


def build_commands_md() -> str:
    venv_python_cmd = display_venv_python()
    lines = [
        "# Environment Repro Commands",
        "",
        "## Bootstrap",
        "",
        "```bash",
        "python scripts/bootstrap_env.py --dev",
        "python scripts/bootstrap_env.py --dev --recreate",
        "python scripts/bootstrap_env.py --runtime-only",
        "```",
        "",
        "## Verify",
        "",
        "```bash",
        f"{venv_python_cmd} -m pytest -q",
        f"{venv_python_cmd} scripts/verify_environment.py",
        f"{venv_python_cmd} scripts/verify_baseline.py",
        "```",
        "",
        "## Refresh locks",
        "",
        "```bash",
        "python scripts/export_environment_snapshot.py --refresh-locks",
        "```",
    ]
    return "\n".join(lines) + "\n"


def write_environment_sidecars(
    repo: Path,
    *,
    report_json: dict[str, Any],
    report_md: str,
    python_version_text: str,
    current_freeze_text: str,
    output_root: Path | None = None,
) -> dict[str, str]:
    out = artifact_root(repo) if output_root is None else output_root
    out.mkdir(parents=True, exist_ok=True)
    report_json_path = out / "environment_report.json"
    report_md_path = out / "environment_report.md"
    python_version_path = out / "python_version.txt"
    current_freeze_path = out / "pip_freeze.current.txt"
    lock_hashes_path = out / "lock_hashes.json"
    commands_path = out / "commands.md"

    write_json(report_json_path, report_json)
    write_text(report_md_path, report_md)
    write_text(python_version_path, python_version_text)
    write_text(current_freeze_path, current_freeze_text)
    write_json(lock_hashes_path, lock_hashes(repo))
    write_text(commands_path, build_commands_md())
    return {
        "environment_report_json": report_json_path.relative_to(repo).as_posix(),
        "environment_report_md": report_md_path.relative_to(repo).as_posix(),
        "python_version_txt": python_version_path.relative_to(repo).as_posix(),
        "pip_freeze_current_txt": current_freeze_path.relative_to(repo).as_posix(),
        "lock_hashes_json": lock_hashes_path.relative_to(repo).as_posix(),
        "commands_md": commands_path.relative_to(repo).as_posix(),
    }
