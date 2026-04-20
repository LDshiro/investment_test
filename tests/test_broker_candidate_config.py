from __future__ import annotations

from pathlib import Path

from leadlag.broker.validation import load_broker_candidate_config, load_broker_selection_config


def test_actual_candidate_configs_load() -> None:
    for path in [
        Path("configs/brokers/null_broker_v1.yaml"),
        Path("configs/brokers/kabu_station_research_v1.yaml"),
        Path("configs/brokers/ibkr_research_v1.yaml"),
    ]:
        cfg = load_broker_candidate_config(path)
        assert cfg["broker_id"]
        assert "status" in cfg
        assert "decision_scores" in cfg


def test_selection_config_loads() -> None:
    cfg = load_broker_selection_config(Path("configs/brokers/broker_selection_v1.yaml"))
    assert cfg["selection_id"] == "broker_selection_v1"
    assert len(cfg["candidate_configs"]) == 3


def test_candidate_loader_supports_extends(tmp_path: Path) -> None:
    base_path = tmp_path / "base_candidate.yaml"
    child_path = tmp_path / "child_candidate.yaml"
    base_path.write_text(
        """
schema_version: 1
broker_id: child_broker
display_name: Child Broker
status: research_only
supported_markets: [JP]
supported_asset_types: [equity]
order_types_known: [MARKET, UNKNOWN]
time_in_force_known: [DAY, UNKNOWN]
supports_paper: false
supports_live_api: false
supports_shortability_check: false
supports_position_query: true
supports_order_status_query: true
operational_requirements: [local app]
known_limits: [research only]
safety_notes: [safe]
open_questions: [todo]
source_urls: [https://example.com]
decision_scores:
  operational_safety: 0.5
  jp_cash_equity_fit: 0.5
  dry_run_readiness: 0.5
  paper_progression_clarity: 0.5
  live_api_maturity: 0.5
  observability: 0.5
research_facts:
  - fact_id: fact
    summary: summary
    source_url: https://example.com
""".strip(),
        encoding="utf-8",
    )
    child_path.write_text(
        """
extends:
  - base_candidate.yaml
display_name: Child Broker Override
status: dry_run_only
""".strip(),
        encoding="utf-8",
    )
    cfg = load_broker_candidate_config(child_path)
    assert cfg["display_name"] == "Child Broker Override"
    assert cfg["status"] == "dry_run_only"


def test_selection_loader_supports_extends(tmp_path: Path) -> None:
    candidate_path = tmp_path / "candidate.yaml"
    candidate_path.write_text(
        """
schema_version: 1
broker_id: temp_null
display_name: Temp Null
status: dry_run_only
supported_markets: [JP]
supported_asset_types: [equity]
order_types_known: [MARKET, UNKNOWN]
time_in_force_known: [DAY, UNKNOWN]
supports_paper: false
supports_live_api: false
supports_shortability_check: false
supports_position_query: true
supports_order_status_query: true
operational_requirements: [none]
known_limits: [dry run]
safety_notes: [safe]
open_questions: [none]
source_urls: []
decision_scores:
  operational_safety: 1.0
  jp_cash_equity_fit: 1.0
  dry_run_readiness: 1.0
  paper_progression_clarity: 0.0
  live_api_maturity: 0.0
  observability: 1.0
research_facts:
  - fact_id: fact
    summary: summary
    source_url: internal://docs
""".strip(),
        encoding="utf-8",
    )
    parent_path = tmp_path / "parent_selection.yaml"
    child_path = tmp_path / "child_selection.yaml"
    parent_path.write_text(
        f"""
schema_version: 1
selection_id: test_selection
default_safe_adapter: temp_null
future_external_comparison: []
candidate_configs:
  - {candidate_path}
weights:
  operational_safety: 0.30
  jp_cash_equity_fit: 0.25
  dry_run_readiness: 0.20
  paper_progression_clarity: 0.10
  live_api_maturity: 0.10
  observability: 0.05
""".strip(),
        encoding="utf-8",
    )
    child_path.write_text(
        """
extends:
  - parent_selection.yaml
selection_id: test_selection_override
""".strip(),
        encoding="utf-8",
    )
    cfg = load_broker_selection_config(child_path)
    assert cfg["selection_id"] == "test_selection_override"
    assert cfg["default_safe_adapter"] == "temp_null"
