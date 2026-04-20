from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from environment_common import (
    choose_best_lock,
    lock_hashes,
    normalize_freeze_lines,
    overall_status,
    parse_python_version,
    python_version_matches,
    resolve_repo_venv_target,
    select_dev_lock_source,
    write_lock_file,
)


def test_python_version_parsing_and_match() -> None:
    assert parse_python_version("3.14.3") == (3, 14, 3)
    assert python_version_matches("3.14.3", "3.14.3") is True
    assert python_version_matches("3.14.2", "3.14.3") is False


def test_normalize_freeze_lines_rewrites_repo_editable(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'leadlag-stack'\n",
        encoding="utf-8",
    )
    lines = [
        "# comment",
        f"-e {tmp_path}",
        "numpy==2.4.4",
        "",
    ]
    normalized = normalize_freeze_lines(lines, tmp_path)
    assert normalized == ["-e .", "numpy==2.4.4"]


def test_normalize_freeze_lines_rewrites_repo_vcs_editable(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'leadlag-stack'\n",
        encoding="utf-8",
    )
    lines = [
        "-e git+https://github.com/example/investment_test.git@abc123#egg=leadlag_stack",
        "numpy==2.4.4",
    ]
    normalized = normalize_freeze_lines(lines, tmp_path)
    assert normalized == ["-e .", "numpy==2.4.4"]


def test_select_dev_lock_source_prefers_baseline_snapshot(tmp_path: Path) -> None:
    baseline_freeze = tmp_path / "artifacts" / "baseline_shadow_stack_v1" / "pip_freeze.txt"
    baseline_freeze.parent.mkdir(parents=True)
    baseline_freeze.write_text("-e .\nnumpy==2.4.4\n", encoding="utf-8")

    source, lines = select_dev_lock_source(tmp_path)
    assert source == "artifacts/baseline_shadow_stack_v1/pip_freeze.txt"
    assert lines == ["-e .", "numpy==2.4.4"]


def test_choose_best_lock_prefers_exact_match(tmp_path: Path) -> None:
    write_lock_file(
        tmp_path / "requirements-dev.lock.txt",
        lines=["-e .", "numpy==2.4.4", "pytest==9.0.3"],
        source_label="dev",
    )
    write_lock_file(
        tmp_path / "requirements.lock.txt",
        lines=["-e .", "numpy==2.4.4"],
        source_label="runtime",
    )

    best, comparisons = choose_best_lock(tmp_path, ["-e .", "numpy==2.4.4"])
    assert best is not None
    assert best.lock_path == "requirements.lock.txt"
    assert best.exact_match is True
    assert len(comparisons) == 2


def test_lock_hashes_reports_both_files(tmp_path: Path) -> None:
    (tmp_path / "requirements.lock.txt").write_text("numpy==2.4.4\n", encoding="utf-8")
    (tmp_path / "requirements-dev.lock.txt").write_text("pytest==9.0.3\n", encoding="utf-8")
    payload = lock_hashes(tmp_path)
    assert len(payload["entries"]) == 2
    assert {item["kind"] for item in payload["entries"]} == {
        "requirements.lock.txt",
        "requirements-dev.lock.txt",
    }


def test_overall_status_classifies_fail_warn_pass() -> None:
    assert overall_status(failures=["x"], warnings=[]) == "fail"
    assert overall_status(failures=[], warnings=["y"]) == "warn"
    assert overall_status(failures=[], warnings=[]) == "pass"


def test_resolve_repo_venv_target_rejects_outside_path(tmp_path: Path) -> None:
    resolved = resolve_repo_venv_target(tmp_path)
    assert resolved == (tmp_path / ".venv").resolve(strict=False)
    try:
        resolve_repo_venv_target(tmp_path, tmp_path / "other")
    except ValueError:
        pass
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("expected ValueError for non-local venv target")
