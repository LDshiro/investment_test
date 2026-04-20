
from __future__ import annotations

US_TICKERS = [
    "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"
]

JP_TICKERS = [
    "1617.T", "1618.T", "1619.T", "1620.T", "1621.T", "1622.T", "1623.T", "1624.T",
    "1625.T", "1626.T", "1627.T", "1628.T", "1629.T", "1630.T", "1631.T", "1632.T",
    "1633.T",
]

ALL_TICKERS = US_TICKERS + JP_TICKERS

US_CYCLICAL = {"XLB", "XLE", "XLF", "XLRE"}
US_DEFENSIVE = {"XLK", "XLP", "XLU", "XLV"}

JP_CYCLICAL = {"1618.T", "1625.T", "1629.T", "1631.T"}
JP_DEFENSIVE = {"1617.T", "1621.T", "1627.T", "1630.T"}

TABLE1_TARGET_COUNTS = {
    **{t: 2590 for t in JP_TICKERS},
    "XLB": 2590,
    "XLC": 1758,
    "XLE": 2590,
    "XLF": 2590,
    "XLI": 2590,
    "XLK": 2590,
    "XLP": 2590,
    "XLRE": 2409,
    "XLU": 2590,
    "XLV": 2590,
    "XLY": 2590,
}

TABLE2_TARGET = {
    "MOM": {"AR": 5.63, "RISK": 10.59, "R/R": 0.53, "MDD": 16.97},
    "PCA_PLAIN": {"AR": 6.24, "RISK": 9.94, "R/R": 0.62, "MDD": 23.65},
    "PCA_SUB": {"AR": 23.79, "RISK": 10.70, "R/R": 2.22, "MDD": 9.58},
    "DOUBLE": {"AR": 18.86, "RISK": 11.16, "R/R": 1.69, "MDD": 12.10},
}
