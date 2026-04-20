from __future__ import annotations

import numpy as np

from leadlag.config.models import AppConfig


def build_prior_basis(cfg: AppConfig, asset_order: list[str]) -> np.ndarray:
    n = len(asset_order)
    v1 = np.ones(n)

    us = set(cfg.universe.us_core + cfg.universe.us_extended)
    jp = set(cfg.universe.jp)
    v2 = np.array([1.0 if a in us else -1.0 if a in jp else 0.0 for a in asset_order])

    cyc = set(cfg.strategy.priors.get("cyc_def", {}).get("us_cyclical", [])) | set(
        cfg.strategy.priors.get("cyc_def", {}).get("jp_cyclical", [])
    )
    defensive = set(cfg.strategy.priors.get("cyc_def", {}).get("us_defensive", [])) | set(
        cfg.strategy.priors.get("cyc_def", {}).get("jp_defensive", [])
    )
    v3 = np.array([1.0 if a in cyc else -1.0 if a in defensive else 0.0 for a in asset_order])

    V = np.column_stack([v1, v2, v3]).astype(float)
    # simple Gram-Schmidt
    for i in range(V.shape[1]):
        for j in range(i):
            V[:, i] -= V[:, j] * (V[:, j] @ V[:, i])
        norm = np.linalg.norm(V[:, i])
        if norm > 0:
            V[:, i] /= norm
    return V
