from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import argparse
import json
import shutil
import traceback

import pandas as pd
import yaml

from leadlag.config.loader import load_app_config
from leadlag.data_contract import validate_corrected_bundle, write_validation_outputs
from leadlag.ops.shadow_replay_validation import validate_shadow_replay
from leadlag.ops.runbook import render_runbook_artifacts
from leadlag.reporting.weekly_review import generate_weekly_review
from leadlag.reporting.weekly_rules import generate_weekly_gates
from leadlag.runtime.corrected_shadow_batch import run_corrected_shadow_batch


REPO_ROOT = Path(__file__).resolve().parents[3]
REQUIRED_STAGE_NAMES = [
    "validate_data_contract",
    "run_batch",
    "validate_shadow_replay",
    "weekly_review",
    "weekly_gates",
    "render_runbook",
]


class ShadowOpsConfigError(RuntimeError):
    pass


class ShadowOpsStageFailure(RuntimeError):
    def __init__(self, message: str, *, summary: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.summary = summary or {}


@dataclass(slots=True)
class ShadowOpsStageResult:
    stage: str
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = None
    output_dir: str | None = None
    stdout_log: str | None = None
    stderr_log: str | None = None
    config_reference: str | None = None
    error: str | None = None
    summary: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ShadowOpsResult:
    passed: bool
    overall_status: str
    ops_run_id: str
    output_dir: str
    stage_results: list[ShadowOpsStageResult] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    output_paths: dict[str, str] = field(default_factory=dict)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key == "extends":
            continue
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ShadowOpsConfigError(f"shadow ops config not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ShadowOpsConfigError("shadow ops config must deserialize to a mapping")
    return data


def _load_yaml_with_extends(path: Path) -> dict[str, Any]:
    data = _load_yaml(path)
    merged: dict[str, Any] = {}
    for rel in data.get("extends", []) or []:
        parent = (path.parent / rel).resolve()
        merged = _deep_merge(merged, _load_yaml_with_extends(parent))
    return _deep_merge(merged, data)


def _resolve_repo_path(path_value: str | Path | None) -> Path | None:
    if path_value is None:
        return None
    path = Path(path_value)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve(strict=False)


def load_shadow_ops_config(path: Path | str) -> dict[str, Any]:
    cfg_path = Path(path).resolve()
    data = _load_yaml_with_extends(cfg_path)
    if "ops" not in data or "stages" not in data:
        raise ShadowOpsConfigError("shadow ops config must include top-level ops and stages sections")

    ops = data["ops"]
    stages = data["stages"]
    if not isinstance(ops, dict) or not isinstance(stages, dict):
        raise ShadowOpsConfigError("ops and stages must both be mappings")
    if ops.get("mode") != "shadow_only":
        raise ShadowOpsConfigError("ops.mode must be 'shadow_only'")
    if ops.get("variant") not in {"legacy", "canonical"}:
        raise ShadowOpsConfigError("ops.variant must be either 'legacy' or 'canonical'")

    missing_stages = [name for name in REQUIRED_STAGE_NAMES if name not in stages]
    if missing_stages:
        raise ShadowOpsConfigError(f"missing required stages: {', '.join(missing_stages)}")

    required_stage_fields = {
        "validate_data_contract": {"enabled", "bundle_dir", "contract"},
        "run_batch": {"enabled", "config"},
        "validate_shadow_replay": {"enabled", "config"},
        "weekly_review": {"enabled"},
        "weekly_gates": {"enabled", "rules_config"},
        "render_runbook": {"enabled", "config"},
    }
    for stage_name, required_fields in required_stage_fields.items():
        payload = stages.get(stage_name)
        if not isinstance(payload, dict):
            raise ShadowOpsConfigError(f"stage '{stage_name}' must be a mapping")
        missing = sorted(required_fields - set(payload.keys()))
        if missing:
            raise ShadowOpsConfigError(f"stage '{stage_name}' missing required keys: {', '.join(missing)}")

    if not stages["run_batch"]["enabled"]:
        need_existing_batch = bool(stages["validate_shadow_replay"]["enabled"] or stages["weekly_review"]["enabled"])
        if need_existing_batch and not stages["run_batch"].get("existing_batch_dir"):
            raise ShadowOpsConfigError(
                "stages.run_batch.existing_batch_dir is required when run_batch is disabled and downstream stages need a batch directory"
            )
        if stages["run_batch"].get("existing_batch_dir"):
            existing_batch_dir = _resolve_repo_path(stages["run_batch"]["existing_batch_dir"])
            if existing_batch_dir is None or not existing_batch_dir.exists():
                raise ShadowOpsConfigError(f"existing_batch_dir not found: {stages['run_batch']['existing_batch_dir']}")

    if not stages["weekly_review"]["enabled"] and stages["weekly_gates"]["enabled"]:
        if not stages["weekly_review"].get("existing_review_dir"):
            raise ShadowOpsConfigError(
                "stages.weekly_review.existing_review_dir is required when weekly_review is disabled and weekly_gates is enabled"
            )
        existing_review_dir = _resolve_repo_path(stages["weekly_review"]["existing_review_dir"])
        if existing_review_dir is None or not existing_review_dir.exists():
            raise ShadowOpsConfigError(f"existing_review_dir not found: {stages['weekly_review']['existing_review_dir']}")

    data["_config_path"] = str(cfg_path)
    return data


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timestamp_label() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _stage_slug(stage_name: str) -> str:
    return {
        "validate_data_contract": "data_contract",
        "run_batch": "batch",
        "validate_shadow_replay": "replay_validation",
        "weekly_review": "weekly_review",
        "weekly_gates": "weekly_gates",
        "render_runbook": "runbook",
    }[stage_name]


def _copy_if_exists(source: Path, destination: Path) -> None:
    if source.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _load_packet_run_metadata(packet_dir: Path) -> dict[str, Any]:
    run_meta_path = packet_dir / "run.json"
    if not run_meta_path.exists():
        return {}
    return json.loads(run_meta_path.read_text(encoding="utf-8"))


def _build_downstream_batch_summary(batch_dir: Path, destination: Path) -> dict[str, Any]:
    source = batch_dir / "batch_summary.csv"
    if not source.exists():
        return {"path": None, "normalized_rows": 0}

    df = pd.read_csv(source)
    if df.empty or "result" not in df.columns or "packet_dir" not in df.columns:
        destination.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(destination, index=False)
        return {"path": str(destination), "normalized_rows": 0}

    normalized_rows = 0
    for idx, row in df.iterrows():
        result = str(row.get("result", ""))
        status = str(row.get("status", ""))
        packet_dir_value = row.get("packet_dir")
        if result != "skipped_existing" and status != "SKIPPED":
            continue
        if pd.isna(packet_dir_value):
            continue
        packet_dir = _resolve_repo_path(str(packet_dir_value))
        if packet_dir is None or not packet_dir.exists():
            continue

        run_meta = _load_packet_run_metadata(packet_dir)
        if not run_meta:
            continue

        df.at[idx, "result"] = "completed"
        if run_meta.get("run_status"):
            df.at[idx, "status"] = run_meta["run_status"]

        for column in [
            "asof_us_date",
            "trade_date",
            "shadow_net_return",
            "paper_counterfactual_return",
            "shadow_gross_return",
        ]:
            if column in run_meta and (column not in df.columns or pd.isna(df.at[idx, column])):
                df.at[idx, column] = run_meta[column]

        normalized_rows += 1

    destination.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(destination, index=False)
    return {"path": str(destination), "normalized_rows": normalized_rows}


def _run_validate_data_contract_stage(stage_cfg: dict[str, Any], _: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    bundle_dir = _resolve_repo_path(stage_cfg["bundle_dir"])
    contract_path = _resolve_repo_path(stage_cfg["contract"])
    if bundle_dir is None or contract_path is None:
        raise ShadowOpsStageFailure("validate_data_contract stage has invalid bundle_dir or contract path")
    result = validate_corrected_bundle(bundle_dir, contract_path)
    write_validation_outputs(result, output_dir)
    summary = {
        "passed": result.passed,
        "issue_counts": result.issue_counts(),
        "bundle_dir": str(bundle_dir),
        "contract": str(contract_path),
        "output_dir": str(output_dir),
    }
    if not result.passed:
        raise ShadowOpsStageFailure("data contract validation failed", summary=summary)
    return summary


def _run_batch_stage(stage_cfg: dict[str, Any], context: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    config_path = _resolve_repo_path(stage_cfg["config"])
    if config_path is None:
        raise ShadowOpsStageFailure("run_batch stage has invalid config path")
    cfg = load_app_config(config_path)
    batch_dir, status = run_corrected_shadow_batch(cfg)
    batch_dir = Path(batch_dir).resolve()
    context["batch_dir"] = batch_dir

    for filename in ["batch_summary.csv", "batch_summary.json", "batch_summary.md"]:
        _copy_if_exists(batch_dir / filename, output_dir / filename)

    downstream_summary = _build_downstream_batch_summary(batch_dir, output_dir / "batch_summary_for_downstream.csv")
    if downstream_summary["path"] is not None:
        context["weekly_review_batch_summary_path"] = Path(downstream_summary["path"]).resolve()

    summary = {
        **status,
        "config": str(config_path),
        "batch_dir": str(batch_dir),
        "output_dir": str(output_dir),
        "downstream_batch_summary_path": downstream_summary["path"],
        "normalized_skipped_existing_rows": downstream_summary["normalized_rows"],
    }
    if int(status.get("failed", 0)) > 0:
        raise ShadowOpsStageFailure("batch replay reported failed days", summary=summary)
    return summary


def _run_validate_shadow_replay_stage(stage_cfg: dict[str, Any], context: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    batch_dir = context.get("batch_dir")
    if batch_dir is None:
        raise ShadowOpsStageFailure("validate_shadow_replay stage requires batch_dir from run_batch or existing_batch_dir")
    validation_config = _resolve_repo_path(stage_cfg["config"])
    if validation_config is None:
        raise ShadowOpsStageFailure("validate_shadow_replay stage has invalid config path")
    result = validate_shadow_replay(batch_dir=Path(batch_dir), validation_config=validation_config, output_dir=output_dir)
    summary = {
        "status": result.status,
        "passed": result.passed,
        **result.summary,
        "validation_config": str(validation_config),
        "output_dir": str(output_dir),
    }
    context["replay_validation_summary"] = summary
    if result.status == "FAIL":
        raise ShadowOpsStageFailure("shadow replay validation failed", summary=summary)
    return summary


def _run_weekly_review_stage(_: dict[str, Any], context: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    batch_dir = context.get("batch_dir")
    if batch_dir is None:
        raise ShadowOpsStageFailure("weekly_review stage requires batch_dir from run_batch or existing_batch_dir")
    batch_summary_path = context.get("weekly_review_batch_summary_path")
    if batch_summary_path is not None:
        review_dir, status = generate_weekly_review(batch_summary_path=batch_summary_path, output_dir=output_dir)
    else:
        review_dir, status = generate_weekly_review(batch_dir=batch_dir, output_dir=output_dir)
    review_dir = Path(review_dir).resolve()
    context["weekly_review_dir"] = review_dir
    summary = {
        **status,
        "batch_dir": str(Path(batch_dir).resolve()),
        "source_batch_summary_path": str(Path(batch_summary_path).resolve()) if batch_summary_path is not None else None,
        "output_dir": str(review_dir),
    }
    return summary


def _run_weekly_gates_stage(stage_cfg: dict[str, Any], context: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    review_dir = context.get("weekly_review_dir")
    if review_dir is None:
        raise ShadowOpsStageFailure("weekly_gates stage requires weekly_review_dir from weekly_review or existing_review_dir")
    rules_config = _resolve_repo_path(stage_cfg["rules_config"])
    if rules_config is None:
        raise ShadowOpsStageFailure("weekly_gates stage has invalid rules_config path")
    gates_dir, status = generate_weekly_gates(review_dir=review_dir, rules_config_path=rules_config, output_dir=output_dir)
    gates_dir = Path(gates_dir).resolve()
    promotion_path = gates_dir / "promotion_assessment.json"
    promotion = json.loads(promotion_path.read_text(encoding="utf-8")) if promotion_path.exists() else {}
    summary = {
        **status,
        "rules_config": str(rules_config),
        "output_dir": str(gates_dir),
        "promotion_failed_checks": promotion.get("failed_checks", []),
        "promotion_blocked_checks": promotion.get("blocked_checks", []),
    }
    context["weekly_gates_summary"] = summary
    context["promotion_assessment"] = promotion
    return summary


def _run_render_runbook_stage(stage_cfg: dict[str, Any], _: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    config_path = _resolve_repo_path(stage_cfg["config"])
    if config_path is None:
        raise ShadowOpsStageFailure("render_runbook stage has invalid config path")
    result = render_runbook_artifacts(config_path, output_dir)
    summary = {
        "passed": result.passed,
        "issue_counts": result.issue_counts(),
        **result.summary,
        "config": str(config_path),
        "output_dir": str(output_dir),
    }
    if not result.passed:
        raise ShadowOpsStageFailure("runbook validation/rendering failed", summary=summary)
    return summary


def _execute_named_stage(stage_name: str, stage_cfg: dict[str, Any], context: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    if stage_name == "validate_data_contract":
        return _run_validate_data_contract_stage(stage_cfg, context, output_dir)
    if stage_name == "run_batch":
        return _run_batch_stage(stage_cfg, context, output_dir)
    if stage_name == "validate_shadow_replay":
        return _run_validate_shadow_replay_stage(stage_cfg, context, output_dir)
    if stage_name == "weekly_review":
        return _run_weekly_review_stage(stage_cfg, context, output_dir)
    if stage_name == "weekly_gates":
        return _run_weekly_gates_stage(stage_cfg, context, output_dir)
    if stage_name == "render_runbook":
        return _run_render_runbook_stage(stage_cfg, context, output_dir)
    raise ShadowOpsConfigError(f"unknown stage: {stage_name}")


def _prepare_ops_output_dir(config: dict[str, Any]) -> tuple[str, Path]:
    ops_cfg = config["ops"]
    artifact_root = _resolve_repo_path(ops_cfg["artifact_root"])
    if artifact_root is None:
        raise ShadowOpsConfigError("ops.artifact_root is invalid")
    artifact_root.mkdir(parents=True, exist_ok=True)
    ops_name = str(ops_cfg["name"])
    if ops_cfg.get("timestamp_outputs", True):
        run_id = f"{ops_name}_{_timestamp_label()}"
        output_dir = artifact_root / run_id
    else:
        run_id = ops_name
        output_dir = artifact_root / ops_name
        if output_dir.exists() and not ops_cfg.get("overwrite_existing", False):
            raise ShadowOpsConfigError(f"shadow ops output dir already exists and overwrite_existing is false: {output_dir}")
        if output_dir.exists():
            shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return run_id, output_dir.resolve()


def _stage_result_frame(stage_results: list[ShadowOpsStageResult]) -> pd.DataFrame:
    return pd.DataFrame([asdict(item) for item in stage_results])


def _load_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _derive_summary(config: dict[str, Any], context: dict[str, Any], stage_results: list[ShadowOpsStageResult]) -> dict[str, Any]:
    replay_summary = context.get("replay_validation_summary", {})
    promotion = context.get("promotion_assessment", {})
    weekly_gates_summary = context.get("weekly_gates_summary", {})
    latest_week_status = weekly_gates_summary.get("latest_week_status")
    promotion_status = promotion.get("promotion_status")
    failed_checks = promotion.get("failed_checks", [])
    batch_result_counts = replay_summary.get("batch_result_counts", {}) or {}
    raw_completed_days = int(replay_summary.get("completed_days") or 0)
    skipped_existing_days = int(batch_result_counts.get("skipped_existing") or 0)
    completed_days = raw_completed_days + skipped_existing_days

    any_failed_stage = any(stage.status == "FAILED" for stage in stage_results)
    failed_days = int(replay_summary.get("failed_days") or 0)
    human_action_required = bool(
        any_failed_stage
        or failed_days > 0
        or latest_week_status in {"WARN", "STOP"}
        or promotion_status in {"BLOCKED", "READY_FOR_SMALL_LIVE"}
    )

    if any_failed_stage:
        recommended_next_action = "Investigate the failed stage, preserve the artifacts, and rerun shadow-ops after review."
    elif promotion_status == "BLOCKED":
        recommended_next_action = "Resolve the blocking condition and rerun the shadow-only review pipeline."
    elif promotion_status == "READY_FOR_SMALL_LIVE":
        recommended_next_action = "Open a separate human review for potential small-live consideration; do not start live trading automatically."
    elif latest_week_status in {"WARN", "STOP"}:
        recommended_next_action = "Review the recent weekly anomalies and continue shadow-only monitoring after human assessment."
    elif promotion_status == "HOLD_SHADOW":
        recommended_next_action = "Continue shadow-only monitoring and gather more evidence before any promotion review."
    else:
        recommended_next_action = "Continue routine shadow operations and keep the current review cadence."

    return {
        "ops_run_id": context["ops_run_id"],
        "generated_at": context["generated_at"],
        "profile_path": config["_config_path"],
        "ops_name": config["ops"]["name"],
        "mode": config["ops"]["mode"],
        "variant": config["ops"]["variant"],
        "overall_status": "FAILED" if any_failed_stage else "SUCCESS",
        "batch": {
            "batch_dir": str(context["batch_dir"]) if context.get("batch_dir") else None,
            "total_days": replay_summary.get("total_days"),
            "completed_days": completed_days,
            "failed_days": replay_summary.get("failed_days"),
            "packet_run_status_counts": replay_summary.get("packet_run_status_counts", {}),
            "batch_result_counts": batch_result_counts,
        },
        "weekly": {
            "review_dir": str(context["weekly_review_dir"]) if context.get("weekly_review_dir") else None,
            "latest_week_status": latest_week_status,
            "latest_week": weekly_gates_summary.get("latest_week"),
        },
        "promotion": {
            "promotion_status": promotion_status,
            "failed_checks": failed_checks,
            "blocked_checks": promotion.get("blocked_checks", []),
        },
        "canonical_reconciliation": {
            "max_abs_net_return_diff_bps": replay_summary.get("max_abs_net_return_diff_bps"),
            "max_abs_gross_return_diff_bps": replay_summary.get("max_abs_gross_return_diff_bps"),
            "max_abs_cost_return_diff_bps": replay_summary.get("max_abs_cost_return_diff_bps"),
        },
        "human_action_required": human_action_required,
        "recommended_next_action": recommended_next_action,
    }


def _build_operator_digest(summary: dict[str, Any], stage_results: list[ShadowOpsStageResult], paths: dict[str, str]) -> str:
    lines = [
        "# Shadow Ops Operator Digest",
        "",
        f"- ops run id: `{summary['ops_run_id']}`",
        f"- generated_at: `{summary['generated_at']}`",
        f"- profile used: `{summary['profile_path']}`",
        f"- mode: `{summary['mode']}`",
        f"- variant: `{summary['variant']}`",
        f"- overall_status: `{summary['overall_status']}`",
        "",
        "## Stage Status",
        "",
    ]
    for stage in stage_results:
        lines.append(f"- `{stage.stage}`: `{stage.status}`")
    lines.extend(
        [
            "",
            "## Batch Summary",
            "",
            f"- total_days: `{summary['batch']['total_days']}`",
            f"- completed_days: `{summary['batch']['completed_days']}`",
            f"- failed_days: `{summary['batch']['failed_days']}`",
            f"- GO/WARN/STOP counts: `{summary['batch']['packet_run_status_counts']}`",
            "",
            "## Weekly And Promotion",
            "",
            f"- latest weekly status: `{summary['weekly']['latest_week_status']}`",
            f"- promotion status: `{summary['promotion']['promotion_status']}`",
            f"- main promotion failed checks: `{summary['promotion']['failed_checks']}`",
            "",
        ]
    )
    if summary["variant"] == "canonical":
        lines.extend(
            [
                "## Canonical Reconciliation",
                "",
                f"- max_abs_net_return_diff_bps: `{summary['canonical_reconciliation']['max_abs_net_return_diff_bps']}`",
                f"- max_abs_gross_return_diff_bps: `{summary['canonical_reconciliation']['max_abs_gross_return_diff_bps']}`",
                f"- max_abs_cost_return_diff_bps: `{summary['canonical_reconciliation']['max_abs_cost_return_diff_bps']}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Artifact Paths",
            "",
        ]
    )
    for key, value in paths.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            f"- human action required: `{'yes' if summary['human_action_required'] else 'no'}`",
            f"- recommended next action: {summary['recommended_next_action']}",
            "",
        ]
    )
    return "\n".join(lines)


def run_shadow_ops(path_or_dict: Path | str | dict[str, Any]) -> ShadowOpsResult:
    config = dict(path_or_dict) if isinstance(path_or_dict, dict) else load_shadow_ops_config(path_or_dict)
    ops_run_id, ops_dir = _prepare_ops_output_dir(config)
    logs_dir = ops_dir / "logs"
    stages_root = ops_dir / "stages"
    logs_dir.mkdir(parents=True, exist_ok=True)
    stages_root.mkdir(parents=True, exist_ok=True)

    context: dict[str, Any] = {
        "ops_run_id": ops_run_id,
        "generated_at": _iso_now(),
    }

    if not config["stages"]["run_batch"]["enabled"] and config["stages"]["run_batch"].get("existing_batch_dir"):
        context["batch_dir"] = _resolve_repo_path(config["stages"]["run_batch"]["existing_batch_dir"]).resolve()
    if not config["stages"]["weekly_review"]["enabled"] and config["stages"]["weekly_review"].get("existing_review_dir"):
        context["weekly_review_dir"] = _resolve_repo_path(config["stages"]["weekly_review"]["existing_review_dir"]).resolve()

    stage_results: list[ShadowOpsStageResult] = []
    previous_failure = False
    stop_on_failure = bool(config["ops"].get("stop_on_stage_failure", True))

    for stage_name in REQUIRED_STAGE_NAMES:
        stage_cfg = config["stages"][stage_name]
        stage_dir = stages_root / _stage_slug(stage_name)
        stdout_log = logs_dir / f"{stage_name}.stdout.txt"
        stderr_log = logs_dir / f"{stage_name}.stderr.txt"

        if not stage_cfg.get("enabled", False):
            stage_results.append(
                ShadowOpsStageResult(
                    stage=stage_name,
                    status="DISABLED",
                    output_dir=str(stage_dir.resolve()),
                    stdout_log=str(stdout_log.resolve()),
                    stderr_log=str(stderr_log.resolve()),
                    config_reference=str(stage_cfg.get("config") or stage_cfg.get("contract") or stage_cfg.get("rules_config") or ""),
                    summary={
                        "existing_batch_dir": str(context["batch_dir"]) if stage_name == "run_batch" and context.get("batch_dir") else None,
                        "existing_review_dir": str(context["weekly_review_dir"]) if stage_name == "weekly_review" and context.get("weekly_review_dir") else None,
                    },
                )
            )
            continue

        if previous_failure and stop_on_failure:
            stage_results.append(
                ShadowOpsStageResult(
                    stage=stage_name,
                    status="SKIPPED",
                    output_dir=str(stage_dir.resolve()),
                    stdout_log=str(stdout_log.resolve()),
                    stderr_log=str(stderr_log.resolve()),
                    config_reference=str(stage_cfg.get("config") or stage_cfg.get("contract") or stage_cfg.get("rules_config") or ""),
                    summary={"reason": "previous stage failed and stop_on_stage_failure is true"},
                )
            )
            continue

        stage_dir.mkdir(parents=True, exist_ok=True)
        started_at = _iso_now()
        start_ts = datetime.now(timezone.utc)
        stage_result = ShadowOpsStageResult(
            stage=stage_name,
            status="SUCCESS",
            started_at=started_at,
            output_dir=str(stage_dir.resolve()),
            stdout_log=str(stdout_log.resolve()),
            stderr_log=str(stderr_log.resolve()),
            config_reference=str(stage_cfg.get("config") or stage_cfg.get("contract") or stage_cfg.get("rules_config") or ""),
        )

        with stdout_log.open("w", encoding="utf-8") as stdout_handle, stderr_log.open("w", encoding="utf-8") as stderr_handle:
            try:
                with redirect_stdout(stdout_handle), redirect_stderr(stderr_handle):
                    stage_result.summary = _execute_named_stage(stage_name, stage_cfg, context, stage_dir)
            except ShadowOpsStageFailure as exc:
                stderr_handle.write(traceback.format_exc())
                stage_result.status = "FAILED"
                stage_result.error = str(exc)
                if exc.summary:
                    stage_result.summary = exc.summary
                previous_failure = True
            except Exception as exc:  # pragma: no cover - defensive runtime path
                stderr_handle.write(traceback.format_exc())
                stage_result.status = "FAILED"
                stage_result.error = repr(exc)
                previous_failure = True

        stage_result.finished_at = _iso_now()
        stage_result.duration_seconds = round((datetime.now(timezone.utc) - start_ts).total_seconds(), 6)
        stage_results.append(stage_result)

    summary = _derive_summary(config, context, stage_results)
    paths = {
        "ops_dir": str(ops_dir),
        "logs_dir": str(logs_dir),
        "data_contract_dir": str((stages_root / "data_contract").resolve()),
        "batch_stage_dir": str((stages_root / "batch").resolve()),
        "batch_dir": str(context["batch_dir"]) if context.get("batch_dir") else "",
        "replay_validation_dir": str((stages_root / "replay_validation").resolve()),
        "weekly_review_dir": str(context["weekly_review_dir"]) if context.get("weekly_review_dir") else "",
        "weekly_gates_dir": str((stages_root / "weekly_gates").resolve()),
        "runbook_dir": str((stages_root / "runbook").resolve()),
    }

    stage_frame = _stage_result_frame(stage_results)
    stage_status_csv = ops_dir / "stage_status.csv"
    stage_status_json = ops_dir / "stage_status.json"
    paths_json = ops_dir / "paths.json"
    summary_json = ops_dir / "shadow_ops_summary.json"
    digest_md = ops_dir / "operator_digest.md"

    stage_frame.to_csv(stage_status_csv, index=False)
    stage_status_json.write_text(
        json.dumps([asdict(stage) for stage in stage_results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    paths_json.write_text(json.dumps(paths, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_json.write_text(
        json.dumps(
            {
                **summary,
                "stage_results": [asdict(stage) for stage in stage_results],
                "output_paths": {
                    "stage_status_csv": str(stage_status_csv),
                    "stage_status_json": str(stage_status_json),
                    "paths_json": str(paths_json),
                    "operator_digest_md": str(digest_md),
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    if config["ops"].get("operator_digest", True):
        digest_md.write_text(_build_operator_digest(summary, stage_results, paths), encoding="utf-8")

    return ShadowOpsResult(
        passed=summary["overall_status"] != "FAILED",
        overall_status=summary["overall_status"],
        ops_run_id=ops_run_id,
        output_dir=str(ops_dir),
        stage_results=stage_results,
        summary=summary,
        output_paths={
            "stage_status_csv": str(stage_status_csv),
            "stage_status_json": str(stage_status_json),
            "paths_json": str(paths_json),
            "shadow_ops_summary_json": str(summary_json),
            "operator_digest_md": str(digest_md),
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the shadow-only operations orchestration profile.")
    parser.add_argument("--config", required=True, help="Shadow ops profile YAML.")
    args = parser.parse_args(argv)

    result = run_shadow_ops(args.config)
    print(
        json.dumps(
            {
                "passed": result.passed,
                "overall_status": result.overall_status,
                "ops_run_id": result.ops_run_id,
                "output_dir": result.output_dir,
                "summary": result.summary,
                "output_paths": result.output_paths,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.passed else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
