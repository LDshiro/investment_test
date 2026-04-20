from pathlib import Path

import pandas as pd

from leadlag.config.loader import load_app_config
from leadlag.portfolio.risk_gates import evaluate_hard_gates


def test_stop_on_missing_price() -> None:
    cfg = load_app_config(Path("configs/profiles/shadow_corrected.yaml"))
    signal = pd.Series([1.0] * 10)
    result = evaluate_hard_gates(cfg, signal, expected_cost_bps=10.0, missing_price=True)
    assert result["status"] == "STOP"
