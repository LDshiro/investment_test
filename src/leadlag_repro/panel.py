
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from .tickers import US_TICKERS, JP_TICKERS, ALL_TICKERS

FieldMode = Literal["ret_cc_adj", "ret_cc_raw", "ret_oc_adj", "ret_oc_raw"]

@dataclass(slots=True)
class EvalWindow:
    start: pd.Timestamp
    end: pd.Timestamp
    majority_dates: pd.DatetimeIndex

def stack_field(data: dict[str, pd.DataFrame], field: str, tickers: list[str] | None = None) -> pd.DataFrame:
    tickers = ALL_TICKERS if tickers is None else tickers
    series = []
    for ticker in tickers:
        df = data[ticker]
        s = df[field].rename(ticker)
        series.append(s)
    panel = pd.concat(series, axis=1).sort_index()
    return panel

def stack_price_field(data: dict[str, pd.DataFrame], field: str, tickers: list[str] | None = None) -> pd.DataFrame:
    tickers = ALL_TICKERS if tickers is None else tickers
    series = []
    for ticker in tickers:
        df = data[ticker]
        s = df[field].rename(ticker)
        series.append(s)
    panel = pd.concat(series, axis=1).sort_index()
    return panel

def complete_intersection_dates(
    data: dict[str, pd.DataFrame],
    tickers: list[str],
    field: str,
    start: str | None = None,
    end: str | None = None,
) -> pd.DatetimeIndex:
    panel = stack_field(data, field, tickers)
    if start is not None:
        panel = panel.loc[pd.Timestamp(start):]
    if end is not None:
        panel = panel.loc[:pd.Timestamp(end)]
    mask = panel.notna().all(axis=1)
    return panel.index[mask]

def infer_majority_eval_window(
    data: dict[str, pd.DataFrame],
    majority_tickers: list[str],
    field: str,
    target_count: int,
    end: str | None = None,
) -> EvalWindow:
    dates = complete_intersection_dates(data, majority_tickers, field, end=end)
    if len(dates) < target_count:
        raise ValueError(
            f"Not enough complete dates ({len(dates)}) for target count {target_count}."
        )
    majority_dates = dates[-target_count:]
    return EvalWindow(
        start=majority_dates[0],
        end=majority_dates[-1],
        majority_dates=majority_dates,
    )

def counts_in_window(
    data: dict[str, pd.DataFrame],
    field: str,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    tickers: list[str] | None = None,
) -> pd.Series:
    panel = stack_field(data, field, tickers)
    panel = panel.loc[pd.Timestamp(start):pd.Timestamp(end)]
    return panel.notna().sum(axis=0)

def basic_stats_in_window(
    data: dict[str, pd.DataFrame],
    field: str,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    annualization_base: int,
    tickers: list[str] | None = None,
) -> pd.DataFrame:
    from .utils import raw_kurtosis
    panel = stack_field(data, field, tickers).loc[pd.Timestamp(start):pd.Timestamp(end)]
    rows = []
    for ticker in panel.columns:
        x = panel[ticker].dropna()
        rows.append(
            {
                "Ticker": ticker,
                "Ret (%)": x.mean() * annualization_base * 100.0,
                "Vol (%)": x.std(ddof=1) * np.sqrt(annualization_base) * 100.0,
                "Ret/Vol": (x.mean() * annualization_base) / (x.std(ddof=1) * np.sqrt(annualization_base))
                if x.std(ddof=1) > 0.0 else np.nan,
                "Skew": x.skew(),
                "Kurtosis": raw_kurtosis(x),
                "N": int(x.shape[0]),
            }
        )
    return pd.DataFrame(rows).sort_values("Ticker").reset_index(drop=True)

def common_calendar_for_paper_mode(
    data: dict[str, pd.DataFrame],
    field: str,
    us_tickers: list[str] | None = None,
    jp_tickers: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    dynamic_assets: bool = True,
) -> pd.DatetimeIndex:
    """
    For 'paper mode' we use a common calendar of dates that exist in both countries.
    If dynamic_assets=True, we intersect country-level dates rather than ticker-level dates.
    This keeps the daily country calendar stable while allowing tickers like XLC/XLRE to enter later.
    """
    us_tickers = US_TICKERS if us_tickers is None else us_tickers
    jp_tickers = JP_TICKERS if jp_tickers is None else jp_tickers

    if dynamic_assets:
        us_panel = stack_field(data, field, us_tickers)
        jp_panel = stack_field(data, field, jp_tickers)
        if start is not None:
            us_panel = us_panel.loc[pd.Timestamp(start):]
            jp_panel = jp_panel.loc[pd.Timestamp(start):]
        if end is not None:
            us_panel = us_panel.loc[:pd.Timestamp(end)]
            jp_panel = jp_panel.loc[:pd.Timestamp(end)]
        us_dates = us_panel.index[us_panel.notna().any(axis=1)]
        jp_dates = jp_panel.index[jp_panel.notna().any(axis=1)]
        dates = us_dates.intersection(jp_dates)
        return dates
    return complete_intersection_dates(data, us_tickers + jp_tickers, field, start, end)

def first_next_jp_dates(us_dates: pd.DatetimeIndex, jp_dates: pd.DatetimeIndex) -> pd.Series:
    jp_arr = np.array(jp_dates)
    positions = np.searchsorted(jp_arr, np.array(us_dates), side="right")
    mapped = []
    for pos in positions:
        if pos >= len(jp_arr):
            mapped.append(pd.NaT)
        else:
            mapped.append(pd.Timestamp(jp_arr[pos]))
    return pd.Series(mapped, index=us_dates, name="jp_next_date")

def robust_pair_table(
    data: dict[str, pd.DataFrame],
    field: str,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    us_panel = stack_field(data, field, US_TICKERS)
    jp_panel = stack_field(data, field, JP_TICKERS)
    if start is not None:
        us_panel = us_panel.loc[pd.Timestamp(start):]
        jp_panel = jp_panel.loc[pd.Timestamp(start):]
    if end is not None:
        us_panel = us_panel.loc[:pd.Timestamp(end)]
        jp_panel = jp_panel.loc[:pd.Timestamp(end)]
    us_dates = us_panel.index[us_panel.notna().any(axis=1)]
    jp_dates = jp_panel.index[jp_panel.notna().any(axis=1)]
    jp_next = first_next_jp_dates(us_dates, jp_dates)
    out = pd.DataFrame({"us_date": us_dates, "jp_next_date": jp_next.values})
    out = out.dropna().reset_index(drop=True)
    return out
