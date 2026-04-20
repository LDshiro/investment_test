from __future__ import annotations

from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from baseline_common import build_sha256_manifest_lines, file_record, write_json, write_sha256_manifest, write_text
from freeze_baseline import CommandResult, collect_git_metadata
from verify_baseline import validate_baseline


def test_collect_git_metadata_handles_unavailable_repo(tmp_path: Path) -> None:
    meta = collect_git_metadata(tmp_path)
    assert meta["available"] is False
    assert meta["reason"]
    assert meta["requested_tag"] == "baseline-shadow-stack-v1"


def test_sha256_manifest_matches_recomputed_tree(tmp_path: Path) -> None:
    write_text(tmp_path / "a.txt", "alpha\n")
    write_text(tmp_path / "nested" / "b.txt", "beta\n")
    write_sha256_manifest(tmp_path)
    expected = "\n".join(build_sha256_manifest_lines(tmp_path, exclude={"sha256_manifest.txt"}))
    actual = (tmp_path / "sha256_manifest.txt").read_text(encoding="utf-8").rstrip("\n")
    assert expected == actual


def test_validate_baseline_passes_for_consistent_artifacts(tmp_path: Path) -> None:
    reference = tmp_path / "reference_results"
    reference.mkdir(parents=True)
    write_text(reference / "placeholder.txt", "ok\n")
    config_hashes = {"entries": [{"path": "configs/profiles/shadow_corrected_local.yaml", "exists": True}]}
    data_hashes = {"entries": [{"path": "data/normalized/corrected_bundle/returns_cc.csv", "exists": True}]}
    manifest = {
        "baseline_name": "baseline_shadow_stack_v1",
        "created_at_utc": "2026-04-17T00:00:00Z",
        "git": {"available": False},
        "environment": {"dependency_snapshot": "pip_freeze.txt"},
        "canonical_profiles": [],
        "auxiliary_profiles": [],
        "config_hashes": config_hashes,
        "data_hashes": data_hashes,
        "reference_commands": [],
        "reference_artifacts": {},
        "acceptance_checks": [{"name": "ok", "status": "pass"}],
        "notes": [],
    }

    write_text(tmp_path / "README.md", "# baseline\n")
    write_json(tmp_path / "config_hashes.json", config_hashes)
    write_json(tmp_path / "data_hashes.json", data_hashes)
    write_text(tmp_path / "reference_commands.md", "# commands\n")
    write_text(tmp_path / "baseline_manifest.md", "# manifest\n")
    write_json(tmp_path / "baseline_manifest.json", manifest)
    write_sha256_manifest(tmp_path)

    assert validate_baseline(tmp_path) == []


def test_validate_baseline_reports_missing_required_file(tmp_path: Path) -> None:
    write_json(
        tmp_path / "baseline_manifest.json",
        {
            "baseline_name": "baseline_shadow_stack_v1",
            "created_at_utc": "2026-04-17T00:00:00Z",
            "git": {},
            "environment": {},
            "canonical_profiles": [],
            "auxiliary_profiles": [],
            "config_hashes": {},
            "data_hashes": {},
            "reference_commands": [],
            "reference_artifacts": {},
            "acceptance_checks": [],
            "notes": [],
        },
    )
    errors = validate_baseline(tmp_path)
    assert any("missing required artifact" in item for item in errors)


def test_manifest_sidecars_can_roundtrip(tmp_path: Path) -> None:
    payload = {"entries": [{"path": "x", "exists": True}]}
    write_json(tmp_path / "config_hashes.json", payload)
    loaded = json.loads((tmp_path / "config_hashes.json").read_text(encoding="utf-8"))
    assert loaded["entries"][0]["path"] == "x"


def test_file_record_has_required_hash_keys(tmp_path: Path) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("sample\n", encoding="utf-8")
    record = file_record(target, root=tmp_path)
    assert set(record) >= {"path", "exists", "size_bytes", "mtime_utc", "sha256"}
    assert record["path"] == "sample.txt"
    assert record["exists"] is True


def test_command_result_manifest_keeps_substitution_and_outputs() -> None:
    result = CommandResult(
        name="inspect_bundle",
        requested_command="requested",
        actual_command="actual",
        substitution_note="substituted",
        exit_code=0,
        stdout_path="stdout.txt",
        stderr_path="stderr.txt",
        resolved_output_path="artifacts/out",
        output_artifacts=["artifacts/out/summary.json"],
    )
    payload = result.to_manifest()
    assert payload["substitution_note"] == "substituted"
    assert payload["resolved_output_path"] == "artifacts/out"
    assert payload["output_artifacts"] == ["artifacts/out/summary.json"]
