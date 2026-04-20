from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from leadlag.config.models import AppConfig
from leadlag.runtime.corrected_shadow import build_corrected_shadow_day_preview


SCALE_ALERT_CODES = {
    "scaled_for_single_name_cap",
    "scaled_for_gross_cap",
    "gross_exposure_exceeded",
    "max_single_name_abs_exceeded",
}

REQUIRED_AUDIT_SUMMARY_COLUMNS = [
    "trade_date",
    "selection_reason",
    "asof_us_date",
    "status",
    "selected_names_count",
    "gross_exposure",
    "expected_cost_bps",
    "shadow_net_return",
    "alert_count",
    "triggered_gates_count",
    "packet_path",
    "stable_fingerprint",
    "rerun_match",
]


def load_simulator_contract(path: Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        contract = yaml.safe_load(handle)
    if not isinstance(contract, dict):
        raise ValueError(f"simulator contract must be a mapping: {path}")
    return contract


def build_shadow_day_preview(
    cfg: AppConfig,
    prepared: dict[str, Any],
    trade_date: pd.Timestamp,
    *,
    holiday_gap_days: int = 4,
) -> dict[str, Any]:
    trade_date = pd.Timestamp(trade_date)
    preview = build_corrected_shadow_day_preview(cfg, prepared, trade_date_override=trade_date.date().isoformat())
    valid_dates = _valid_trade_dates(prepared)
    alert_codes = [str(alert.get("code", "")) for alert in preview["alerts"]]
    triggered_gate_codes = [
        code
        for code, payload in preview["gate_result"]["gate_results"].items()
        if bool(payload.get("triggered"))
    ]
    return {
        "trade_date": preview["trade_date"].date().isoformat(),
        "asof_us_date": preview["us_date"].date().isoformat(),
        "status": str(preview["gate_result"]["status"]),
        "tradable_names": int(preview["gate_result"]["tradable_names"]),
        "selected_names": int(preview["gate_result"]["selected_names"]),
        "gross_exposure": float(preview["gate_result"]["gross_exposure"]),
        "net_exposure": float(preview["gate_result"]["net_exposure"]),
        "expected_cost_bps": float(preview["expected_cost_bps"]),
        "alert_codes": alert_codes,
        "alert_count": len(alert_codes),
        "triggered_gate_codes": triggered_gate_codes,
        "triggered_gates_count": len(triggered_gate_codes),
        "paper_counterfactual_return": preview["paper_counterfactual_return"],
        "sample_filter_start": preview["sample"].start.date().isoformat(),
        "sample_filter_end": preview["sample"].end.date().isoformat(),
        "sample_filter_exact": bool(preview["sample"].exact_match),
        "is_holiday_edge": _is_holiday_edge(valid_dates, preview["trade_date"], holiday_gap_days),
    }


def select_golden_days(
    cfg: AppConfig,
    prepared: dict[str, Any],
    contract: dict[str, Any],
) -> list[dict[str, Any]]:
    audit_cfg = contract.get("audit", {})
    min_golden_days = int(audit_cfg.get("min_golden_days", 5))
    candidate_pool_recent_n = int(audit_cfg.get("candidate_pool_recent_n", 20))
    fallback_pool_recent_n = int(audit_cfg.get("fallback_pool_recent_n", 60))
    holiday_gap_days = int(audit_cfg.get("holiday_gap_days", 4))

    valid_dates = _valid_trade_dates(prepared)
    if len(valid_dates) == 0:
        raise RuntimeError("No valid trade dates available for simulator audit.")

    candidate_dates = pd.DatetimeIndex(valid_dates[-candidate_pool_recent_n:]).sort_values().unique()
    fallback_dates = pd.DatetimeIndex(valid_dates[-fallback_pool_recent_n:]).sort_values().unique()
    preview_cache: dict[str, dict[str, Any]] = {}

    def get_preview(trade_date: pd.Timestamp) -> dict[str, Any]:
        key = pd.Timestamp(trade_date).date().isoformat()
        if key not in preview_cache:
            preview_cache[key] = build_shadow_day_preview(
                cfg,
                prepared,
                pd.Timestamp(trade_date),
                holiday_gap_days=holiday_gap_days,
            )
        return preview_cache[key]

    candidate_previews = [get_preview(trade_date) for trade_date in candidate_dates]
    selected: list[dict[str, Any]] = []
    selected_by_date: dict[str, dict[str, Any]] = {}

    def add_selection(preview: dict[str, Any] | None, reason: str) -> None:
        if preview is None:
            return
        trade_date = preview["trade_date"]
        if trade_date in selected_by_date:
            selected_by_date[trade_date]["matched_categories"].append(reason)
            return
        row = {
            "trade_date": trade_date,
            "selection_reason": reason,
            "matched_categories": [reason],
            "status": preview["status"],
            "alert_count": preview["alert_count"],
            "alert_codes": preview["alert_codes"],
            "triggered_gates_count": preview["triggered_gates_count"],
            "triggered_gate_codes": preview["triggered_gate_codes"],
            "is_holiday_edge": preview["is_holiday_edge"],
        }
        selected.append(row)
        selected_by_date[trade_date] = row

    def latest_match(predicate) -> dict[str, Any] | None:
        for preview in reversed(candidate_previews):
            if predicate(preview):
                return preview
        return None

    latest_valid = candidate_previews[-1] if candidate_previews else None
    latest_trade_date = latest_valid["trade_date"] if latest_valid is not None else None
    add_selection(latest_valid, "latest_valid")
    add_selection(
        latest_match(lambda preview: preview["trade_date"] != latest_trade_date and preview["status"] == "GO"),
        "earlier_go",
    )
    add_selection(latest_match(lambda preview: preview["alert_count"] > 0), "nonzero_alert")
    add_selection(
        latest_match(lambda preview: any(code in SCALE_ALERT_CODES for code in preview["alert_codes"])),
        "scaling_or_cap_alert",
    )
    add_selection(latest_match(lambda preview: preview["is_holiday_edge"]), "holiday_edge")

    evenly_spaced_dates = _evenly_spaced_dates(
        fallback_dates,
        count=min(len(fallback_dates), max(min_golden_days * 3, min_golden_days)),
    )
    for trade_date in evenly_spaced_dates:
        if len(selected) >= min_golden_days:
            break
        add_selection(get_preview(trade_date), "fallback_evenly_spaced")

    if len(selected) < min_golden_days:
        for trade_date in fallback_dates:
            if len(selected) >= min_golden_days:
                break
            add_selection(get_preview(trade_date), "fallback_recent")

    for index, row in enumerate(selected, start=1):
        row["selection_rank"] = index
        row["matched_categories"] = ";".join(row["matched_categories"])
        row["alert_codes"] = ";".join(str(code) for code in row["alert_codes"])
        row["triggered_gate_codes"] = ";".join(str(code) for code in row["triggered_gate_codes"])

    return selected


def extract_packet_audit_row(packet_dir: Path, relative_packet_path: str) -> dict[str, Any]:
    packet_dir = Path(packet_dir)
    run_payload = _read_json(packet_dir / "run.json")
    risk_payload = _read_json(packet_dir / "risk_report.json")
    alerts_payload = _read_json(packet_dir / "alerts.json")
    alerts = list(alerts_payload.get("alerts", []))
    gate_results = dict(risk_payload.get("gate_results", {}))
    triggered_gate_codes = sorted(code for code, payload in gate_results.items() if bool(payload.get("triggered")))
    return {
        "trade_date": str(run_payload.get("trade_date")),
        "asof_us_date": str(run_payload.get("asof_us_date")),
        "status": str(run_payload.get("run_status", risk_payload.get("status"))),
        "selected_names_count": int(risk_payload.get("selected_names", 0)),
        "gross_exposure": float(risk_payload.get("gross_exposure", 0.0)),
        "expected_cost_bps": float(run_payload.get("expected_cost_bps", risk_payload.get("expected_cost_bps", 0.0))),
        "shadow_net_return": float(run_payload.get("shadow_net_return", 0.0)),
        "alert_count": len(alerts),
        "triggered_gates_count": len(triggered_gate_codes),
        "packet_path": relative_packet_path.replace("\\", "/"),
        "alert_codes": ";".join(str(alert.get("code", "")) for alert in alerts),
        "triggered_gate_codes": ";".join(triggered_gate_codes),
    }


def fingerprint_packet(packet_dir: Path, contract: dict[str, Any]) -> dict[str, Any]:
    packet_dir = Path(packet_dir)
    audit_cfg = contract.get("audit", {})
    fingerprint_cfg = audit_cfg.get("fingerprint_files", {})
    volatile_run_json_fields = set(audit_cfg.get("volatile_run_json_fields", []))

    file_hashes: dict[str, str] = {}
    for filename in fingerprint_cfg.get("raw_csv", []):
        path = packet_dir / filename
        file_hashes[filename] = _sha256_bytes(path.read_bytes())

    for filename in fingerprint_cfg.get("normalized_json", []):
        path = packet_dir / filename
        payload = _read_json(path)
        if filename == "run.json":
            payload = _strip_volatile_fields(payload, volatile_run_json_fields)
        normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        file_hashes[filename] = _sha256_bytes(normalized)

    combined_blob = "\n".join(f"{name}:{file_hashes[name]}" for name in sorted(file_hashes)).encode("utf-8")
    return {
        "stable_fingerprint": _sha256_bytes(combined_blob),
        "files": file_hashes,
        "volatile_run_json_fields": sorted(volatile_run_json_fields),
    }


def compare_fingerprint_sets(primary: dict[str, Any], rerun: dict[str, Any]) -> dict[str, Any]:
    trade_dates = sorted(set(primary) | set(rerun))
    per_trade_date: dict[str, Any] = {}
    mismatches: list[str] = []
    missing_primary: list[str] = []
    missing_rerun: list[str] = []

    for trade_date in trade_dates:
        primary_payload = primary.get(trade_date)
        rerun_payload = rerun.get(trade_date)
        if primary_payload is None:
            missing_primary.append(trade_date)
            per_trade_date[trade_date] = {"match": False, "reason": "missing_primary"}
            mismatches.append(trade_date)
            continue
        if rerun_payload is None:
            missing_rerun.append(trade_date)
            per_trade_date[trade_date] = {"match": False, "reason": "missing_rerun"}
            mismatches.append(trade_date)
            continue
        match = (
            primary_payload.get("stable_fingerprint") == rerun_payload.get("stable_fingerprint")
            and primary_payload.get("files") == rerun_payload.get("files")
        )
        per_trade_date[trade_date] = {
            "match": match,
            "primary_fingerprint": primary_payload.get("stable_fingerprint"),
            "rerun_fingerprint": rerun_payload.get("stable_fingerprint"),
        }
        if not match:
            mismatches.append(trade_date)

    return {
        "passed": not mismatches,
        "trade_dates": trade_dates,
        "missing_primary": missing_primary,
        "missing_rerun": missing_rerun,
        "mismatches": mismatches,
        "per_trade_date": per_trade_date,
    }


def build_audit_summary_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    for column in REQUIRED_AUDIT_SUMMARY_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.NA
    extra_columns = [column for column in frame.columns if column not in REQUIRED_AUDIT_SUMMARY_COLUMNS]
    return frame[REQUIRED_AUDIT_SUMMARY_COLUMNS + extra_columns]


def _valid_trade_dates(prepared: dict[str, Any]) -> pd.DatetimeIndex:
    strategy_output = prepared["strategy_output"]
    valid_dates = pd.DatetimeIndex(strategy_output.returns.dropna().index).sort_values().unique()
    sample_dates = pd.DatetimeIndex(prepared["sample_dates"]).sort_values().unique()
    return valid_dates.intersection(sample_dates)


def _is_holiday_edge(valid_dates: pd.DatetimeIndex, trade_date: pd.Timestamp, gap_days: int) -> bool:
    trade_date = pd.Timestamp(trade_date)
    position = valid_dates.get_indexer([trade_date])[0]
    if position <= 0:
        return False
    previous_date = pd.Timestamp(valid_dates[position - 1])
    return int((trade_date - previous_date).days) >= gap_days


def _evenly_spaced_dates(dates: pd.DatetimeIndex, count: int) -> list[pd.Timestamp]:
    if len(dates) == 0 or count <= 0:
        return []
    target_count = min(len(dates), count)
    raw_indices = np.linspace(0, len(dates) - 1, num=target_count)
    seen: list[int] = []
    for index in np.round(raw_indices).astype(int).tolist():
        if index not in seen:
            seen.append(index)
    if len(seen) < target_count:
        for index in range(len(dates)):
            if index not in seen:
                seen.append(index)
            if len(seen) >= target_count:
                break
    return [pd.Timestamp(dates[index]) for index in seen]


def _strip_volatile_fields(payload: Any, volatile_fields: set[str]) -> Any:
    if isinstance(payload, dict):
        return {
            key: _strip_volatile_fields(value, volatile_fields)
            for key, value in sorted(payload.items())
            if key not in volatile_fields
        }
    if isinstance(payload, list):
        return [_strip_volatile_fields(item, volatile_fields) for item in payload]
    return payload


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()
