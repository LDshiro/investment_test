from __future__ import annotations

from typing import List, Tuple

import pandas as pd


def long_short_equal_weight(signal: pd.Series, quantile_q: float, allow_short: bool = True) -> pd.Series:
    signal = signal.dropna().sort_values(ascending=False)
    if signal.empty:
        return pd.Series(dtype=float)
    n = len(signal)
    k = max(1, int(n * quantile_q))
    long_names = signal.index[:k]
    short_names = signal.index[-k:] if allow_short else []
    w = pd.Series(0.0, index=signal.index, dtype=float)
    if len(long_names) > 0:
        w.loc[list(long_names)] = 1.0 / len(long_names)
    if allow_short and len(short_names) > 0:
        w.loc[list(short_names)] = -1.0 / len(short_names)
    return w


def scale_weights_to_limits(
    weights: pd.Series,
    max_gross: float,
    max_single_name_abs: float,
) -> Tuple[pd.Series, List[dict]]:
    w = weights.copy().fillna(0.0).astype(float)
    adjustments: List[dict] = []
    if w.empty:
        return w, adjustments

    max_abs = float(w.abs().max()) if not w.empty else 0.0
    if max_single_name_abs > 0.0 and max_abs > max_single_name_abs:
        factor = max_single_name_abs / max_abs
        w *= factor
        adjustments.append(
            {
                "severity": "warning",
                "code": "scaled_for_single_name_cap",
                "message": f"Scaled weights by {factor:.6f} to satisfy max_single_name_abs={max_single_name_abs:.4f}.",
                "factor": factor,
            }
        )

    gross = float(w.abs().sum()) if not w.empty else 0.0
    if max_gross > 0.0 and gross > max_gross:
        factor = max_gross / gross
        w *= factor
        adjustments.append(
            {
                "severity": "warning",
                "code": "scaled_for_gross_cap",
                "message": f"Scaled weights by {factor:.6f} to satisfy max_gross={max_gross:.4f}.",
                "factor": factor,
            }
        )

    return w, adjustments
