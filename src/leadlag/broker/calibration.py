from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
import argparse
import json
import re

import pandas as pd
from pandas.errors import EmptyDataError

from leadlag.security.redaction import redact_inline_secret_assignments

from .models import BrokerMode
from .packet_dryrun import BrokerDryRunError, intent_from_order_row, load_packet_order_inputs
from .validation import BrokerConfigError, load_broker_dryrun_calibration_config


REPO_ROOT = Path(__file__).resolve().parents[3]
CLOSE_LEG_FIELDS = {
    "close_side",
    "intended_close_qty",
    "open_price_adj",
    "close_price_adj",
    "target_weight",
}
SENSITIVE_ASSIGNMENT_RE = re.compile(
    r'(?i)(?P<key>"?(?:[\w.-]*?(?:api[_-]?key|token|secret|password|private[_-]?key|kabu_[\w.-]*|ibkr_[\w.-]*)[\w.-]*)"?)[\s]*[:=][\s]*(?P<value>"[^"]*"|\'[^\']*\'|[^\s,;]+)'
)


class BrokerDryRunCalibrationError(RuntimeError):
    pass


@dataclass(slots=True)
class CalibrationIssue:
    severity: str
    code: str
    message: str
    source_name: str | None = None
    trade_date: str | None = None
    details: dict[str, Any] | None = None


@dataclass(slots=True)
class CalibrationResult:
    status: str
    passed: bool
    summary: dict[str, Any]
    issues: list[CalibrationIssue] = field(default_factory=list)
    output_paths: dict[str, str] = field(default_factory=dict)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_repo_path(path_value: str | Path | None) -> Path | None:
    if path_value is None:
        return None
    path = Path(path_value)
    if path.is_absolute():
        return path.resolve(strict=False)
    return (REPO_ROOT / path).resolve(strict=False)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv_allow_empty(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except EmptyDataError:
        return pd.DataFrame()


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise BrokerDryRunCalibrationError(f"expected JSON list at {path}")
    return [item for item in payload if isinstance(item, dict)]


def _normalize_text(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def _normalize_number(value: Any) -> str | None:
    if value is None or value == "":
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric == 0.0:
        return "0"
    return format(numeric, ".12g")


def intent_fingerprint(record: Mapping[str, Any]) -> str:
    payload = {
        "trade_date": _normalize_text(record.get("trade_date")),
        "symbol": _normalize_text(record.get("symbol")),
        "side": _normalize_text(record.get("side")),
        "order_type": _normalize_text(record.get("order_type")),
        "tif": _normalize_text(record.get("tif")),
        "quantity": _normalize_number(record.get("quantity")),
        "notional_jpy": _normalize_number(record.get("notional_jpy")),
        "strategy_id": _normalize_text(record.get("strategy_id")),
        "run_id": _normalize_text(record.get("run_id")),
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return sha256(serialized.encode("utf-8")).hexdigest()


def _issue_severity(code: str, config: dict[str, Any], default: str = "ERROR") -> str:
    status_policy = config.get("status_policy", {})
    if code in set(status_policy.get("fail_on", [])):
        return "ERROR"
    if code in set(status_policy.get("warn_on", [])):
        return "WARN"
    return default


def _make_issue(
    code: str,
    message: str,
    *,
    config: dict[str, Any],
    source_name: str | None = None,
    trade_date: str | None = None,
    details: dict[str, Any] | None = None,
    default: str = "ERROR",
) -> CalibrationIssue:
    return CalibrationIssue(
        severity=_issue_severity(code, config, default),
        code=code,
        message=message,
        source_name=source_name,
        trade_date=trade_date,
        details=details,
    )


def _counter_diff(left: list[str], right: list[str]) -> int:
    return int(sum((Counter(left) - Counter(right)).values()))


def _duplicate_count(items: list[str]) -> int:
    counter = Counter(items)
    return int(sum(count - 1 for count in counter.values() if count > 1))


def _notional_from_shadow_row(row: pd.Series) -> float | None:
    target = row.get("target_notional_jpy")
    if target is not None and not pd.isna(target):
        return float(target)
    quantity = row.get("intended_open_qty")
    open_price = row.get("open_price_adj")
    if quantity is None or open_price is None or pd.isna(quantity) or pd.isna(open_price):
        return None
    return float(quantity) * float(open_price)


def _shadow_row_record(row: pd.Series, run_meta: dict[str, Any]) -> dict[str, Any]:
    expected = intent_from_order_row(
        row,
        run_meta=run_meta,
        packet_path=run_meta.get("source_packet_path") or "",
    )
    return {
        "run_id": expected.run_id,
        "trade_date": expected.trade_date,
        "symbol": expected.symbol,
        "side": expected.side.value,
        "order_type": expected.order_type.value,
        "tif": expected.tif.value,
        "quantity": expected.quantity,
        "notional_jpy": expected.notional_jpy,
        "strategy_id": expected.strategy_id,
    }


def _intent_row_record(row: pd.Series) -> tuple[dict[str, Any] | None, list[str]]:
    required = ["run_id", "trade_date", "symbol", "side", "order_type", "tif"]
    missing = [key for key in required if _normalize_text(row.get(key)) is None]
    if _normalize_number(row.get("quantity")) is None and _normalize_number(row.get("notional_jpy")) is None:
        missing.append("quantity_or_notional")
    if _normalize_text(row.get("strategy_id")) is None:
        missing.append("strategy_id")
    if missing:
        return None, missing
    return {
        "run_id": row.get("run_id"),
        "trade_date": row.get("trade_date"),
        "symbol": row.get("symbol"),
        "side": row.get("side"),
        "order_type": row.get("order_type"),
        "tif": row.get("tif"),
        "quantity": row.get("quantity"),
        "notional_jpy": row.get("notional_jpy"),
        "strategy_id": row.get("strategy_id"),
    }, []


def _payload_record(item: dict[str, Any], day_context: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    required = ["symbol", "side", "order_type", "tif"]
    missing = [key for key in required if _normalize_text(item.get(key)) is None]
    if _normalize_number(item.get("quantity")) is None and _normalize_number(item.get("notional_jpy")) is None:
        missing.append("quantity_or_notional")
    if missing:
        return None, missing
    return {
        "run_id": day_context.get("run_id"),
        "trade_date": day_context.get("trade_date"),
        "symbol": item.get("symbol"),
        "side": item.get("side"),
        "order_type": item.get("order_type"),
        "tif": item.get("tif"),
        "quantity": item.get("quantity"),
        "notional_jpy": item.get("notional_jpy"),
        "strategy_id": day_context.get("strategy_id"),
    }, []


def _ack_record(item: dict[str, Any], day_context: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    payload = item.get("metadata", {}).get("payload", {})
    if not isinstance(payload, dict):
        return None, ["metadata.payload"]
    required = ["symbol", "side", "order_type", "tif"]
    missing = [key for key in required if _normalize_text(payload.get(key)) is None]
    if _normalize_number(payload.get("quantity")) is None and _normalize_number(payload.get("notional_jpy")) is None:
        missing.append("quantity_or_notional")
    if missing:
        return None, missing
    return {
        "run_id": day_context.get("run_id"),
        "trade_date": day_context.get("trade_date"),
        "symbol": payload.get("symbol"),
        "side": payload.get("side"),
        "order_type": payload.get("order_type"),
        "tif": payload.get("tif"),
        "quantity": payload.get("quantity"),
        "notional_jpy": payload.get("notional_jpy"),
        "strategy_id": day_context.get("strategy_id"),
    }, []


def _close_leg_metadata_only_for_payload(item: dict[str, Any]) -> bool:
    payload = item.get("payload", {})
    if not isinstance(payload, dict):
        return False
    if any(field in payload for field in CLOSE_LEG_FIELDS):
        return False
    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict):
        return False
    return all(field not in item for field in CLOSE_LEG_FIELDS)


def _close_leg_metadata_only_for_ack(item: dict[str, Any]) -> bool:
    metadata = item.get("metadata", {})
    if not isinstance(metadata, dict):
        return False
    payload = metadata.get("payload", {})
    if not isinstance(payload, dict):
        return False
    if any(field in payload for field in CLOSE_LEG_FIELDS):
        return False
    nested = payload.get("metadata", {})
    if not isinstance(nested, dict):
        return False
    return all(field not in item for field in CLOSE_LEG_FIELDS)


def _allow_live_submission_detected(intents_df: pd.DataFrame, payloads: list[dict[str, Any]], acks: list[dict[str, Any]]) -> bool:
    if "allow_live_submission" in intents_df.columns:
        for value in intents_df["allow_live_submission"].tolist():
            if str(value).strip().lower() == "true":
                return True
    for item in payloads:
        if bool(item.get("payload", {}).get("allow_live_submission")):
            return True
    for item in acks:
        if bool(item.get("metadata", {}).get("payload", {}).get("allow_live_submission")):
            return True
    return False


def _detect_mode(broker_modes: list[str], allowed_modes: set[str]) -> bool:
    return any(mode not in allowed_modes for mode in broker_modes if mode)


def _sensitive_assignment_present(text: str) -> bool:
    for match in SENSITIVE_ASSIGNMENT_RE.finditer(text):
        value = match.group("value").strip().strip("\"'")
        if value and value.lower() not in {"null", "none", "***redacted***"}:
            return True
    return False


def _scan_sensitive_values(paths: list[Path]) -> list[str]:
    findings: list[str] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if _sensitive_assignment_present(text):
            findings.append(str(path))
    return findings


def _source_markdown(source_summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {source_summary['source_name'].title()} Calibration Summary",
            "",
            f"- status: `{source_summary['status']}`",
            f"- completed_days: `{source_summary['completed_days']}`",
            f"- failed_days: `{source_summary['failed_days']}`",
            f"- shadow_order_count_total: `{source_summary['shadow_order_count_total']}`",
            f"- intent_count_total: `{source_summary['intent_count_total']}`",
            f"- ack_count_total: `{source_summary['ack_count_total']}`",
            f"- reject_count_total: `{source_summary['reject_count_total']}`",
            f"- unmatched_shadow_order_count: `{source_summary['unmatched_shadow_order_count']}`",
            f"- unmatched_intent_count: `{source_summary['unmatched_intent_count']}`",
            f"- missing_required_field_count: `{source_summary['missing_required_field_count']}`",
            f"- duplicate_intent_fingerprint_count: `{source_summary['duplicate_intent_fingerprint_count']}`",
            f"- paper_or_live_mode_detected: `{source_summary['paper_or_live_mode_detected']}`",
            f"- real_broker_connection_detected: `{source_summary['real_broker_connection_detected']}`",
            f"- credential_like_value_detected: `{source_summary['credential_like_value_detected']}`",
            f"- open_leg_only_submission_passed: `{source_summary['open_leg_only_submission_passed']}`",
            f"- close_leg_metadata_only_passed: `{source_summary['close_leg_metadata_only_passed']}`",
            f"- fingerprint_determinism_passed: `{source_summary['fingerprint_determinism_passed']}`",
            "",
        ]
    )


def _overall_markdown(summary: dict[str, Any]) -> str:
    legacy = summary["sources"].get("legacy")
    canonical = summary["sources"].get("canonical")
    return "\n".join(
        [
            "# Broker Dry-Run Calibration Summary",
            "",
            f"- overall status: `{summary['status']}`",
            f"- legacy status: `{legacy['status'] if legacy else 'not_provided'}`",
            f"- canonical status: `{canonical['status'] if canonical else 'not_provided'}`",
            f"- legacy totals (shadow/intents/acks/rejects): `{legacy['shadow_order_count_total'] if legacy else 0}` / `{legacy['intent_count_total'] if legacy else 0}` / `{legacy['ack_count_total'] if legacy else 0}` / `{legacy['reject_count_total'] if legacy else 0}`",
            f"- canonical totals (shadow/intents/acks/rejects): `{canonical['shadow_order_count_total'] if canonical else 0}` / `{canonical['intent_count_total'] if canonical else 0}` / `{canonical['ack_count_total'] if canonical else 0}` / `{canonical['reject_count_total'] if canonical else 0}`",
            f"- unmatched counts (legacy/canonical shadow): `{legacy['unmatched_shadow_order_count'] if legacy else 0}` / `{canonical['unmatched_shadow_order_count'] if canonical else 0}`",
            f"- unmatched counts (legacy/canonical intent): `{legacy['unmatched_intent_count'] if legacy else 0}` / `{canonical['unmatched_intent_count'] if canonical else 0}`",
            f"- missing field counts (legacy/canonical): `{legacy['missing_required_field_count'] if legacy else 0}` / `{canonical['missing_required_field_count'] if canonical else 0}`",
            "- safety guarantees:",
            f"  - null broker only: `{'yes' if summary['safety_guarantees']['null_broker_only'] else 'no'}`",
            f"  - real broker connection detected: `{'yes' if summary['safety_guarantees']['real_broker_connection_detected'] else 'no'}`",
            f"  - paper/live mode detected: `{'yes' if summary['safety_guarantees']['paper_or_live_mode_detected'] else 'no'}`",
            f"  - credential-like value detected: `{'yes' if summary['safety_guarantees']['credential_like_value_detected'] else 'no'}`",
            "- whether PASS means live-ready: `no`",
            f"- human action required: `{'yes' if summary['human_action_required'] else 'no'}`",
            "",
        ]
    )


def _day_status(issues: list[CalibrationIssue]) -> str:
    severities = {issue.severity for issue in issues}
    if "ERROR" in severities:
        return "FAIL"
    if "WARN" in severities:
        return "WARN"
    return "PASS"


def _source_status(issues: list[CalibrationIssue], source_summary: dict[str, Any]) -> str:
    if source_summary["failed_days"] > 0:
        return "FAIL"
    severities = {issue.severity for issue in issues}
    if "ERROR" in severities:
        return "FAIL"
    if "WARN" in severities:
        return "WARN"
    return "PASS"


def _resolve_source(source_name: str, shadow_ops_dir: str | Path, config: dict[str, Any]) -> tuple[dict[str, Any], list[CalibrationIssue]]:
    source_root = Path(shadow_ops_dir).resolve()
    if not source_root.exists():
        raise BrokerDryRunCalibrationError(f"{source_name} shadow-ops dir not found: {source_root}")
    summary_path = source_root / "shadow_ops_summary.json"
    if not summary_path.exists():
        raise BrokerDryRunCalibrationError(f"{source_name} shadow_ops_summary.json not found: {summary_path}")
    shadow_summary = _load_json(summary_path)
    broker_output = shadow_summary.get("broker_dryrun", {}).get("output_dir")
    issues: list[CalibrationIssue] = []
    if broker_output:
        broker_dir = Path(str(broker_output)).resolve()
    else:
        broker_dir = source_root / "stages" / "broker_dryrun"
        issues.append(
            _make_issue(
                "source_artifact_layout_unrecognized_but_recoverable",
                "broker_dryrun.output_dir missing from shadow_ops_summary.json; used fallback stage path.",
                config=config,
                source_name=source_name,
                default="WARN",
            )
        )
    if not broker_dir.exists():
        raise BrokerDryRunCalibrationError(f"{source_name} broker dry-run output dir not found: {broker_dir}")
    return {
        "source_name": source_name,
        "shadow_ops_dir": str(source_root),
        "broker_dryrun_dir": str(broker_dir.resolve()),
        "shadow_ops_summary": shadow_summary,
    }, issues


def _calibrate_source(source_name: str, shadow_ops_dir: str | Path, config: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], list[CalibrationIssue]]:
    source_info, source_issues = _resolve_source(source_name, shadow_ops_dir, config)
    broker_dir = Path(source_info["broker_dryrun_dir"])
    summary_df = _read_csv_allow_empty(broker_dir / "broker_dryrun_summary.csv")
    if summary_df.empty:
        raise BrokerDryRunCalibrationError(f"{source_name} broker_dryrun_summary.csv is missing or empty: {broker_dir}")
    summary_json = _load_json(broker_dir / "broker_dryrun_summary.json")
    _load_json(broker_dir / "broker_dryrun_validation.json")

    allowed_broker_ids = set(config["allowed_broker_ids"])
    allowed_modes = set(config["allowed_modes"])

    day_rows: list[dict[str, Any]] = []
    all_issues: list[CalibrationIssue] = list(source_issues)
    total_shadow_orders = 0
    total_intents = 0
    total_acks = 0
    total_rejects = 0
    total_unmatched_shadow = 0
    total_unmatched_intent = 0
    total_missing_required = 0
    total_duplicate_fingerprints = 0
    paper_or_live_mode_detected = False
    real_broker_connection_detected = False
    credential_like_value_detected = False
    open_leg_only_submission_passed = True
    close_leg_metadata_only_passed = True
    fingerprint_determinism_passed = True
    completed_days = 0
    failed_days = 0

    for _, summary_row in summary_df.iterrows():
        trade_date = str(summary_row.get("trade_date"))
        packet_dir_value = summary_row.get("packet_dir")
        packet_dir = _resolve_repo_path(packet_dir_value) if packet_dir_value else None
        issues_for_day: list[CalibrationIssue] = []
        day_dir = broker_dir / "daily" / trade_date
        intents_path = day_dir / "broker_order_intents.csv"
        payloads_path = day_dir / "broker_payloads.json"
        acks_path = day_dir / "broker_acks.json"
        diagnostics_path = day_dir / "broker_diagnostics.json"

        if packet_dir is None or not packet_dir.exists():
            issues_for_day.append(
                _make_issue(
                    "shadow_packet_missing",
                    "shadow packet directory referenced by broker dry-run summary could not be found.",
                    config=config,
                    source_name=source_name,
                    trade_date=trade_date,
                    details={"packet_dir": None if packet_dir is None else str(packet_dir)},
                )
            )
            shadow_orders_df = pd.DataFrame()
            run_meta = {"run_id": None, "trade_date": trade_date, "strategy": None}
        else:
            try:
                _, run_meta, shadow_orders_df = load_packet_order_inputs(packet_dir, allow_empty_orders=True)
            except BrokerDryRunError as exc:
                issues_for_day.append(
                    _make_issue(
                        "shadow_packet_missing",
                        f"could not read shadow packet inputs: {exc}",
                        config=config,
                        source_name=source_name,
                        trade_date=trade_date,
                    )
                )
                shadow_orders_df = pd.DataFrame()
                run_meta = {"run_id": None, "trade_date": trade_date, "strategy": None}

        if not intents_path.exists() or not payloads_path.exists() or not acks_path.exists() or not diagnostics_path.exists():
            issues_for_day.append(
                _make_issue(
                    "broker_dryrun_artifacts_missing",
                    "one or more expected daily broker dry-run artifacts are missing.",
                    config=config,
                    source_name=source_name,
                    trade_date=trade_date,
                    details={
                        "intents_path": str(intents_path),
                        "payloads_path": str(payloads_path),
                        "acks_path": str(acks_path),
                        "diagnostics_path": str(diagnostics_path),
                    },
                )
            )

        intents_df = _read_csv_allow_empty(intents_path) if intents_path.exists() else pd.DataFrame()
        payloads = _read_json_list(payloads_path) if payloads_path.exists() else []
        acks = _read_json_list(acks_path) if acks_path.exists() else []
        diagnostics = _read_json_list(diagnostics_path) if diagnostics_path.exists() else []

        day_context = {
            "run_id": run_meta.get("run_id"),
            "trade_date": str(run_meta.get("trade_date") or trade_date),
            "strategy_id": run_meta.get("strategy"),
        }

        shadow_fingerprints: list[str] = []
        intent_fingerprints: list[str] = []
        payload_fingerprints: list[str] = []
        ack_fingerprints: list[str] = []

        shadow_order_count = int(len(shadow_orders_df))
        intent_count = int(len(intents_df))
        ack_count = int(len(acks))
        reject_count = int(summary_row.get("reject_count") or 0)
        day_missing_required_count = 0
        total_shadow_orders += shadow_order_count
        total_intents += intent_count
        total_acks += ack_count
        total_rejects += reject_count

        if shadow_orders_df.empty and str(run_meta.get("run_status") or summary_row.get("run_status") or "") == "STOP":
            pass
        else:
            for row_idx, shadow_row in shadow_orders_df.iterrows():
                try:
                    shadow_fingerprints.append(intent_fingerprint(_shadow_row_record(shadow_row, run_meta)))
                except (BrokerDryRunError, KeyError, TypeError, ValueError) as exc:
                    total_missing_required += 1
                    day_missing_required_count += 1
                    issues_for_day.append(
                        _make_issue(
                            "missing_required_fields_exceeds_threshold",
                            f"shadow order row could not be converted to an expected broker-neutral record: {exc}",
                            config=config,
                            source_name=source_name,
                            trade_date=trade_date,
                            details={"row_index": int(row_idx)},
                        )
                    )

        for row_idx, intent_row in intents_df.iterrows():
            intent_record, missing = _intent_row_record(intent_row)
            if intent_record is None:
                total_missing_required += 1
                day_missing_required_count += 1
                issues_for_day.append(
                    _make_issue(
                        "missing_required_fields_exceeds_threshold",
                        "broker_order_intents.csv contains a row with missing required fields.",
                        config=config,
                        source_name=source_name,
                        trade_date=trade_date,
                        details={"row_index": int(row_idx), "missing": missing},
                    )
                )
                continue
            if intent_fingerprint(intent_record) != intent_fingerprint(intent_record):
                fingerprint_determinism_passed = False
                issues_for_day.append(
                    _make_issue(
                        "fingerprint_determinism_failed",
                        "intent fingerprint computation was not deterministic.",
                        config=config,
                        source_name=source_name,
                        trade_date=trade_date,
                    )
                )
            intent_fingerprints.append(intent_fingerprint(intent_record))

        duplicate_count = _duplicate_count(intent_fingerprints)
        total_duplicate_fingerprints += duplicate_count
        if config["require_deterministic_fingerprints"] and duplicate_count > 0:
            issues_for_day.append(
                _make_issue(
                    "duplicate_intent_fingerprint_detected",
                    "duplicate broker intent fingerprints were detected for the same trade date.",
                    config=config,
                    source_name=source_name,
                    trade_date=trade_date,
                    details={"duplicate_count": duplicate_count},
                )
            )

        for idx, item in enumerate(payloads):
            payload_record, missing = _payload_record(item, day_context)
            if payload_record is None:
                total_missing_required += 1
                day_missing_required_count += 1
                issues_for_day.append(
                    _make_issue(
                        "missing_required_fields_exceeds_threshold",
                        "broker_payloads.json contains a record with missing required fields.",
                        config=config,
                        source_name=source_name,
                        trade_date=trade_date,
                        details={"index": idx, "missing": missing},
                    )
                )
                continue
            payload_fingerprints.append(intent_fingerprint(payload_record))
            if not _close_leg_metadata_only_for_payload(item):
                close_leg_metadata_only_passed = False
                issues_for_day.append(
                    _make_issue(
                        "close_leg_submission_detected",
                        "close-leg fields were found outside payload metadata.",
                        config=config,
                        source_name=source_name,
                        trade_date=trade_date,
                    )
                )

        for idx, item in enumerate(acks):
            ack_record, missing = _ack_record(item, day_context)
            if ack_record is None:
                total_missing_required += 1
                day_missing_required_count += 1
                issues_for_day.append(
                    _make_issue(
                        "missing_required_fields_exceeds_threshold",
                        "broker_acks.json contains a record with missing required fields.",
                        config=config,
                        source_name=source_name,
                        trade_date=trade_date,
                        details={"index": idx, "missing": missing},
                    )
                )
                continue
            ack_fingerprints.append(intent_fingerprint(ack_record))
            if not _close_leg_metadata_only_for_ack(item):
                close_leg_metadata_only_passed = False
                issues_for_day.append(
                    _make_issue(
                        "close_leg_submission_detected",
                        "close-leg fields were found outside ack payload metadata.",
                        config=config,
                        source_name=source_name,
                        trade_date=trade_date,
                    )
                )

        broker_modes = {
            str(summary_row.get("broker_mode") or ""),
            str(summary_json.get("broker_mode") or ""),
            *[str(item.get("broker_mode") or "") for item in payloads],
            *[str(item.get("broker_mode") or "") for item in acks],
        }
        broker_ids = {
            str(summary_row.get("broker_id") or ""),
            str(summary_json.get("broker_id") or ""),
            *[str(item.get("broker_id") or "") for item in payloads],
            *[str(item.get("broker_id") or "") for item in acks],
        }

        if any(broker_id and broker_id not in allowed_broker_ids for broker_id in broker_ids):
            real_broker_connection_detected = True
            issues_for_day.append(
                _make_issue(
                    "real_broker_connection_detected",
                    "non-null broker id detected in broker dry-run artifacts.",
                    config=config,
                    source_name=source_name,
                    trade_date=trade_date,
                    details={"broker_ids": sorted(broker_ids)},
                )
            )
        if _detect_mode(list(broker_modes), allowed_modes):
            paper_or_live_mode_detected = True
            issues_for_day.append(
                _make_issue(
                    "paper_or_live_mode_detected",
                    "paper/live broker mode detected in broker dry-run artifacts.",
                    config=config,
                    source_name=source_name,
                    trade_date=trade_date,
                    details={"broker_modes": sorted(broker_modes)},
                )
            )

        if _allow_live_submission_detected(intents_df, payloads, acks):
            open_leg_only_submission_passed = False
            issues_for_day.append(
                _make_issue(
                    "unsafe_live_submission_detected",
                    "allow_live_submission=true was detected in a dry-run artifact.",
                    config=config,
                    source_name=source_name,
                    trade_date=trade_date,
                )
            )

        unmatched_shadow = _counter_diff(shadow_fingerprints, intent_fingerprints)
        unmatched_intent = _counter_diff(intent_fingerprints, shadow_fingerprints)
        total_unmatched_shadow += unmatched_shadow
        total_unmatched_intent += unmatched_intent
        if config["require_one_intent_per_shadow_order"] and (
            unmatched_shadow > int(config["max_unmatched_shadow_orders"])
            or unmatched_intent > int(config["max_unmatched_intents"])
        ):
            open_leg_only_submission_passed = False
            issues_for_day.append(
                _make_issue(
                    "unmatched_order_exceeds_threshold",
                    "shadow orders and broker-neutral intents did not reconcile one-for-one.",
                    config=config,
                    source_name=source_name,
                    trade_date=trade_date,
                    details={
                        "unmatched_shadow_order_count": unmatched_shadow,
                        "unmatched_intent_count": unmatched_intent,
                    },
                )
            )

        if Counter(intent_fingerprints) != Counter(payload_fingerprints):
            issues_for_day.append(
                _make_issue(
                    "payload_intent_mismatch_detected",
                    "payload fingerprints did not match broker-neutral intent fingerprints.",
                    config=config,
                    source_name=source_name,
                    trade_date=trade_date,
                    default="ERROR",
                )
            )
        if config["require_one_ack_per_intent"] and Counter(intent_fingerprints) != Counter(ack_fingerprints):
            issues_for_day.append(
                _make_issue(
                    "ack_count_mismatch_detected",
                    "ack fingerprints did not match broker-neutral intent fingerprints.",
                    config=config,
                    source_name=source_name,
                    trade_date=trade_date,
                    default="ERROR",
                )
            )

        if config["require_no_rejections"] and reject_count > int(config["max_reject_count"]):
            issues_for_day.append(
                _make_issue(
                    "reject_count_exceeds_threshold",
                    "reject_count exceeded the configured threshold.",
                    config=config,
                    source_name=source_name,
                    trade_date=trade_date,
                    details={"reject_count": reject_count},
                )
            )
        if day_missing_required_count > int(config["max_missing_required_fields"]):
            issues_for_day.append(
                _make_issue(
                    "missing_required_fields_exceeds_threshold",
                    "missing required field count exceeded the configured threshold.",
                    config=config,
                    source_name=source_name,
                    trade_date=trade_date,
                    details={"missing_required_field_count": day_missing_required_count},
                )
            )

        day_sensitive_files = [intents_path, payloads_path, acks_path, diagnostics_path]
        sensitive_hits = _scan_sensitive_values([path for path in day_sensitive_files if path.exists()])
        if sensitive_hits:
            credential_like_value_detected = True
            issues_for_day.append(
                _make_issue(
                    "credential_like_value_detected",
                    "credential-like assignment detected in broker dry-run artifacts.",
                    config=config,
                    source_name=source_name,
                    trade_date=trade_date,
                    details={"paths": sensitive_hits},
                )
            )

        day_status = _day_status(issues_for_day)
        if day_status == "FAIL":
            failed_days += 1
        else:
            completed_days += 1
        day_rows.append(
            {
                "source_name": source_name,
                "trade_date": trade_date,
                "status": day_status,
                "shadow_order_count": shadow_order_count,
                "intent_count": intent_count,
                "ack_count": ack_count,
                "reject_count": reject_count,
                "missing_required_field_count": day_missing_required_count,
                "unmatched_shadow_order_count": unmatched_shadow,
                "unmatched_intent_count": unmatched_intent,
                "issues": ";".join(issue.code for issue in issues_for_day),
            }
        )
        all_issues.extend(issues_for_day)

    source_sensitive_hits = _scan_sensitive_values(
        [
            broker_dir / "broker_dryrun_summary.csv",
            broker_dir / "broker_dryrun_summary.json",
            broker_dir / "broker_dryrun_summary.md",
            broker_dir / "broker_dryrun_validation.json",
        ]
    )
    if source_sensitive_hits:
        credential_like_value_detected = True
        all_issues.append(
            _make_issue(
                "credential_like_value_detected",
                "credential-like assignment detected in top-level broker dry-run artifacts.",
                config=config,
                source_name=source_name,
                details={"paths": source_sensitive_hits},
            )
        )

    source_summary = {
        "source_name": source_name,
        "status": "PASS",
        "completed_days": completed_days,
        "failed_days": failed_days,
        "shadow_order_count_total": total_shadow_orders,
        "intent_count_total": total_intents,
        "ack_count_total": total_acks,
        "reject_count_total": total_rejects,
        "unmatched_shadow_order_count": total_unmatched_shadow,
        "unmatched_intent_count": total_unmatched_intent,
        "missing_required_field_count": total_missing_required,
        "duplicate_intent_fingerprint_count": total_duplicate_fingerprints,
        "paper_or_live_mode_detected": paper_or_live_mode_detected,
        "real_broker_connection_detected": real_broker_connection_detected,
        "credential_like_value_detected": credential_like_value_detected,
        "open_leg_only_submission_passed": open_leg_only_submission_passed and total_unmatched_shadow == 0 and total_unmatched_intent == 0,
        "close_leg_metadata_only_passed": close_leg_metadata_only_passed,
        "fingerprint_determinism_passed": fingerprint_determinism_passed,
        "shadow_ops_dir": source_info["shadow_ops_dir"],
        "broker_dryrun_dir": source_info["broker_dryrun_dir"],
    }
    source_summary["status"] = _source_status([issue for issue in all_issues if issue.source_name == source_name], source_summary)
    return source_summary, day_rows, all_issues


def calibrate_broker_dryrun_outputs(
    *,
    legacy_shadow_ops_dir: str | Path | None,
    canonical_shadow_ops_dir: str | Path | None,
    calibration_config: str | Path | dict[str, Any],
    output_dir: str | Path,
) -> CalibrationResult:
    if legacy_shadow_ops_dir is None and canonical_shadow_ops_dir is None:
        raise BrokerDryRunCalibrationError("at least one of legacy_shadow_ops_dir or canonical_shadow_ops_dir must be provided")

    config = dict(calibration_config) if isinstance(calibration_config, dict) else load_broker_dryrun_calibration_config(calibration_config)
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    source_summaries: dict[str, dict[str, Any] | None] = {"legacy": None, "canonical": None}
    day_rows: list[dict[str, Any]] = []
    issues: list[CalibrationIssue] = []

    if legacy_shadow_ops_dir is not None:
        source_summary, source_days, source_issues = _calibrate_source("legacy", legacy_shadow_ops_dir, config)
        source_summaries["legacy"] = source_summary
        day_rows.extend(source_days)
        issues.extend(source_issues)
    if canonical_shadow_ops_dir is not None:
        source_summary, source_days, source_issues = _calibrate_source("canonical", canonical_shadow_ops_dir, config)
        source_summaries["canonical"] = source_summary
        day_rows.extend(source_days)
        issues.extend(source_issues)

    issue_rows = [
        {
            "source_name": issue.source_name,
            "trade_date": issue.trade_date,
            "severity": issue.severity,
            "code": issue.code,
            "message": redact_inline_secret_assignments(issue.message, ["password", "secret", "token", "api_key", "private_key"], "***REDACTED***"),
            "details_json": json.dumps(issue.details, ensure_ascii=False, sort_keys=True) if issue.details is not None else "",
        }
        for issue in issues
    ]

    by_source_rows = [summary for summary in source_summaries.values() if summary is not None]
    overall_status = "PASS"
    if any(summary and summary["status"] == "FAIL" for summary in source_summaries.values()):
        overall_status = "FAIL"
    elif any(summary and summary["status"] == "WARN" for summary in source_summaries.values()):
        overall_status = "WARN"

    summary_payload = {
        "status": overall_status,
        "passed": overall_status == "PASS",
        "generated_at": _iso_now(),
        "calibration_config": config.get("_config_path"),
        "provided_sources": {
            "legacy": legacy_shadow_ops_dir is not None,
            "canonical": canonical_shadow_ops_dir is not None,
        },
        "sources": source_summaries,
        "issue_counts": {
            "ERROR": sum(1 for issue in issues if issue.severity == "ERROR"),
            "WARN": sum(1 for issue in issues if issue.severity == "WARN"),
            "INFO": sum(1 for issue in issues if issue.severity == "INFO"),
        },
        "safety_guarantees": {
            "null_broker_only": not any(summary and summary["real_broker_connection_detected"] for summary in source_summaries.values()),
            "paper_or_live_mode_detected": any(summary and summary["paper_or_live_mode_detected"] for summary in source_summaries.values()),
            "real_broker_connection_detected": any(summary and summary["real_broker_connection_detected"] for summary in source_summaries.values()),
            "credential_like_value_detected": any(summary and summary["credential_like_value_detected"] for summary in source_summaries.values()),
            "pass_means_live_ready": False,
        },
        "human_action_required": overall_status != "PASS",
    }

    calibration_by_source = out_dir / "calibration_by_source.csv"
    calibration_by_day = out_dir / "calibration_by_day.csv"
    calibration_issues = out_dir / "calibration_issues.csv"
    calibration_summary_json = out_dir / "calibration_summary.json"
    calibration_summary_md = out_dir / "calibration_summary.md"

    pd.DataFrame(by_source_rows).to_csv(calibration_by_source, index=False)
    pd.DataFrame(day_rows).to_csv(calibration_by_day, index=False)
    pd.DataFrame(issue_rows).to_csv(calibration_issues, index=False)
    calibration_summary_json.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    calibration_summary_md.write_text(_overall_markdown(summary_payload), encoding="utf-8")

    for source_name, summary in source_summaries.items():
        if summary is None:
            continue
        source_dir = out_dir / source_name
        source_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([row for row in day_rows if row["source_name"] == source_name]).to_csv(source_dir / "calibration_by_day.csv", index=False)
        pd.DataFrame([row for row in issue_rows if row["source_name"] == source_name]).to_csv(source_dir / "calibration_issues.csv", index=False)
        (source_dir / "calibration_summary.md").write_text(_source_markdown(summary), encoding="utf-8")

    generated_sensitive_hits = _scan_sensitive_values(
        [path for path in out_dir.rglob("*") if path.is_file()]
    )
    if generated_sensitive_hits:
        overall_status = "FAIL"
        leak_issue = _make_issue(
            "credential_like_value_detected",
            "generated calibration outputs contain credential-like assignments.",
            config=config,
            details={"paths": generated_sensitive_hits},
        )
        issues.append(leak_issue)
        issue_rows.append(
            {
                "source_name": leak_issue.source_name,
                "trade_date": leak_issue.trade_date,
                "severity": leak_issue.severity,
                "code": leak_issue.code,
                "message": leak_issue.message,
                "details_json": json.dumps(leak_issue.details, ensure_ascii=False, sort_keys=True) if leak_issue.details is not None else "",
            }
        )
        summary_payload["status"] = overall_status
        summary_payload["passed"] = False
        summary_payload["issue_counts"]["ERROR"] = sum(1 for issue in issues if issue.severity == "ERROR")
        summary_payload["issue_counts"]["WARN"] = sum(1 for issue in issues if issue.severity == "WARN")
        summary_payload["safety_guarantees"]["credential_like_value_detected"] = True
        summary_payload["human_action_required"] = True
        pd.DataFrame(issue_rows).to_csv(calibration_issues, index=False)
        calibration_summary_json.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        calibration_summary_md.write_text(_overall_markdown(summary_payload), encoding="utf-8")

    output_paths = {
        "calibration_summary_md": str(calibration_summary_md),
        "calibration_summary_json": str(calibration_summary_json),
        "calibration_by_source_csv": str(calibration_by_source),
        "calibration_by_day_csv": str(calibration_by_day),
        "calibration_issues_csv": str(calibration_issues),
    }
    return CalibrationResult(
        status=summary_payload["status"],
        passed=bool(summary_payload["passed"]),
        summary=summary_payload,
        issues=issues,
        output_paths=output_paths,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcile Step 11 broker dry-run shadow-ops outputs.")
    parser.add_argument("--legacy-shadow-ops-dir", required=False, help="Legacy Step 11 shadow-ops run directory")
    parser.add_argument("--canonical-shadow-ops-dir", required=False, help="Canonical Step 11 shadow-ops run directory")
    parser.add_argument("--calibration-config", required=True, help="Broker dry-run calibration config YAML")
    parser.add_argument("--output-dir", required=True, help="Directory for calibration artifacts")
    args = parser.parse_args(argv)

    result = calibrate_broker_dryrun_outputs(
        legacy_shadow_ops_dir=args.legacy_shadow_ops_dir,
        canonical_shadow_ops_dir=args.canonical_shadow_ops_dir,
        calibration_config=args.calibration_config,
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {
                "status": result.status,
                "passed": result.passed,
                "summary": result.summary,
                "output_paths": result.output_paths,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.status != "FAIL" else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
