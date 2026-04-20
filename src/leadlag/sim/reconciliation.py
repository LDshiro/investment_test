from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json
from typing import Any

import pandas as pd

from leadlag.sim.models import ReconciliationResult


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    return float(value)


def _load_single_row_csv(path: Path) -> pd.Series:
    frame = pd.read_csv(path)
    if frame.empty:
        raise ValueError(f"Expected at least one row in {path}")
    return frame.iloc[0]


def reconcile_shadow_packet(
    packet_dir: Path,
    *,
    tolerance_net_return_bps: float = 1.0,
    fail_on_tolerance_breach: bool = False,
) -> ReconciliationResult:
    legacy_pnl = _load_single_row_csv(packet_dir / "pnl.csv")
    canonical_pnl = _load_single_row_csv(packet_dir / "canonical_pnl.csv")

    risk_payload = json.loads((packet_dir / "risk_report.json").read_text(encoding="utf-8"))
    legacy_gross_exposure = _safe_float(risk_payload.get("gross_exposure")) or 0.0
    canonical_gross_exposure = _safe_float(canonical_pnl.get("gross_exposure")) or 0.0

    legacy_net_return = _safe_float(legacy_pnl.get("net_return")) or 0.0
    canonical_net_return = _safe_float(canonical_pnl.get("net_return")) or 0.0
    net_return_diff = canonical_net_return - legacy_net_return
    net_return_diff_bps = net_return_diff * 10000.0
    legacy_cost_return = _safe_float(legacy_pnl.get("cost_return"))
    canonical_cost_return = _safe_float(canonical_pnl.get("cost_return")) or 0.0

    gross_return_diff = (_safe_float(canonical_pnl.get("gross_return")) or 0.0) - (_safe_float(legacy_pnl.get("gross_return")) or 0.0)
    cost_return_diff = canonical_cost_return - (legacy_cost_return or 0.0)

    within_tolerance = abs(net_return_diff_bps) <= tolerance_net_return_bps
    if within_tolerance:
        status = "PASS"
    elif fail_on_tolerance_breach:
        status = "FAIL"
    else:
        status = "WARN"

    notes = [
        "Legacy shadow embeds execution cost into assumed fill prices; canonical_v1 records execution cost as separate cash cost.",
        (
            f"Gross return diff: {gross_return_diff * 10000.0:.4f} bps; "
            f"cost return diff: {cost_return_diff * 10000.0:.4f} bps."
        ),
    ]
    if not within_tolerance:
        notes.append(
            f"Net return diff {net_return_diff_bps:.4f} bps exceeded tolerance {tolerance_net_return_bps:.4f} bps."
        )

    diagnostics = {
        "gross_return_diff": gross_return_diff,
        "gross_return_diff_bps": gross_return_diff * 10000.0,
        "cost_return_diff": cost_return_diff,
        "cost_return_diff_bps": cost_return_diff * 10000.0,
        "legacy_borrow_pnl_jpy": _safe_float(legacy_pnl.get("borrow_pnl_jpy")),
        "canonical_borrow_cost_jpy": _safe_float(canonical_pnl.get("borrow_cost_jpy")),
    }

    return ReconciliationResult(
        trade_date=str(canonical_pnl.get("trade_date") or canonical_pnl.get("date") or legacy_pnl.get("date")),
        legacy_net_return=legacy_net_return,
        canonical_net_return=canonical_net_return,
        net_return_diff=net_return_diff,
        net_return_diff_bps=net_return_diff_bps,
        legacy_gross_exposure=legacy_gross_exposure,
        canonical_gross_exposure=canonical_gross_exposure,
        legacy_cost_return=legacy_cost_return,
        canonical_cost_return=canonical_cost_return,
        status=status,
        notes=notes,
        tolerance_net_return_bps=tolerance_net_return_bps,
        within_tolerance=within_tolerance,
        diagnostics=diagnostics,
    )


def reconciliation_frame(result: ReconciliationResult) -> pd.DataFrame:
    payload = asdict(result)
    payload["notes"] = " | ".join(result.notes)
    payload["diagnostics"] = json.dumps(result.diagnostics, ensure_ascii=False, sort_keys=True)
    return pd.DataFrame([payload])


def reconciliation_payload(result: ReconciliationResult) -> dict[str, Any]:
    return asdict(result)


def reconciliation_markdown(result: ReconciliationResult) -> str:
    lines = [
        "# Simulation Reconciliation",
        "",
        f"- trade_date: `{result.trade_date}`",
        f"- status: `{result.status}`",
        f"- within_tolerance: `{result.within_tolerance}`",
        f"- tolerance_net_return_bps: `{result.tolerance_net_return_bps}`",
        "",
        "## Summary",
        "",
        f"- legacy_net_return: `{result.legacy_net_return:.10f}`",
        f"- canonical_net_return: `{result.canonical_net_return:.10f}`",
        f"- net_return_diff_bps: `{result.net_return_diff_bps:.6f}`",
        f"- legacy_gross_exposure: `{result.legacy_gross_exposure:.6f}`",
        f"- canonical_gross_exposure: `{result.canonical_gross_exposure:.6f}`",
        f"- legacy_cost_return: `{result.legacy_cost_return if result.legacy_cost_return is not None else 'n/a'}`",
        f"- canonical_cost_return: `{result.canonical_cost_return:.10f}`",
        "",
        "## Notes",
        "",
    ]
    for note in result.notes:
        lines.append(f"- {note}")
    return "\n".join(lines) + "\n"


def write_reconciliation_outputs(result: ReconciliationResult, output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "sim_reconciliation.csv"
    json_path = output_dir / "sim_reconciliation.json"
    md_path = output_dir / "sim_reconciliation.md"
    reconciliation_frame(result).to_csv(csv_path, index=False)
    json_path.write_text(json.dumps(reconciliation_payload(result), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(reconciliation_markdown(result), encoding="utf-8")
    return {
        "csv": str(csv_path),
        "json": str(json_path),
        "md": str(md_path),
    }
