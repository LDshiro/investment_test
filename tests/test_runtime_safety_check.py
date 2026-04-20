from __future__ import annotations

from pathlib import Path
import json
import subprocess

from leadlag.runtime.safety import run_runtime_safety_check


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _init_git_repo(repo_root: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "init"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )


def _prepare_temp_repo(repo_root: Path, *, include_logs: bool = True, include_state: bool = True) -> None:
    _write(repo_root / ".python-version", "3.14.3\n")
    _write(
        repo_root / ".env.example",
        "\n".join(
            [
                "# Shadow mode needs no real broker credentials.",
                "LEADLAG_MODE=shadow",
                "LEADLAG_ARTIFACT_ROOT=artifacts",
                "LEADLAG_LOG_DIR=logs",
                "",
                "# Future broker placeholders only. Do not fill real values.",
                "KABU_API_PASSWORD=",
                "IBKR_HOST=",
                "IBKR_PORT=",
            ]
        ),
    )
    (repo_root / "data/normalized/corrected_bundle").mkdir(parents=True, exist_ok=True)
    (repo_root / "runs").mkdir(parents=True, exist_ok=True)
    (repo_root / "artifacts").mkdir(parents=True, exist_ok=True)
    if include_logs:
        (repo_root / "logs").mkdir(parents=True, exist_ok=True)
    if include_state:
        (repo_root / "state").mkdir(parents=True, exist_ok=True)
    _write(repo_root / "docs/security_and_host_policy_v1.md", "backup plan doc\n")
    _write(repo_root / "docs/execution_host_setup_v1.md", "restore test doc\n")
    _init_git_repo(repo_root)


def test_runtime_safety_report_generation_redacts_secret_values(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _prepare_temp_repo(repo_root)

    result = run_runtime_safety_check(
        security_config=Path("configs/security/runtime_security_policy_v1.yaml").resolve(),
        secrets_inventory=Path("configs/security/secrets_inventory_v1.yaml").resolve(),
        host_config=Path("configs/runtime/execution_host_local_v1.yaml").resolve(),
        output_dir=tmp_path / "runtime_safety",
        repo_root=repo_root,
        environment={
            "LEADLAG_API_PASSWORD": "super-secret-value",
            "LEADLAG_MODE": "shadow",
        },
    )

    assert result.status == "PASS"
    snapshot_path = Path(result.output_paths["redacted_environment_snapshot_json"])
    report_json_path = Path(result.output_paths["runtime_safety_report_json"])
    report_md_path = Path(result.output_paths["runtime_safety_report_md"])
    for path in [snapshot_path, report_json_path, report_md_path]:
        text = path.read_text(encoding="utf-8")
        assert "super-secret-value" not in text
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["environment"]["LEADLAG_API_PASSWORD"] == "***REDACTED***"


def test_runtime_safety_fails_on_non_empty_env_example_secret_placeholder(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _prepare_temp_repo(repo_root)
    _write(
        repo_root / ".env.example",
        "\n".join(
            [
                "LEADLAG_MODE=shadow",
                "KABU_API_PASSWORD=not-empty",
                "IBKR_HOST=",
                "IBKR_PORT=",
            ]
        ),
    )
    subprocess.run(["git", "add", ".env.example"], cwd=repo_root, check=True, capture_output=True, text=True)

    result = run_runtime_safety_check(
        security_config=Path("configs/security/runtime_security_policy_v1.yaml").resolve(),
        secrets_inventory=Path("configs/security/secrets_inventory_v1.yaml").resolve(),
        host_config=Path("configs/runtime/execution_host_local_v1.yaml").resolve(),
        output_dir=tmp_path / "runtime_safety",
        repo_root=repo_root,
        environment={},
    )

    assert result.status == "FAIL"
    assert any(issue.code == "unsafe_env_example_value" for issue in result.issues)


def test_runtime_safety_warns_on_missing_logs_state_and_dirty_git(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _prepare_temp_repo(repo_root, include_logs=False, include_state=False)
    _write(repo_root / "untracked.txt", "dirty\n")

    result = run_runtime_safety_check(
        security_config=Path("configs/security/runtime_security_policy_v1.yaml").resolve(),
        secrets_inventory=Path("configs/security/secrets_inventory_v1.yaml").resolve(),
        host_config=Path("configs/runtime/execution_host_local_v1.yaml").resolve(),
        output_dir=tmp_path / "runtime_safety",
        repo_root=repo_root,
        environment={},
    )

    assert result.status == "WARN"
    codes = {issue.code for issue in result.issues}
    assert "missing_required_directory" in codes
    assert "git_dirty_state" in codes


def test_runtime_safety_fails_when_secret_file_is_tracked(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _prepare_temp_repo(repo_root)
    _write(repo_root / ".env.local", "SECRET=1\n")
    subprocess.run(["git", "add", ".env.local"], cwd=repo_root, check=True, capture_output=True, text=True)

    result = run_runtime_safety_check(
        security_config=Path("configs/security/runtime_security_policy_v1.yaml").resolve(),
        secrets_inventory=Path("configs/security/secrets_inventory_v1.yaml").resolve(),
        host_config=Path("configs/runtime/execution_host_local_v1.yaml").resolve(),
        output_dir=tmp_path / "runtime_safety",
        repo_root=repo_root,
        environment={},
    )

    assert result.status == "FAIL"
    assert any(issue.code == "tracked_secret_file" for issue in result.issues)
