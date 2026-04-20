from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import argparse
import json

import pandas as pd
import yaml


REQUIRED_TOP_LEVEL_KEYS = {
    "runbook_id",
    "version",
    "scope",
    "status_actions",
    "incident_levels",
    "required_daily_packet_files",
    "canonical_sidecars_when_enabled",
    "checklists",
    "manual_override_policy",
    "kill_switch_policy",
    "ai_review_policy",
}
REQUIRED_STATUSES = {
    "GO",
    "WARN",
    "STOP",
    "HOLD_SHADOW",
    "READY_FOR_SMALL_LIVE",
    "BLOCKED",
}
REQUIRED_INCIDENT_LEVELS = {"P0", "P1", "P2", "P3"}
REQUIRED_PACKET_FILES = [
    "summary.md",
    "run.json",
    "signals.csv",
    "orders_shadow.csv",
    "fills_shadow.csv",
    "positions.csv",
    "pnl.csv",
    "risk_report.json",
    "alerts.json",
]
REQUIRED_CHECKLISTS = {
    "daily_pre_open",
    "daily_post_close",
    "weekly_review",
    "deployment_review",
    "promotion_review",
}
REQUIRED_STATUS_FIELDS = {"summary", "required_action", "shadow_continues", "escalation", "notes"}
REQUIRED_INCIDENT_FIELDS = {
    "summary",
    "trigger_examples",
    "immediate_action",
    "review_owner",
    "shadow_continues",
    "required_artifact",
    "resolution_criteria",
}


class RunbookConfigError(RuntimeError):
    pass


class DuplicateKeyError(RunbookConfigError):
    pass


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_mapping(loader: UniqueKeyLoader, node: yaml.nodes.MappingNode, deep: bool = False) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise DuplicateKeyError(f"duplicate YAML key detected: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


@dataclass(slots=True)
class RunbookValidationIssue:
    severity: str
    code: str
    message: str
    details: dict[str, Any] | None = None


@dataclass(slots=True)
class RunbookValidationResult:
    passed: bool
    issues: list[RunbookValidationIssue] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    output_paths: dict[str, str] = field(default_factory=dict)

    def issue_counts(self) -> dict[str, int]:
        counts = {"ERROR": 0, "WARN": 0, "INFO": 0}
        for issue in self.issues:
            counts[issue.severity] = counts.get(issue.severity, 0) + 1
        return counts


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RunbookConfigError(f"runbook config not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.load(handle, Loader=UniqueKeyLoader) or {}
    except DuplicateKeyError:
        raise
    except yaml.YAMLError as exc:
        raise RunbookConfigError(f"invalid YAML in runbook config: {path}") from exc
    if not isinstance(data, dict):
        raise RunbookConfigError("runbook config must deserialize to a mapping")
    return data


def load_runbook_config(path: Path | str) -> dict[str, Any]:
    return _load_yaml(Path(path).resolve())


def _append_missing_keys(
    issues: list[RunbookValidationIssue],
    *,
    actual: set[str],
    required: set[str],
    code: str,
    label: str,
) -> None:
    missing = sorted(required - actual)
    if missing:
        issues.append(
            RunbookValidationIssue(
                severity="ERROR",
                code=code,
                message=f"Missing required {label}: {', '.join(missing)}",
                details={"missing": missing},
            )
        )


def validate_runbook_config(path_or_dict: Path | str | dict[str, Any]) -> RunbookValidationResult:
    issues: list[RunbookValidationIssue] = []

    try:
        if isinstance(path_or_dict, dict):
            config = dict(path_or_dict)
            config_source = "<in-memory>"
        else:
            config = load_runbook_config(path_or_dict)
            config_source = str(Path(path_or_dict).resolve())
    except DuplicateKeyError as exc:
        issues.append(
            RunbookValidationIssue(
                severity="ERROR",
                code="duplicate_yaml_key",
                message=str(exc),
            )
        )
        return RunbookValidationResult(
            passed=False,
            issues=issues,
            summary={"config_source": str(path_or_dict)},
        )
    except RunbookConfigError as exc:
        issues.append(
            RunbookValidationIssue(
                severity="ERROR",
                code="config_load_failed",
                message=str(exc),
            )
        )
        return RunbookValidationResult(
            passed=False,
            issues=issues,
            summary={"config_source": str(path_or_dict)},
        )

    _append_missing_keys(
        issues,
        actual=set(config.keys()),
        required=REQUIRED_TOP_LEVEL_KEYS,
        code="missing_top_level_keys",
        label="top-level keys",
    )

    status_actions = config.get("status_actions", {})
    if isinstance(status_actions, dict):
        _append_missing_keys(
            issues,
            actual=set(status_actions.keys()),
            required=REQUIRED_STATUSES,
            code="missing_status_actions",
            label="status actions",
        )
        for status_name in sorted(REQUIRED_STATUSES & set(status_actions.keys())):
            payload = status_actions.get(status_name, {})
            if not isinstance(payload, dict):
                issues.append(
                    RunbookValidationIssue(
                        severity="ERROR",
                        code="invalid_status_action",
                        message=f"Status action '{status_name}' must be a mapping.",
                    )
                )
                continue
            _append_missing_keys(
                issues,
                actual=set(payload.keys()),
                required=REQUIRED_STATUS_FIELDS,
                code=f"missing_status_fields_{status_name}",
                label=f"fields for status action {status_name}",
            )
    else:
        issues.append(
            RunbookValidationIssue(
                severity="ERROR",
                code="invalid_status_actions_section",
                message="status_actions must be a mapping.",
            )
        )

    incident_levels = config.get("incident_levels", {})
    if isinstance(incident_levels, dict):
        _append_missing_keys(
            issues,
            actual=set(incident_levels.keys()),
            required=REQUIRED_INCIDENT_LEVELS,
            code="missing_incident_levels",
            label="incident levels",
        )
        for level_name in sorted(REQUIRED_INCIDENT_LEVELS & set(incident_levels.keys())):
            payload = incident_levels.get(level_name, {})
            if not isinstance(payload, dict):
                issues.append(
                    RunbookValidationIssue(
                        severity="ERROR",
                        code="invalid_incident_level",
                        message=f"Incident level '{level_name}' must be a mapping.",
                    )
                )
                continue
            _append_missing_keys(
                issues,
                actual=set(payload.keys()),
                required=REQUIRED_INCIDENT_FIELDS,
                code=f"missing_incident_fields_{level_name}",
                label=f"fields for incident level {level_name}",
            )
    else:
        issues.append(
            RunbookValidationIssue(
                severity="ERROR",
                code="invalid_incident_levels_section",
                message="incident_levels must be a mapping.",
            )
        )

    packet_files = config.get("required_daily_packet_files", [])
    if not isinstance(packet_files, list):
        issues.append(
            RunbookValidationIssue(
                severity="ERROR",
                code="invalid_required_packet_files",
                message="required_daily_packet_files must be a list.",
            )
        )
        packet_files = []
    missing_packet_files = [name for name in REQUIRED_PACKET_FILES if name not in packet_files]
    if missing_packet_files:
        issues.append(
            RunbookValidationIssue(
                severity="ERROR",
                code="missing_required_daily_packet_files",
                message=f"Missing required daily packet files: {', '.join(missing_packet_files)}",
                details={"missing": missing_packet_files},
            )
        )

    checklists = config.get("checklists", {})
    if isinstance(checklists, dict):
        _append_missing_keys(
            issues,
            actual=set(checklists.keys()),
            required=REQUIRED_CHECKLISTS,
            code="missing_checklists",
            label="checklists",
        )
    else:
        issues.append(
            RunbookValidationIssue(
                severity="ERROR",
                code="invalid_checklists_section",
                message="checklists must be a mapping.",
            )
        )
        checklists = {}

    summary = {
        "config_source": config_source,
        "runbook_id": config.get("runbook_id"),
        "version": config.get("version"),
        "scope": config.get("scope"),
        "status_action_count": len(status_actions) if isinstance(status_actions, dict) else 0,
        "incident_level_count": len(incident_levels) if isinstance(incident_levels, dict) else 0,
        "required_daily_packet_file_count": len(packet_files),
        "checklist_names": sorted(checklists.keys()) if isinstance(checklists, dict) else [],
    }
    return RunbookValidationResult(
        passed=not any(issue.severity == "ERROR" for issue in issues),
        issues=issues,
        summary=summary,
    )


def _to_markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    frame = pd.DataFrame(rows, columns=columns)
    if frame.empty:
        return "No rows."
    return frame.fillna("").to_markdown(index=False)


def _render_runbook_summary(config: dict[str, Any]) -> str:
    status_rows = []
    for status_name, payload in config["status_actions"].items():
        status_rows.append(
            {
                "status": status_name,
                "summary": payload.get("summary"),
                "required_action": payload.get("required_action"),
                "shadow_continues": payload.get("shadow_continues"),
                "escalation": payload.get("escalation"),
            }
        )
    lines = [
        "# Runbook Summary",
        "",
        f"- runbook_id: `{config['runbook_id']}`",
        f"- version: `{config['version']}`",
        f"- scope: `{config['scope']}`",
        "",
        "## Operating modes",
        "",
    ]
    for mode_name, description in config.get("operating_modes", {}).items():
        lines.append(f"- `{mode_name}`: {description}")
    lines.extend(
        [
        "",
        "## Operating stance",
        "",
        "- Default operation remains shadow only in the current repo phase.",
        "- `READY_FOR_SMALL_LIVE` is not permission to start live automatically.",
        "- AI review is advisory; deterministic gates and human kill-switch authority take precedence.",
        "",
        "## Status actions",
        "",
        _to_markdown_table(
            status_rows,
            ["status", "summary", "required_action", "shadow_continues", "escalation"],
        ),
        "",
        "## Manual override policy",
        "",
        str(config["manual_override_policy"]),
        "",
        "## Kill switch policy",
        "",
        str(config["kill_switch_policy"]),
        "",
        "## AI review policy",
        "",
        str(config["ai_review_policy"]),
        "",
    ]
    )
    return "\n".join(lines)


def _render_checklist_section(title: str, items: list[str]) -> list[str]:
    lines = [f"## {title}", ""]
    for idx, item in enumerate(items, start=1):
        lines.append(f"{idx}. {item}")
    lines.append("")
    return lines


def _render_daily_checklist(config: dict[str, Any]) -> str:
    lines = ["# Daily Checklist", ""]
    lines.extend(_render_checklist_section("Pre-Open Checklist", list(config["checklists"]["daily_pre_open"])))
    lines.extend(_render_checklist_section("Post-Close Checklist", list(config["checklists"]["daily_post_close"])))
    lines.append("## Required Daily Packet Files")
    lines.append("")
    for item in config["required_daily_packet_files"]:
        lines.append(f"- `{item}`")
    lines.append("")
    lines.append("## Canonical Sidecars When Enabled")
    lines.append("")
    for item in config["canonical_sidecars_when_enabled"]:
        lines.append(f"- `{item}`")
    lines.append("")
    return "\n".join(lines)


def _render_weekly_checklist(config: dict[str, Any]) -> str:
    lines = ["# Weekly And Deployment Checklist", ""]
    lines.extend(_render_checklist_section("Weekly Review", list(config["checklists"]["weekly_review"])))
    lines.extend(_render_checklist_section("Deployment Review", list(config["checklists"]["deployment_review"])))
    lines.extend(_render_checklist_section("Promotion Review", list(config["checklists"]["promotion_review"])))
    return "\n".join(lines)


def _render_incident_matrix(config: dict[str, Any]) -> str:
    rows = []
    for level_name, payload in config["incident_levels"].items():
        rows.append(
            {
                "level": level_name,
                "summary": payload.get("summary"),
                "review_owner": payload.get("review_owner"),
                "shadow_continues": payload.get("shadow_continues"),
                "required_artifact": payload.get("required_artifact"),
                "resolution_criteria": payload.get("resolution_criteria"),
            }
        )
    lines = [
        "# Incident Matrix",
        "",
        _to_markdown_table(
            rows,
            [
                "level",
                "summary",
                "review_owner",
                "shadow_continues",
                "required_artifact",
                "resolution_criteria",
            ],
        ),
        "",
    ]
    return "\n".join(lines)


def render_runbook_artifacts(path_or_dict: Path | str | dict[str, Any], output_dir: Path | str) -> RunbookValidationResult:
    result = validate_runbook_config(path_or_dict)
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    validation_json = out_dir / "runbook_validation.json"
    result.output_paths["runbook_validation_json"] = str(validation_json)

    payload = {
        "passed": result.passed,
        "issue_counts": result.issue_counts(),
        "issues": [asdict(issue) for issue in result.issues],
        "summary": result.summary,
        "output_paths": result.output_paths,
    }

    if result.passed:
        config = load_runbook_config(path_or_dict) if not isinstance(path_or_dict, dict) else dict(path_or_dict)
        summary_md = out_dir / "runbook_summary.md"
        daily_md = out_dir / "daily_checklist.md"
        weekly_md = out_dir / "weekly_checklist.md"
        incident_md = out_dir / "incident_matrix.md"

        summary_md.write_text(_render_runbook_summary(config), encoding="utf-8")
        daily_md.write_text(_render_daily_checklist(config), encoding="utf-8")
        weekly_md.write_text(_render_weekly_checklist(config), encoding="utf-8")
        incident_md.write_text(_render_incident_matrix(config), encoding="utf-8")

        result.output_paths.update(
            {
                "runbook_summary_md": str(summary_md),
                "daily_checklist_md": str(daily_md),
                "weekly_checklist_md": str(weekly_md),
                "incident_matrix_md": str(incident_md),
            }
        )
        payload["output_paths"] = result.output_paths

    validation_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and render the shadow/pre-live runbook config.")
    parser.add_argument("--config", required=True, help="Runbook YAML config path.")
    parser.add_argument("--output-dir", required=True, help="Directory for rendered runbook artifacts.")
    args = parser.parse_args(argv)

    result = render_runbook_artifacts(args.config, args.output_dir)
    print(
        json.dumps(
            {
                "passed": result.passed,
                "issue_counts": result.issue_counts(),
                "summary": result.summary,
                "output_paths": result.output_paths,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.passed else 1
