from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from datetime import date

from pydantic import BaseModel, Field


class RunSection(BaseModel):
    name: str
    mode: Literal["backtest", "shadow", "live_dryrun", "live"]
    timezone: str = "Asia/Tokyo"
    seed: int = 42
    write_daily_packet: bool = True
    runs_root: str = "./runs"
    logs_root: str = "./logs"
    historical_trade_date: Optional[date] = None
    shadow_nav_jpy: float = 1_000_000.0


class CalendarSection(BaseModel):
    mode: Literal["paper_mode", "robust_mode"] = "paper_mode"
    timezone_us: str = "America/New_York"
    timezone_jp: str = "Asia/Tokyo"


class DataSection(BaseModel):
    source: str
    root: str
    files: Dict[str, str] = Field(default_factory=dict)


class UniverseSection(BaseModel):
    us_core: List[str]
    us_extended: List[str]
    jp: List[str]


class SampleSection(BaseModel):
    enforce_table1_counts: bool = True
    table1_target: Dict[str, int] = Field(default_factory=dict)
    sample_filter_source: str = "common_dates_core"
    cfull_window_start: date = date(2010, 1, 1)
    cfull_window_end: date = date(2014, 12, 31)
    filter_mode: Optional[str] = None
    report_table1_like: bool = False


class StrategySection(BaseModel):
    name: str
    lookback_L: int
    n_components_K: int
    prior_dim_K0: int
    lambda_reg: float
    quantile_q: float
    target_return: Optional[str] = None
    predictor_return: Optional[str] = None
    weighting: Optional[str] = None
    annualization_days: Optional[int] = 252
    metrics: Dict[str, Any] = Field(default_factory=dict)
    priors: Dict[str, Any] = Field(default_factory=dict)
    cfull_policy: Optional[str] = None


class CostsSection(BaseModel):
    commission_bps: float = 0.0
    open_half_spread_bps: float = 0.0
    close_half_spread_bps: float = 0.0
    slippage_open_bps: float = 0.0
    slippage_close_bps: float = 0.0
    borrow_fee_bps_annual: float = 0.0
    notes: Optional[str] = None


class RiskSection(BaseModel):
    max_gross: float = 1.0
    max_net: float = 0.0
    max_single_name_abs: float = 0.15
    min_tradable_names: int = 6
    max_expected_cost_bps: float = 35.0
    halt_on_missing_price: bool = True
    halt_on_unapproved_patch: bool = True
    halt_on_universe_shrinkage: bool = True
    allow_short: bool = False
    hard_gates: List[str] = Field(default_factory=list)


class BatchSection(BaseModel):
    enabled: bool = False
    date_source: Literal["sample_filter", "strategy_index", "explicit"] = "sample_filter"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    trade_dates: List[date] = Field(default_factory=list)
    max_days: Optional[int] = None
    skip_existing_packets: bool = True
    stop_on_error: bool = True
    write_batch_summary: bool = True


class BrokerSection(BaseModel):
    kind: str = "null"
    paper_sync: bool = False
    dry_run_only: bool = True
    host_env: Optional[str] = None
    password_env: Optional[str] = None
    port_env: Optional[str] = None
    client_id_env: Optional[str] = None
    account_mode: Optional[str] = None


class PacketSection(BaseModel):
    schema_version: int = 1
    summary_template: str = "default"
    include_charts: bool = True
    write_csv: bool = True
    write_json: bool = True
    required_files: List[str] = Field(default_factory=list)
    optional_files: List[str] = Field(default_factory=list)


class RuntimeSection(BaseModel):
    jobs: List[str] = Field(default_factory=list)


class AppConfig(BaseModel):
    run: RunSection
    calendar: CalendarSection
    data: DataSection
    universe: UniverseSection
    sample: SampleSection
    strategy: StrategySection
    costs: CostsSection
    risk: RiskSection
    broker: BrokerSection
    packet: PacketSection
    batch: BatchSection = Field(default_factory=BatchSection)
    runtime: RuntimeSection = Field(default_factory=RuntimeSection)
