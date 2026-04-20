from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import time
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from leadlag.config.loader import load_app_config
from leadlag.runtime.corrected_shadow import prepare_corrected_shadow_context, run_corrected_shadow_prepared
from leadlag.simulator_audit import (
    build_audit_summary_frame,
    compare_fingerprint_sets,
    extract_packet_audit_row,
    fingerprint_packet,
    load_simulator_contract,
    select_golden_days,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run golden-day simulator audit packets and deterministic rerun checks.")
    parser.add_argument(
        "--config",
        default="configs/profiles/shadow_corrected_local.yaml",
        help="Historical shadow profile used for the audit.",
    )
    parser.add_argument(
        "--simulator-contract",
        default="configs/simulator/canonical_simulator_v1.yaml",
        help="Simulator contract YAML path.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/simulator_audit/canonical_v1",
        help="Directory where audit artifacts will be written.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Regenerate golden days and overwrite existing audit outputs.",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    output_dir = Path(args.output_dir).resolve()
    if args.refresh and output_dir.exists():
        _remove_tree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cfg = load_app_config(Path(args.config))
    contract = load_simulator_contract(Path(args.simulator_contract))
    prepared = prepare_corrected_shadow_context(cfg)
    golden_days = _load_or_select_golden_days(output_dir, cfg, prepared, contract, refresh=args.refresh)

    staging_root = output_dir / "_staging_runs"
    if staging_root.exists():
        _remove_tree(staging_root)
    staging_root.mkdir(parents=True, exist_ok=True)

    primary_cfg = _clone_config(cfg)
    primary_cfg.run.runs_root = str(staging_root)
    packets_root = output_dir / "packets"
    packets_root.mkdir(parents=True, exist_ok=True)

    primary_rows: list[dict[str, Any]] = []
    primary_fingerprints: dict[str, Any] = {}
    for golden_day in golden_days:
        trade_date = str(golden_day["trade_date"])
        packet_dir, _ = run_corrected_shadow_prepared(primary_cfg, prepared, trade_date_override=trade_date)
        final_packet_dir = packets_root / trade_date
        _copy_packet_tree(packet_dir, final_packet_dir)
        fingerprint = fingerprint_packet(packet_dir, contract)
        primary_fingerprints[trade_date] = fingerprint
        audit_row = extract_packet_audit_row(final_packet_dir, f"packets/{trade_date}")
        audit_row.update(
            {
                "selection_rank": int(golden_day["selection_rank"]),
                "selection_reason": str(golden_day["selection_reason"]),
                "matched_categories": str(golden_day.get("matched_categories", golden_day["selection_reason"])),
                "is_holiday_edge": bool(golden_day.get("is_holiday_edge", False)),
                "stable_fingerprint": fingerprint["stable_fingerprint"],
                "rerun_match": False,
            }
        )
        primary_rows.append(audit_row)

    deterministic_required = bool(contract.get("audit", {}).get("deterministic_rerun_required", True))
    rerun_fingerprints: dict[str, Any] = {}
    comparison = {
        "passed": True,
        "trade_dates": [str(row["trade_date"]) for row in golden_days],
        "missing_primary": [],
        "missing_rerun": [],
        "mismatches": [],
        "per_trade_date": {},
    }
    if deterministic_required:
        time.sleep(1.1)
        rerun_cfg = _clone_config(cfg)
        rerun_cfg.run.runs_root = str(staging_root)
        for golden_day in golden_days:
            trade_date = str(golden_day["trade_date"])
            packet_dir, _ = run_corrected_shadow_prepared(rerun_cfg, prepared, trade_date_override=trade_date)
            rerun_fingerprints[trade_date] = fingerprint_packet(packet_dir, contract)
        comparison = compare_fingerprint_sets(primary_fingerprints, rerun_fingerprints)

    for row in primary_rows:
        trade_date = str(row["trade_date"])
        row["rerun_match"] = bool(comparison["per_trade_date"].get(trade_date, {}).get("match", not deterministic_required))

    summary_frame = build_audit_summary_frame(primary_rows).sort_values("selection_rank")
    summary_frame.to_csv(output_dir / "audit_summary.csv", index=False)

    fingerprints_payload = {
        "contract_version": contract.get("version"),
        "primary": primary_fingerprints,
        "rerun": rerun_fingerprints,
        "comparison": comparison,
    }
    (output_dir / "fingerprints.json").write_text(
        json.dumps(fingerprints_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    json_payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "config_path": str(Path(args.config).resolve()),
        "simulator_contract_path": str(Path(args.simulator_contract).resolve()),
        "output_dir": str(output_dir),
        "golden_days": golden_days,
        "audit_rows": summary_frame.to_dict(orient="records"),
        "deterministic_rerun": comparison,
    }
    (output_dir / "audit_summary.json").write_text(
        json.dumps(json_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "audit_summary.md").write_text(
        _render_markdown_summary(
            contract=contract,
            config_path=Path(args.config),
            golden_days=golden_days,
            summary_frame=summary_frame,
            comparison=comparison,
        ),
        encoding="utf-8",
    )

    if staging_root.exists():
        _remove_tree(staging_root)

    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "golden_days": [str(row["trade_date"]) for row in golden_days],
                "deterministic_rerun_passed": bool(comparison["passed"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if bool(comparison["passed"]) else 1


def _clone_config(cfg):
    if hasattr(cfg, "model_copy"):
        return cfg.model_copy(deep=True)
    return copy.deepcopy(cfg)


def _copy_packet_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        _remove_tree(dst)
    shutil.copytree(src, dst)


def _remove_tree(path: Path) -> None:
    path = Path(path)
    if not path.exists():
        return
    last_error: Exception | None = None
    for _ in range(3):
        try:
            shutil.rmtree(path, onexc=_handle_remove_readonly)
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(0.5)
    if last_error is not None:
        raise last_error


def _handle_remove_readonly(func, path, excinfo) -> None:
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _load_or_select_golden_days(
    output_dir: Path,
    cfg,
    prepared: dict[str, Any],
    contract: dict[str, Any],
    *,
    refresh: bool,
) -> list[dict[str, Any]]:
    golden_days_path = output_dir / "golden_days.csv"
    if golden_days_path.exists() and not refresh:
        frame = pd.read_csv(golden_days_path)
    else:
        rows = select_golden_days(cfg, prepared, contract)
        frame = pd.DataFrame(rows)
        frame.to_csv(golden_days_path, index=False)
    return frame.sort_values("selection_rank").to_dict(orient="records")


def _render_markdown_summary(
    *,
    contract: dict[str, Any],
    config_path: Path,
    golden_days: list[dict[str, Any]],
    summary_frame: pd.DataFrame,
    comparison: dict[str, Any],
) -> str:
    golden_frame = pd.DataFrame(golden_days)
    lines = [
        "# Canonical Simulator Golden-Day Audit",
        "",
        f"- Contract: `{contract.get('version')}`",
        f"- Config: `{config_path.as_posix()}`",
        f"- Golden days selected: {len(golden_days)}",
        f"- Deterministic rerun required: {bool(contract.get('audit', {}).get('deterministic_rerun_required', True))}",
        f"- Deterministic rerun passed: `{bool(comparison.get('passed', False))}`",
        "",
        "## Golden Days",
        "",
    ]
    golden_display = golden_frame[
        [
            "selection_rank",
            "trade_date",
            "selection_reason",
            "matched_categories",
            "status",
            "alert_count",
            "is_holiday_edge",
        ]
    ]
    lines.append(golden_display.to_markdown(index=False))
    lines.extend(
        [
            "",
            "## Audit Summary",
            "",
            summary_frame[
                [
                    "selection_rank",
                    "trade_date",
                    "status",
                    "selected_names_count",
                    "gross_exposure",
                    "expected_cost_bps",
                    "shadow_net_return",
                    "alert_count",
                    "triggered_gates_count",
                    "rerun_match",
                ]
            ].to_markdown(index=False),
            "",
            "## Human Review Checklist",
            "",
            "- `summary.md` が status / top longs / alerts を自然に説明しているかを確認する",
            "- `signals.csv` と `orders_shadow.csv` の selected names / target weights が整合しているかを見る",
            "- `fills_shadow.csv` と `pnl.csv` で same-day open/close two-fill assumption が意図どおり反映されているかを見る",
            "- `alerts.json` と `risk_report.json` の triggered gate / scaling alert が想定どおりかを確認する",
        ]
    )
    if comparison.get("mismatches"):
        lines.extend(["", "## Deterministic Rerun Mismatches", ""])
        for trade_date in comparison["mismatches"]:
            lines.append(f"- {trade_date}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
