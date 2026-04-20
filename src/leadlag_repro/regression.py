
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .utils import annualize_mean

@dataclass(slots=True)
class RegressionResult:
    model_name: str
    alpha_annual_pct: float
    alpha_t: float
    coeffs: dict[str, float]
    tstats: dict[str, float]
    adj_r2: float
    n_obs: int
    nw_lag: int

def hac_ols(
    y: pd.Series,
    x: pd.DataFrame,
    nw_lag: int,
    annualization_base: int,
    subtract_rf: bool = False,
) -> RegressionResult:
    df = pd.concat([y.rename("strategy"), x], axis=1).dropna()
    if df.empty:
        raise ValueError("No overlapping observations for regression.")

    yv = df["strategy"].copy()
    if subtract_rf and "RF" in df.columns:
        yv = yv - df["RF"]

    x_cols = [c for c in df.columns if c not in ("strategy", "RF")]
    xv = sm.add_constant(df[x_cols], has_constant="add")
    fit = sm.OLS(yv, xv).fit(cov_type="HAC", cov_kwds={"maxlags": nw_lag})

    alpha_daily = float(fit.params["const"])
    alpha_t = float(fit.tvalues["const"])

    coeffs = {c: float(fit.params[c]) for c in x_cols}
    tstats = {c: float(fit.tvalues[c]) for c in x_cols}

    return RegressionResult(
        model_name="+".join(x_cols),
        alpha_annual_pct=annualize_mean(alpha_daily, annualization_base) * 100.0,
        alpha_t=alpha_t,
        coeffs=coeffs,
        tstats=tstats,
        adj_r2=float(fit.rsquared_adj),
        n_obs=int(fit.nobs),
        nw_lag=int(nw_lag),
    )

def ff3_regression(
    strategy_returns: pd.Series,
    ff3: pd.DataFrame,
    annualization_base: int,
    nw_lag: int,
    subtract_rf: bool = False,
) -> RegressionResult:
    factor_cols = [c for c in ff3.columns if c in ("Mkt-RF", "SMB", "HML", "RF")]
    if "Mkt-RF" not in factor_cols:
        # Common alternative spellings
        rename = {}
        for c in ff3.columns:
            if c.replace(" ", "").upper() in {"MKT-RF", "MKT_RF"}:
                rename[c] = "Mkt-RF"
        ff3 = ff3.rename(columns=rename)
        factor_cols = [c for c in ff3.columns if c in ("Mkt-RF", "SMB", "HML", "RF")]
    return hac_ols(
        strategy_returns,
        ff3[factor_cols],
        nw_lag=nw_lag,
        annualization_base=annualization_base,
        subtract_rf=subtract_rf,
    )

def carhart4_regression(
    strategy_returns: pd.Series,
    ff3: pd.DataFrame,
    mom: pd.DataFrame,
    annualization_base: int,
    nw_lag: int,
    subtract_rf: bool = False,
) -> RegressionResult:
    merged = ff3.join(mom, how="inner")
    if "WML" in merged.columns and "Mom" not in merged.columns:
        merged = merged.rename(columns={"WML": "Mom"})
    factor_cols = [c for c in ("Mkt-RF", "SMB", "HML", "Mom", "RF") if c in merged.columns]
    return hac_ols(
        strategy_returns,
        merged[factor_cols],
        nw_lag=nw_lag,
        annualization_base=annualization_base,
        subtract_rf=subtract_rf,
    )

def result_to_row(strategy_name: str, result: RegressionResult) -> dict[str, float | int | str]:
    row: dict[str, float | int | str] = {
        "Strategy": strategy_name,
        "alpha (%/yr)": result.alpha_annual_pct,
        "alpha t": result.alpha_t,
        "Adj. R2": result.adj_r2,
        "N": result.n_obs,
        "NW lag": result.nw_lag,
    }
    for k, v in result.coeffs.items():
        row[k] = v
    for k, v in result.tstats.items():
        row[f"{k} t"] = v
    return row
