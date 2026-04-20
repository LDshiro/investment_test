
"""Reproduction package for the paper:
Lead-lag strategies for Japanese and U.S. sectors using subspace regularization PCA.

This package is designed for local Yahoo Finance CSV exports and optional Kenneth French
factor files. It also contains synthetic smoke tests so the mathematical pipeline can be
validated without market downloads.
"""

from .config import ReproConfig
from .tickers import US_TICKERS, JP_TICKERS, ALL_TICKERS

__all__ = ["ReproConfig", "US_TICKERS", "JP_TICKERS", "ALL_TICKERS"]
