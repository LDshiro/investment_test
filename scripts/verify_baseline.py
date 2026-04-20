from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

from baseline_common import (
    ARTIFACT_ROOT_REL,
    REQUIRED_ARTIFACT_FILES,
    REQUIRED_MANIFEST_KEYS,
    build_sha256_manifest_lines,
    read_json,
)


def validate_baseline(artifact_root: Path) -> list[str]:
    errors: list[str] = []
    for rel in REQUIRED_ARTIFACT_FILES:
        if not (artifact_root / rel).exists():
            errors.append(f"missing required artifact: {rel}")

    manifest_path = artifact_root / "baseline_manifest.json"
    if not manifest_path.exists():
        return errors

    manifest = read_json(manifest_path)
    for key in REQUIRED_MANIFEST_KEYS:
        if key not in manifest:
            errors.append(f"manifest missing key: {key}")

    for rel, manifest_key in [
        ("config_hashes.json", "config_hashes"),
        ("data_hashes.json", "data_hashes"),
    ]:
        path = artifact_root / rel
        if path.exists() and manifest.get(manifest_key) != read_json(path):
            errors.append(f"manifest mismatch for {manifest_key}")

    sha_path = artifact_root / "sha256_manifest.txt"
    if sha_path.exists():
        expected = "\n".join(build_sha256_manifest_lines(artifact_root, exclude={"sha256_manifest.txt"}))
        actual = sha_path.read_text(encoding="utf-8").rstrip("\n")
        if expected != actual:
            errors.append("sha256_manifest.txt does not match recomputed hashes")

    for item in manifest.get("acceptance_checks", []):
        if item.get("status") != "pass":
            errors.append(f"acceptance check not passed: {item.get('name')}")

    reference_results = artifact_root / "reference_results"
    if not reference_results.exists():
        errors.append("reference_results directory missing")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify baseline artifacts are present and internally consistent.")
    parser.add_argument(
        "--artifact-root",
        default=str(ARTIFACT_ROOT_REL),
        help="Baseline artifact root to verify.",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    artifact_root = Path(args.artifact_root).resolve()
    errors = validate_baseline(artifact_root)
    if errors:
        print(f"baseline verification failed: {artifact_root}")
        for item in errors:
            print(f"- {item}")
        return 1
    print(f"baseline verification passed: {artifact_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
