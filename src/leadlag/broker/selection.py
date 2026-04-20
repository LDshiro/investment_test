from __future__ import annotations

from pathlib import Path
from typing import Any
import argparse
import json

import pandas as pd

from .validation import load_broker_candidate_config, load_broker_selection_config


class BrokerSelectionError(RuntimeError):
    pass


def _score_row(candidate: dict[str, Any], weights: dict[str, float]) -> dict[str, Any]:
    scores = candidate["decision_scores"]
    row: dict[str, Any] = {
        "broker_id": candidate["broker_id"],
        "display_name": candidate["display_name"],
        "status": candidate["status"],
        "supported_markets": ";".join(candidate["supported_markets"]),
        "supports_paper": candidate["supports_paper"],
        "supports_live_api": candidate["supports_live_api"],
    }
    total = 0.0
    for key, weight in weights.items():
        raw_score = float(scores.get(key, 0.0))
        weighted = raw_score * float(weight)
        row[f"score_{key}"] = raw_score
        row[f"weighted_{key}"] = weighted
        total += weighted
    row["total_score"] = round(total, 6)
    return row


def _derive_blocking_notes(candidate: dict[str, Any]) -> str:
    notes: list[str] = []
    if candidate["status"] == "dry_run_only":
        notes.append("No external connectivity; safe local dry-run only.")
    if candidate["status"] == "research_only":
        notes.append("Research facts only; no Step 09 runtime integration beyond documentation.")
    if candidate["status"] == "paper_candidate":
        notes.append("Paper-first only; Step 09 does not add sockets or credentials.")
    notes.extend(candidate.get("safety_notes", [])[:2])
    notes.extend(candidate.get("open_questions", [])[:2])
    return "; ".join(notes)


def _select_recommendations(frame: pd.DataFrame, selection_cfg: dict[str, Any]) -> pd.DataFrame:
    out = frame.copy()
    default_safe_adapter = str(selection_cfg["default_safe_adapter"])
    external_ids = list(selection_cfg.get("future_external_comparison", []))
    external = out[out["broker_id"].isin(external_ids)].sort_values("total_score", ascending=False)
    external_front_runner = None if external.empty else str(external.iloc[0]["broker_id"])

    recommendations: list[str] = []
    for _, row in out.iterrows():
        broker_id = str(row["broker_id"])
        if broker_id == default_safe_adapter:
            recommendations.append("step09_default_dry_run")
        elif broker_id == external_front_runner:
            recommendations.append("future_external_front_runner")
        elif broker_id in external_ids:
            recommendations.append("future_external_secondary")
        else:
            recommendations.append("not_selected")
    out["selection_recommendation"] = recommendations
    return out


def _markdown_report(
    selection_cfg: dict[str, Any],
    candidate_cfgs: list[dict[str, Any]],
    matrix: pd.DataFrame,
) -> str:
    default_safe_adapter = selection_cfg["default_safe_adapter"]
    external_ids = selection_cfg.get("future_external_comparison", [])
    external = matrix[matrix["broker_id"].isin(external_ids)].sort_values("total_score", ascending=False)

    lines = [
        "# Broker Selection Report",
        "",
        "Step 09 is a non-live broker research and dry-run design step.",
        "",
        f"- selection_id: `{selection_cfg['selection_id']}`",
        f"- default Step 09 dry-run adapter: `{default_safe_adapter}`",
        "- live-ready broker selected: `none`",
        "",
        "## Current safe recommendation",
        "",
        f"- Use `{default_safe_adapter}` for Step 09 packet dry-run and adapter-contract verification.",
        "- This adapter is local-only, credential-free, and cannot submit a live order.",
        "",
        "## Future external broker comparison",
        "",
    ]

    if external.empty:
        lines.append("No future external candidates were configured.")
    else:
        lines.append(
            external[
                [
                    "broker_id",
                    "display_name",
                    "status",
                    "total_score",
                    "selection_recommendation",
                    "blocking_notes",
                ]
            ]
            .fillna("")
            .to_markdown(index=False)
        )
    lines.extend(
        [
            "",
            "## Full decision matrix",
            "",
            matrix[
                [
                    "broker_id",
                    "display_name",
                    "status",
                    "supported_markets",
                    "supports_paper",
                    "supports_live_api",
                    "total_score",
                    "selection_recommendation",
                    "blocking_notes",
                ]
            ]
            .fillna("")
            .to_markdown(index=False),
            "",
            "## Research fact sources",
            "",
        ]
    )
    for candidate in candidate_cfgs:
        lines.append(f"### `{candidate['broker_id']}`")
        for fact in candidate.get("research_facts", []):
            lines.append(f"- `{fact['fact_id']}`: {fact['summary']} ({fact['source_url']})")
        if not candidate.get("research_facts"):
            lines.append("- no external research facts recorded")
        lines.append("")
    lines.append("AI may summarize and audit these results, but it must not be the only live-order authorization mechanism.")
    lines.append("")
    return "\n".join(lines)


def evaluate_broker_candidates(config_path: str | Path, output_dir: str | Path) -> tuple[Path, dict[str, Any]]:
    selection_cfg = load_broker_selection_config(config_path)
    candidate_cfgs = [load_broker_candidate_config(path) for path in selection_cfg["candidate_configs"]]
    weights = {key: float(value) for key, value in selection_cfg["weights"].items()}

    rows = []
    for candidate in candidate_cfgs:
        row = _score_row(candidate, weights)
        row["blocking_notes"] = _derive_blocking_notes(candidate)
        rows.append(row)

    matrix = pd.DataFrame(rows).sort_values("total_score", ascending=False).reset_index(drop=True)
    matrix = _select_recommendations(matrix, selection_cfg)

    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    decision_csv = out_dir / "broker_decision_matrix.csv"
    report_md = out_dir / "broker_selection_report.md"
    report_json = out_dir / "broker_selection_report.json"

    matrix.to_csv(decision_csv, index=False)
    report_md.write_text(_markdown_report(selection_cfg, candidate_cfgs, matrix), encoding="utf-8")
    report_json.write_text(
        json.dumps(
            {
                "selection_id": selection_cfg["selection_id"],
                "default_safe_adapter": selection_cfg["default_safe_adapter"],
                "future_external_comparison": selection_cfg["future_external_comparison"],
                "weights": weights,
                "candidates": matrix.to_dict(orient="records"),
                "output_dir": str(out_dir),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    status = {
        "output_dir": str(out_dir),
        "candidate_count": int(matrix.shape[0]),
        "default_safe_adapter": selection_cfg["default_safe_adapter"],
        "future_external_front_runner": None
        if matrix[matrix["selection_recommendation"] == "future_external_front_runner"].empty
        else str(matrix[matrix["selection_recommendation"] == "future_external_front_runner"].iloc[0]["broker_id"]),
        "live_ready_broker": None,
    }
    return out_dir, status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate standalone broker candidate configs for Step 09.")
    parser.add_argument("--config", required=True, help="Broker selection YAML")
    parser.add_argument("--output-dir", required=True, help="Directory for selection artifacts")
    args = parser.parse_args(argv)

    out_dir, status = evaluate_broker_candidates(args.config, args.output_dir)
    print(f"broker selection completed: {out_dir}")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
