
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

AlignmentMode = Literal["paper", "robust"]
CFullMethod = Literal["post_inception_only", "proxy_backfill"]
AnnualizationMode = Literal["main", "paper"]
MDDMode = Literal["running_peak", "paper_formula"]

@dataclass(slots=True)
class ReproConfig:
    # Data roots
    data_root: Path = Path("data/raw/yahoo")
    factor_root: Path = Path("data/raw/factors")
    output_root: Path = Path("artifacts")

    # Main paper hyper-parameters
    lookback: int = 60
    n_components: int = 3
    prior_dim: int = 3
    lambda_reg: float = 0.9
    q: float = 0.30

    # Date controls
    cfull_start: str = "2010-01-01"
    cfull_end: str = "2014-12-31"
    eval_start: str = "2015-01-01"
    eval_end: str = "2025-12-31"

    # Handling ambiguities
    alignment_mode: AlignmentMode = "paper"
    cfull_method: CFullMethod = "post_inception_only"
    annualization_base_main: int = 252
    annualization_base_paper: int = 12
    mdd_mode_main: MDDMode = "running_peak"
    mdd_mode_paper: MDDMode = "paper_formula"

    # Open-to-close construction
    use_adjusted_ohlc: bool = True

    # Factor regression
    subtract_rf_in_regression: bool = False
    nw_lag: int = 5
    nw_lag_grid: tuple[int, ...] = (5, 10, 20)

    # Reproduction helpers
    majority_target_count: int = 2590
    require_strict_complete_cases: bool = True

    # Optional proxy map for C_full backfill. Expected to be present in local CSV dir.
    proxy_map: dict[str, str] = field(default_factory=dict)

    # Synthetic smoke test
    synthetic_seed: int = 42
    synthetic_days: int = 3000

    def ensure_dirs(self) -> None:
        self.output_root.mkdir(parents=True, exist_ok=True)
