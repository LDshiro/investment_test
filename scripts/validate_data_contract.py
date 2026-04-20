from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from leadlag.data_contract import validate_corrected_bundle, write_validation_outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the corrected bundle against the corrected_bundle_v1 contract.")
    parser.add_argument(
        "--bundle-dir",
        default="data/normalized/corrected_bundle",
        help="Corrected bundle directory to validate.",
    )
    parser.add_argument(
        "--contract",
        default="configs/data_contracts/corrected_bundle_v1.yaml",
        help="Data contract YAML file.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/data_contract/corrected_bundle_v1",
        help="Directory where validation outputs will be written.",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    result = validate_corrected_bundle(Path(args.bundle_dir), Path(args.contract))
    output_dir = Path(args.output_dir)
    write_validation_outputs(result, output_dir)

    print(
        json.dumps(
            {
                "passed": result.passed,
                "issue_counts": result.issue_counts(),
                "output_dir": str(output_dir.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
