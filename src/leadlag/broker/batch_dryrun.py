from __future__ import annotations

from pathlib import Path
from typing import Any
import argparse
import json

import pandas as pd

from leadlag.runtime.safety import run_runtime_safety_check

from .models import BrokerDiagnostic, BrokerMode, OrderIntent, OrderSide, dataclass_to_payload
from .null_adapter import NullBrokerAdapter
from .packet_dryrun import (
    BrokerDryRunError,
    intent_from_order_row,
    intent_record,
    load_packet_order_inputs,
)
from .validation import (
    BrokerConfigError,
    BrokerValidationError,
    load_broker_candidate_config,
    load_broker_dryrun_batch_config,
)


REPO_ROOT = Path(__file__).resolve().parents[3]


class BrokerBatchDryRunError(RuntimeError):
    pass


def _resolve_repo_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve(strict=False)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _severity_counts(diagnostics: list[BrokerDiagnostic]) -> tuple[int, int]:
    error_count = sum(1 for item in diagnostics if item.severity == "ERROR")
    warn_count = sum(1 for item in diagnostics if item.severity == "WARN")
    return error_count, warn_count


def _notional_for_intent(intent: OrderIntent) -> float:
    if intent.notional_jpy is not None:
        return float(intent.notional_jpy)
    open_price = intent.metadata.get("open_price_adj")
    if intent.quantity is None or open_price is None:
        return 0.0
    return float(intent.quantity) * float(open_price)


def _is_buy_side(side: OrderSide) -> bool:
    return side in {OrderSide.BUY, OrderSide.BUY_TO_COVER}


def _packet_dir_from_batch_row(batch_dir: Path, value: Any) -> Path | None:
    if value is None or pd.isna(value):
        return None
    path = Path(str(value))
    if path.is_absolute():
        return path.resolve(strict=False)
    candidate = (REPO_ROOT / path).resolve(strict=False)
    if candidate.exists():
        return candidate
    return (batch_dir / path).resolve(strict=False)


def _validate_broker_cfg(broker_cfg: dict[str, Any], dryrun_cfg: dict[str, Any]) -> None:
    if broker_cfg["broker_id"] not in set(dryrun_cfg["allowed_broker_ids"]):
        raise BrokerConfigError(f"broker_id '{broker_cfg['broker_id']}' is not permitted by broker dry-run batch config")
    if broker_cfg["broker_id"] != "null_broker_v1":
        raise BrokerConfigError("Step 11 broker dry-run batch only supports null_broker_v1")
    if broker_cfg.get("status") != "dry_run_only":
        raise BrokerConfigError("null broker config must remain dry_run_only for Step 11")
    if dryrun_cfg["mode"] != BrokerMode.DRY_RUN.value:
        raise BrokerConfigError("broker dry-run batch mode must remain DRY_RUN")
    if dryrun_cfg["allow_live_submission"]:
        raise BrokerConfigError("allow_live_submission must remain false for Step 11")
    if dryrun_cfg["allow_paper_submission"]:
        raise BrokerConfigError("allow_paper_submission must remain false for Step 11")


def _runtime_safety_gate(dryrun_cfg: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    if not dryrun_cfg["require_runtime_safety"]:
        return {
            "status": "SKIPPED",
            "issue_counts": {"ERROR": 0, "WARN": 0, "INFO": 0},
            "output_dir": None,
        }

    runtime_cfg = dryrun_cfg["runtime_safety"]
    result = run_runtime_safety_check(
        security_config=runtime_cfg["security_config"],
        secrets_inventory=runtime_cfg["secrets_inventory"],
        host_config=runtime_cfg["host_config"],
        output_dir=output_dir / "runtime_safety",
    )
    issue_counts = result.issue_counts()
    if result.status == "FAIL" and dryrun_cfg["block_on_runtime_safety_error"]:
        raise BrokerBatchDryRunError("runtime safety reported FAIL and broker dry-run batch is configured to block on errors")
    if result.status == "WARN" and not dryrun_cfg["allow_runtime_safety_warn"]:
        raise BrokerBatchDryRunError("runtime safety reported WARN and allow_runtime_safety_warn is false")
    return {
        "status": result.status,
        "issue_counts": issue_counts,
        "output_dir": str((output_dir / "runtime_safety").resolve()),
        "output_paths": result.output_paths,
    }


def _empty_day_outputs(trade_date: str, output_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    daily_dir = output_dir / "daily" / trade_date
    daily_dir.mkdir(parents=True, exist_ok=True)
    return [], [], [], []


def _write_daily_outputs(
    trade_date: str,
    output_dir: Path,
    intents: list[OrderIntent],
    payloads: list[dict[str, Any]],
    acks: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
) -> None:
    daily_dir = output_dir / "daily" / trade_date
    daily_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([intent_record(intent) for intent in intents]).to_csv(daily_dir / "broker_order_intents.csv", index=False)
    (daily_dir / "broker_payloads.json").write_text(json.dumps(payloads, ensure_ascii=False, indent=2), encoding="utf-8")
    (daily_dir / "broker_acks.json").write_text(json.dumps(acks, ensure_ascii=False, indent=2), encoding="utf-8")
    (daily_dir / "broker_diagnostics.json").write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8")


def _daily_result_template(
    *,
    trade_date: str,
    packet_dir: Path | None,
    run_status: str | None,
    broker_cfg: dict[str, Any],
    batch_result: str | None,
    runtime_safety_status: str,
) -> dict[str, Any]:
    return {
        "trade_date": trade_date,
        "packet_dir": str(packet_dir.resolve()) if packet_dir is not None else None,
        "run_status": run_status,
        "batch_result": batch_result,
        "intent_count": 0,
        "payload_count": 0,
        "ack_count": 0,
        "reject_count": 0,
        "missing_intent_count": 0,
        "raw_order_row_count": 0,
        "diagnostic_error_count": 0,
        "diagnostic_warn_count": 0,
        "gross_notional_jpy": 0.0,
        "buy_notional_jpy": 0.0,
        "sell_notional_jpy": 0.0,
        "broker_id": broker_cfg["broker_id"],
        "broker_mode": BrokerMode.DRY_RUN.value,
        "runtime_safety_status": runtime_safety_status,
        "passed": False,
        "reason_if_failed": None,
    }


def _load_batch_summary(batch_dir: Path) -> pd.DataFrame:
    summary_path = batch_dir / "batch_summary.csv"
    if not summary_path.exists():
        raise BrokerBatchDryRunError(f"batch_summary.csv not found under batch dir: {batch_dir}")
    df = pd.read_csv(summary_path)
    required_columns = {"trade_date", "packet_dir", "result"}
    missing = sorted(required_columns - set(df.columns))
    if missing:
        raise BrokerBatchDryRunError(f"batch_summary.csv missing required columns: {', '.join(missing)}")
    return df


def broker_dryrun_batch(
    batch_dir: str | Path,
    broker_config: str | Path | dict[str, Any],
    dryrun_config: str | Path | dict[str, Any],
    output_dir: str | Path,
) -> tuple[Path, dict[str, Any]]:
    batch_path = Path(batch_dir).resolve()
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    broker_cfg = dict(broker_config) if isinstance(broker_config, dict) else load_broker_candidate_config(broker_config)
    dryrun_cfg = dict(dryrun_config) if isinstance(dryrun_config, dict) else load_broker_dryrun_batch_config(dryrun_config)
    _validate_broker_cfg(broker_cfg, dryrun_cfg)

    runtime_safety = _runtime_safety_gate(dryrun_cfg, out_dir)
    adapter = NullBrokerAdapter(broker_id=broker_cfg["broker_id"], mode=BrokerMode.DRY_RUN, config=broker_cfg)

    batch_summary = _load_batch_summary(batch_path)
    daily_rows: list[dict[str, Any]] = []
    runtime_status = runtime_safety["status"]

    for _, row in batch_summary.iterrows():
        trade_date = str(row.get("trade_date"))
        packet_dir = _packet_dir_from_batch_row(batch_path, row.get("packet_dir"))
        batch_result = None if pd.isna(row.get("result")) else str(row.get("result"))
        daily = _daily_result_template(
            trade_date=trade_date,
            packet_dir=packet_dir,
            run_status=None if pd.isna(row.get("status")) else str(row.get("status")),
            broker_cfg=broker_cfg,
            batch_result=batch_result,
            runtime_safety_status=runtime_status,
        )

        diagnostics: list[BrokerDiagnostic] = list(adapter.validate_environment())
        payloads: list[dict[str, Any]] = []
        acks: list[dict[str, Any]] = []
        intents: list[OrderIntent] = []
        if packet_dir is None or not packet_dir.exists():
            diagnostics.append(
                BrokerDiagnostic(
                    severity="ERROR",
                    code="packet_dir_missing",
                    message="packet_dir from batch summary does not exist",
                    details={"packet_dir": str(row.get("packet_dir"))},
                )
            )
        else:
            required_paths = {name: packet_dir / name for name in dryrun_cfg["require_packet_files"]}
            missing_files = [name for name, path in required_paths.items() if not path.exists()]
            if missing_files:
                diagnostics.append(
                    BrokerDiagnostic(
                        severity="ERROR",
                        code="missing_required_packet_files",
                        message="required packet files are missing",
                        details={"missing_files": missing_files},
                    )
                )
            else:
                run_meta = _load_json(packet_dir / "run.json")
                daily["run_status"] = str(run_meta.get("run_status") or daily["run_status"] or "")
                packet_path, _, orders_df = load_packet_order_inputs(packet_dir, allow_empty_orders=True)
                daily["raw_order_row_count"] = int(len(orders_df))

                if orders_df.empty:
                    if daily["run_status"] == "STOP":
                        daily["passed"] = True
                    else:
                        diagnostics.append(
                            BrokerDiagnostic(
                                severity="ERROR",
                                code="empty_orders_shadow",
                                message="orders_shadow.csv is empty for a non-STOP run",
                            )
                        )
                else:
                    for row_idx, order_row in orders_df.iterrows():
                        try:
                            intent = intent_from_order_row(order_row, run_meta=run_meta, packet_path=packet_path)
                        except (BrokerDryRunError, KeyError, TypeError, ValueError) as exc:
                            daily["missing_intent_count"] += 1
                            diagnostics.append(
                                BrokerDiagnostic(
                                    severity="ERROR",
                                    code="intent_conversion_failed",
                                    message=f"could not convert packet row to OrderIntent: {exc}",
                                    details={"row_index": int(row_idx), "ticker": None if pd.isna(order_row.get('ticker')) else str(order_row.get('ticker'))},
                                )
                            )
                            continue

                        if intent.allow_live_submission or dryrun_cfg["allow_live_submission"]:
                            raise BrokerBatchDryRunError("allow_live_submission must remain false for Step 11 broker dry-run batch")
                        intents.append(intent)
                        try:
                            payload = adapter.prepare_order_payload(intent)
                            ack = adapter.dry_run_order(intent)
                            payloads.append(dataclass_to_payload(payload))
                            acks.append(dataclass_to_payload(ack))
                            notional = _notional_for_intent(intent)
                            daily["gross_notional_jpy"] += notional
                            if _is_buy_side(intent.side):
                                daily["buy_notional_jpy"] += notional
                            else:
                                daily["sell_notional_jpy"] += notional
                        except (BrokerValidationError, ValueError) as exc:
                            daily["reject_count"] += 1
                            diagnostics.append(
                                BrokerDiagnostic(
                                    severity="ERROR",
                                    code="null_broker_reject",
                                    message=f"NullBroker dry-run rejected an intent: {exc}",
                                    details={"symbol": intent.symbol, "side": intent.side.value},
                                )
                            )

        daily["intent_count"] = len(intents)
        daily["payload_count"] = len(payloads)
        daily["ack_count"] = len(acks)
        error_count, warn_count = _severity_counts(diagnostics)
        daily["diagnostic_error_count"] = error_count
        daily["diagnostic_warn_count"] = warn_count

        if runtime_status == "FAIL":
            daily["reason_if_failed"] = "runtime_safety_failed"
        elif runtime_status == "WARN" and not dryrun_cfg["allow_runtime_safety_warn"]:
            daily["reason_if_failed"] = "runtime_safety_warn_blocked"
        elif daily["diagnostic_error_count"] > 0:
            daily["reason_if_failed"] = daily["reason_if_failed"] or "diagnostic_errors"
        else:
            raw_order_count = max(int(daily["raw_order_row_count"]), 1)
            missing_rate = float(daily["missing_intent_count"]) / float(raw_order_count)
            reject_rate = float(daily["reject_count"]) / float(max(int(daily["intent_count"]), 1))
            ack_required_ok = (not dryrun_cfg["require_ack_for_every_intent"]) or (daily["ack_count"] == daily["intent_count"])
            if missing_rate > float(dryrun_cfg["max_missing_intent_rate"]):
                daily["reason_if_failed"] = "missing_intent_rate_exceeded"
            elif reject_rate > float(dryrun_cfg["max_reject_rate"]):
                daily["reason_if_failed"] = "reject_rate_exceeded"
            elif not ack_required_ok:
                daily["reason_if_failed"] = "missing_ack_for_intent"
            elif not daily["passed"]:
                daily["passed"] = True

        if dryrun_cfg["write_daily_artifacts"]:
            _write_daily_outputs(
                trade_date,
                out_dir,
                intents,
                payloads,
                acks,
                [dataclass_to_payload(item) for item in diagnostics],
            )
        daily_rows.append(daily)

    summary_df = pd.DataFrame(daily_rows)
    total_days = int(len(summary_df))
    completed_days = int(summary_df["passed"].sum()) if not summary_df.empty else 0
    failed_days = total_days - completed_days
    passed = failed_days == 0
    reason_if_failed = None
    if not passed:
        failed_row = summary_df.loc[~summary_df["passed"]].iloc[0]
        reason_if_failed = str(failed_row.get("reason_if_failed") or "one_or_more_days_failed")

    summary = {
        "batch_dir": str(batch_path),
        "broker_id": broker_cfg["broker_id"],
        "broker_mode": BrokerMode.DRY_RUN.value,
        "runtime_safety_status": runtime_status,
        "runtime_safety_issue_counts": runtime_safety["issue_counts"],
        "total_days": total_days,
        "completed_days": completed_days,
        "failed_days": failed_days,
        "intent_count_total": int(summary_df["intent_count"].sum()) if not summary_df.empty else 0,
        "ack_count_total": int(summary_df["ack_count"].sum()) if not summary_df.empty else 0,
        "reject_count_total": int(summary_df["reject_count"].sum()) if not summary_df.empty else 0,
        "diagnostic_error_count_total": int(summary_df["diagnostic_error_count"].sum()) if not summary_df.empty else 0,
        "diagnostic_warn_count_total": int(summary_df["diagnostic_warn_count"].sum()) if not summary_df.empty else 0,
        "passed": passed,
        "reason_if_failed": reason_if_failed,
        "output_paths": {
            "broker_dryrun_summary_csv": str((out_dir / "broker_dryrun_summary.csv").resolve()),
            "broker_dryrun_summary_json": str((out_dir / "broker_dryrun_summary.json").resolve()),
            "broker_dryrun_summary_md": str((out_dir / "broker_dryrun_summary.md").resolve()),
            "broker_dryrun_validation_json": str((out_dir / "broker_dryrun_validation.json").resolve()),
        },
    }

    summary_df.to_csv(out_dir / "broker_dryrun_summary.csv", index=False)
    (out_dir / "broker_dryrun_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "broker_dryrun_validation.json").write_text(
        json.dumps(
            {
                "dryrun_config_path": dryrun_cfg.get("_config_path"),
                "broker_config_path": broker_cfg.get("_config_path"),
                "runtime_safety": runtime_safety,
                "passed": passed,
                "reason_if_failed": reason_if_failed,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (out_dir / "broker_dryrun_summary.md").write_text(
        "\n".join(
            [
                "# Broker Dry-Run Batch Summary",
                "",
                f"- batch_dir: `{batch_path}`",
                f"- broker_id: `{broker_cfg['broker_id']}`",
                f"- broker_mode: `{BrokerMode.DRY_RUN.value}`",
                f"- runtime_safety_status: `{runtime_status}`",
                f"- total_days: `{total_days}`",
                f"- completed_days: `{completed_days}`",
                f"- failed_days: `{failed_days}`",
                f"- intent_count_total: `{summary['intent_count_total']}`",
                f"- ack_count_total: `{summary['ack_count_total']}`",
                f"- reject_count_total: `{summary['reject_count_total']}`",
                f"- passed: `{passed}`",
                f"- reason_if_failed: `{reason_if_failed}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return out_dir, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a safe NullBroker dry-run over a historical shadow batch.")
    parser.add_argument("--batch-dir", required=True, help="Historical shadow batch directory")
    parser.add_argument("--broker-config", required=True, help="Broker candidate config YAML")
    parser.add_argument("--dryrun-config", required=True, help="Broker dry-run batch config YAML")
    parser.add_argument("--output-dir", required=True, help="Directory for broker dry-run batch artifacts")
    args = parser.parse_args(argv)

    out_dir, status = broker_dryrun_batch(
        batch_dir=args.batch_dir,
        broker_config=args.broker_config,
        dryrun_config=args.dryrun_config,
        output_dir=args.output_dir,
    )
    print(f"broker dry-run batch completed: {out_dir}")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0 if status["passed"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
