
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .tickers import ALL_TICKERS
from .utils import candidate_csv_paths, first_existing_path, ensure_datetime_index

YAHOO_REQUIRED_COLUMNS = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]

def read_single_yahoo_csv(path: Path, ticker: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = ensure_datetime_index(df, "Date")

    missing = [c for c in YAHOO_REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{path} is missing Yahoo columns: {missing}")

    out = pd.DataFrame(index=df.index)
    out["ticker"] = ticker
    out["raw_open"] = pd.to_numeric(df["Open"], errors="coerce")
    out["raw_high"] = pd.to_numeric(df["High"], errors="coerce")
    out["raw_low"] = pd.to_numeric(df["Low"], errors="coerce")
    out["raw_close"] = pd.to_numeric(df["Close"], errors="coerce")
    out["adj_close"] = pd.to_numeric(df["Adj Close"], errors="coerce")
    out["volume"] = pd.to_numeric(df["Volume"], errors="coerce")

    out = out.dropna(subset=["raw_open", "raw_high", "raw_low", "raw_close", "adj_close"])
    out = out.loc[out["raw_close"] > 0.0].copy()

    out["adj_factor"] = out["adj_close"] / out["raw_close"]
    out["adj_open"] = out["raw_open"] * out["adj_factor"]
    out["adj_high"] = out["raw_high"] * out["adj_factor"]
    out["adj_low"] = out["raw_low"] * out["adj_factor"]

    # Simple returns
    out["ret_cc_raw"] = out["raw_close"].pct_change()
    out["ret_cc_adj"] = out["adj_close"].pct_change()

    # Open-to-close ratio on the same adjustment basis
    out["ret_oc_raw"] = out["raw_close"] / out["raw_open"] - 1.0
    out["ret_oc_adj"] = out["adj_close"] / out["adj_open"] - 1.0

    return out.sort_index()

def discover_yahoo_csv(root: Path, ticker: str) -> Path:
    path = first_existing_path(candidate_csv_paths(root, ticker))
    if path is None:
        tried = ", ".join(str(p) for p in candidate_csv_paths(root, ticker))
        raise FileNotFoundError(f"Could not find CSV for {ticker}. Tried: {tried}")
    return path

def load_yahoo_universe(root: Path, tickers: list[str] | None = None) -> dict[str, pd.DataFrame]:
    tickers = ALL_TICKERS if tickers is None else tickers
    root = Path(root)
    data: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        path = discover_yahoo_csv(root, ticker)
        data[ticker] = read_single_yahoo_csv(path, ticker)
    return data

def available_date_bounds(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for ticker, df in data.items():
        rows.append(
            {
                "ticker": ticker,
                "start": df.index.min(),
                "end": df.index.max(),
                "n_rows": int(df.shape[0]),
            }
        )
    return pd.DataFrame(rows).sort_values("ticker").reset_index(drop=True)
