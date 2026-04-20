from __future__ import annotations

from pathlib import Path
import json

import pandas as pd
import pytest

from leadlag.broker.batch_dryrun import BrokerBatchDryRunError, broker_dryrun_batch
from leadlag.broker.validation import BrokerConfigError


def _write_packet(packet_dir: Path) -> None:
    packet_dir.mkdir(parents=True, exist_ok=True)
    (packet_dir / "run.json").write_text(
        json.dumps({"run_id": "run-1", "trade_date": "2025-11-28", "run_status": "GO", "strategy": "pca_sub"}),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "date": "2025-11-28",
                "ticker": "1619.T",
                "side": "BUY",
                "target_weight": 0.2,
                "intended_open_qty": 10,
                "intended_close_qty": 0,
                "open_price_adj": 100.0,
                "close_price_adj": 101.0,
                "target_notional_jpy": 1000.0,
                "close_side": "SELL",
            }
        ]
    ).to_csv(packet_dir / "orders_shadow.csv", index=False)
    (packet_dir / "risk_report.json").write_text("{}", encoding="utf-8")
    (packet_dir / "alerts.json").write_text("[]", encoding="utf-8")


def _batch_dir(tmp_path: Path) -> Path:
    batch_dir = tmp_path / "batch"
    batch_dir.mkdir()
    packet_dir = tmp_path / "runs" / "packet"
    _write_packet(packet_dir)
    pd.DataFrame(
        [{"trade_date": "2025-11-28", "result": "completed", "status": "GO", "packet_dir": str(packet_dir)}]
    ).to_csv(batch_dir / "batch_summary.csv", index=False)
    return batch_dir


def _base_cfg() -> dict:
    return {
        "version": "broker_dryrun_batch_v1",
        "mode": "DRY_RUN",
        "allowed_broker_ids": ["null_broker_v1"],
        "allow_live_submission": False,
        "allow_paper_submission": False,
        "require_runtime_safety": False,
        "allow_runtime_safety_warn": True,
        "block_on_runtime_safety_error": True,
        "runtime_safety": {
            "security_config": "configs/security/runtime_security_policy_v1.yaml",
            "secrets_inventory": "configs/security/secrets_inventory_v1.yaml",
            "host_config": "configs/runtime/execution_host_local_v1.yaml",
        },
        "require_packet_files": ["run.json", "orders_shadow.csv", "risk_report.json", "alerts.json"],
        "order_source": "orders_shadow.csv",
        "max_reject_rate": 0.0,
        "max_missing_intent_rate": 0.0,
        "require_ack_for_every_intent": True,
        "write_daily_artifacts": True,
    }


class _FakeRuntimeSafetyResult:
    def __init__(self, status: str) -> None:
        self.status = status
        self.passed = status != "FAIL"
        self.output_paths = {}
        self.summary = {}

    def issue_counts(self) -> dict[str, int]:
        return {"ERROR": 1 if self.status == "FAIL" else 0, "WARN": 1 if self.status == "WARN" else 0, "INFO": 0}


def test_invalid_broker_mode_fails_closed(tmp_path: Path) -> None:
    cfg = _base_cfg()
    cfg["mode"] = "PAPER"
    with pytest.raises(BrokerConfigError):
        broker_dryrun_batch(
            batch_dir=_batch_dir(tmp_path),
            broker_config="configs/brokers/null_broker_v1.yaml",
            dryrun_config=cfg,
            output_dir=tmp_path / "out",
        )


def test_allow_live_submission_true_fails_closed(tmp_path: Path) -> None:
    cfg = _base_cfg()
    cfg["allow_live_submission"] = True
    with pytest.raises(BrokerConfigError):
        broker_dryrun_batch(
            batch_dir=_batch_dir(tmp_path),
            broker_config="configs/brokers/null_broker_v1.yaml",
            dryrun_config=cfg,
            output_dir=tmp_path / "out",
        )


def test_runtime_safety_fail_blocks_batch(monkeypatch, tmp_path: Path) -> None:
    cfg = _base_cfg()
    cfg["require_runtime_safety"] = True
    monkeypatch.setattr(
        "leadlag.broker.batch_dryrun.run_runtime_safety_check",
        lambda *args, **kwargs: _FakeRuntimeSafetyResult("FAIL"),
    )
    with pytest.raises(BrokerBatchDryRunError):
        broker_dryrun_batch(
            batch_dir=_batch_dir(tmp_path),
            broker_config="configs/brokers/null_broker_v1.yaml",
            dryrun_config=cfg,
            output_dir=tmp_path / "out",
        )


def test_runtime_safety_warn_is_allowed_when_configured(monkeypatch, tmp_path: Path) -> None:
    cfg = _base_cfg()
    cfg["require_runtime_safety"] = True
    cfg["allow_runtime_safety_warn"] = True
    monkeypatch.setattr(
        "leadlag.broker.batch_dryrun.run_runtime_safety_check",
        lambda *args, **kwargs: _FakeRuntimeSafetyResult("WARN"),
    )
    _, summary = broker_dryrun_batch(
        batch_dir=_batch_dir(tmp_path),
        broker_config="configs/brokers/null_broker_v1.yaml",
        dryrun_config=cfg,
        output_dir=tmp_path / "out",
    )
    assert summary["passed"] is True
    assert summary["runtime_safety_status"] == "WARN"
