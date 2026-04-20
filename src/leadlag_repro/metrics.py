
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import ReproConfig, AnnualizationMode, MDDMode
from .strategy import BacktestBundle, StrategyOutput
from .tickers import TABLE2_TARGET
from .utils import annualize_mean, annualize_vol, paper_formula_mdd, running_mdd

@dataclass(slots=True)
class StrategySummary:
    strategy: str
    ar: float
    risk: float
    rr: float
    mdd: float
    n_obs: int

def _annualization_base(config: ReproConfig, mode: AnnualizationMode) -> int:
    if mode == "main":
        return config.annualization_base_main
    if mode == "paper":
        return config.annualization_base_paper
    raise ValueError(f"Unknown annualization mode: {mode}")

def _mdd_mode(config: ReproConfig, mode: MDDMode | None) -> MDDMode:
    if mode is not None:
        return mode
    return config.mdd_mode_main

def summarize_strategy(
    output: StrategyOutput,
    config: ReproConfig,
    annualization_mode: AnnualizationMode = "main",
    mdd_mode: MDDMode | None = None,
) -> StrategySummary:
    x = output.returns.dropna().astype(float)
    base = _annualization_base(config, annualization_mode)

    if x.empty:
        return StrategySummary(output.name, np.nan, np.nan, np.nan, np.nan, 0)

    mean_daily = float(x.mean())
    std_daily = float(x.std(ddof=1))
    ar = annualize_mean(mean_daily, base) * 100.0
    risk = annualize_vol(std_daily, base) * 100.0
    rr = ar / risk if np.isfinite(risk) and risk > 0.0 else np.nan

    mdd_kind = _mdd_mode(config, mdd_mode)
    if mdd_kind == "running_peak":
        mdd = running_mdd(x) * 100.0
    elif mdd_kind == "paper_formula":
        mdd = paper_formula_mdd(x) * 100.0
    else:
        raise ValueError(f"Unknown MDD mode: {mdd_kind}")

    return StrategySummary(
        strategy=output.name,
        ar=ar,
        risk=risk,
        rr=rr,
        mdd=mdd,
        n_obs=int(x.shape[0]),
    )

def summarize_bundle(
    bundle: BacktestBundle,
    config: ReproConfig,
    annualization_mode: AnnualizationMode = "main",
    mdd_mode: MDDMode | None = None,
) -> pd.DataFrame:
    outputs = [bundle.mom, bundle.pca_plain, bundle.pca_sub, bundle.double]
    rows = []
    for out in outputs:
        s = summarize_strategy(out, config, annualization_mode=annualization_mode, mdd_mode=mdd_mode)
        rows.append(
            {
                "Strategy": s.strategy,
                "AR": s.ar,
                "RISK": s.risk,
                "R/R": s.rr,
                "MDD": s.mdd,
                "N": s.n_obs,
            }
        )
    return pd.DataFrame(rows)

def cumulative_returns(returns: pd.Series) -> pd.Series:
    returns = returns.dropna().astype(float)
    if returns.empty:
        return pd.Series(dtype=float)
    return (1.0 + returns).cumprod()

def compare_with_table2_targets(summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    target_map = TABLE2_TARGET
    for _, row in summary.iterrows():
        strategy = str(row["Strategy"])
        target = target_map.get(strategy)
        if target is None:
            continue
        rows.append(
            {
                "Strategy": strategy,
                "AR_actual": row["AR"],
                "AR_target": target["AR"],
                "AR_gap": row["AR"] - target["AR"],
                "RISK_actual": row["RISK"],
                "RISK_target": target["RISK"],
                "RISK_gap": row["RISK"] - target["RISK"],
                "R/R_actual": row["R/R"],
                "R/R_target": target["R/R"],
                "R/R_gap": row["R/R"] - target["R/R"],
                "MDD_actual": row["MDD"],
                "MDD_target": target["MDD"],
                "MDD_gap": row["MDD"] - target["MDD"],
                "N": row.get("N", np.nan),
            }
        )
    return pd.DataFrame(rows)
