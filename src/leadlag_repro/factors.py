
from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile
import io
import re

import pandas as pd

def _read_text_from_path(path: Path, encoding: str = "utf-8") -> str:
    if path.suffix.lower() == ".zip":
        with ZipFile(path) as zf:
            names = [n for n in zf.namelist() if n.lower().endswith((".csv", ".txt"))]
            if not names:
                raise ValueError(f"No CSV/TXT found inside {path}")
            with zf.open(names[0]) as f:
                return f.read().decode(encoding, errors="ignore")
    return path.read_text(encoding=encoding, errors="ignore")

def _extract_daily_factor_section(text: str) -> pd.DataFrame:
    """
    Kenneth French files contain header commentary, then a daily section with YYYYMMDD rows.
    This parser finds the first block whose first field is 8 digits and reads until that stops.
    """
    lines = [ln.strip() for ln in text.splitlines()]
    start_idx = None
    for i, ln in enumerate(lines):
        parts = [p.strip() for p in re.split(r",\s*|\s{2,}|\t+", ln) if p.strip() != ""]
        if parts and re.fullmatch(r"\d{8}", parts[0]):
            start_idx = i
            break
    if start_idx is None:
        raise ValueError("Could not find daily YYYYMMDD section in factor file.")

    header_idx = start_idx - 1
    # Backtrack to probable header line
    while header_idx >= 0 and not re.search(r"(Mkt|SMB|HML|Mom|WML|RF|Date)", lines[header_idx], re.I):
        header_idx -= 1
    if header_idx < 0:
        raise ValueError("Could not find factor header line above daily section.")

    block = []
    for ln in lines[header_idx:]:
        parts = [p.strip() for p in re.split(r",\s*|\s{2,}|\t+", ln) if p.strip() != ""]
        if not parts:
            if block:
                break
            continue
        if len(block) > 0 and not re.fullmatch(r"\d{8}", parts[0]):
            break
        block.append(",".join(parts))

    csv_text = "\n".join(block)
    df = pd.read_csv(io.StringIO(csv_text))
    first = df.columns[0]
    df = df.rename(columns={first: "Date"})
    df["Date"] = pd.to_datetime(df["Date"].astype(str), format="%Y%m%d")
    df = df.set_index("Date").sort_index()

    # Convert percent to decimal.
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce") / 100.0
    df = df.dropna(how="all")
    return df

def read_kenneth_french_daily(path: Path) -> pd.DataFrame:
    text = _read_text_from_path(Path(path))
    return _extract_daily_factor_section(text)

def load_japan_ff3_and_mom(factor_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    factor_root = Path(factor_root)
    ff3_candidates = [
        factor_root / "F-F_Research_Data_Factors_Japan_Daily.csv",
        factor_root / "F-F_Research_Data_Factors_Japan_Daily.CSV",
        factor_root / "F-F_Research_Data_Factors_Japan_Daily.zip",
        factor_root / "F-F_Research_Data_Factors_Japan_daily.csv",
        factor_root / "F-F_Research_Data_Factors_Japan_daily.zip",
    ]
    mom_candidates = [
        factor_root / "F-F_Momentum_Factor_Japan_Daily.csv",
        factor_root / "F-F_Momentum_Factor_Japan_Daily.zip",
        factor_root / "Japanese_Momentum_Factor_Daily.csv",
        factor_root / "Japanese_Momentum_Factor_Daily.zip",
    ]

    ff3_path = next((p for p in ff3_candidates if p.exists()), None)
    mom_path = next((p for p in mom_candidates if p.exists()), None)
    if ff3_path is None:
        raise FileNotFoundError("Japanese FF3 daily file not found in factor_root.")
    if mom_path is None:
        raise FileNotFoundError("Japanese daily momentum file not found in factor_root.")

    ff3 = read_kenneth_french_daily(ff3_path)
    mom = read_kenneth_french_daily(mom_path)

    # Harmonize momentum column name
    if "WML" in mom.columns:
        mom = mom.rename(columns={"WML": "Mom"})
    elif "Mom" not in mom.columns:
        mom = mom.rename(columns={mom.columns[0]: "Mom"})

    return ff3, mom[["Mom"]]
