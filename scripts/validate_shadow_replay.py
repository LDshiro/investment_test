from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from leadlag.ops import validate_shadow_replay


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a historical shadow batch replay directory.")
    parser.add_argument("--batch-dir", required=True, help="Historical shadow batch directory.")
    parser.add_argument("--validation-config", required=True, help="Validation config YAML.")
    parser.add_argument("--output-dir", required=True, help="Directory for validation artifacts.")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    result = validate_shadow_replay(
        batch_dir=Path(args.batch_dir),
        validation_config=Path(args.validation_config),
        output_dir=Path(args.output_dir),
    )
    print(
        json.dumps(
            {
                "status": result.status,
                "passed": result.passed,
                "summary": result.summary,
                "output_dir": str(Path(args.output_dir).resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.status != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
