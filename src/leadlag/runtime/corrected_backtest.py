from __future__ import annotations

from pathlib import Path
import json

import pandas as pd

from leadlag.config.models import AppConfig
from leadlag.runtime.packets import ensure_packet_layout
from leadlag_repro.corrected_bundle import (
    load_corrected_bundle as legacy_load_corrected_bundle,
    find_table1_sample_filter,
    basic_stats_in_dates,
    run_corrected_bundle_reproduction,
)


def inspect_corrected_bundle(cfg: AppConfig) -> dict[str, object]:
    loaded = legacy_load_corrected_bundle(Path(cfg.data.root))
    cc = loaded["cc"]
    oc = loaded["oc_jp"]
    sample = find_table1_sample_filter(cc, loaded["core_dates"])
    table1_like = basic_stats_in_dates(cc, sample.dates, annualization_base=252)
    summary = {
        "bundle_root": str(Path(cfg.data.root).resolve()),
        "cc_shape": list(cc.shape),
        "oc_shape": list(oc.shape),
        "core_dates_n": int(len(loaded["core_dates"])),
        "full_dates_n": int(len(loaded["full_dates"])),
        "sample_filter_start": str(sample.start.date()),
        "sample_filter_end": str(sample.end.date()),
        "sample_filter_exact": bool(sample.exact_match),
        "sample_filter_score": int(sample.score),
        "table1_gap_sum": int(sample.table1_counts["gap"].abs().sum()),
    }
    return {
        "summary": summary,
        "table1_counts": sample.table1_counts,
        "table1_like_stats": table1_like,
    }


def run_corrected_backtest(cfg: AppConfig) -> tuple[Path, dict[str, object]]:
    packet_dir = ensure_packet_layout(cfg)
    out_dir = packet_dir / "backtest_outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    status = run_corrected_bundle_reproduction(Path(cfg.data.root), out_dir)

    (packet_dir / "run.json").write_text(
        json.dumps(
            {
                "mode": cfg.run.mode,
                "name": cfg.run.name,
                "data_root": cfg.data.root,
                "status": status,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    table2 = pd.read_csv(out_dir / "table2_main.csv")
    lines = [
        f"# {cfg.run.name}",
        "",
        f"- mode: {cfg.run.mode}",
        f"- data_root: {cfg.data.root}",
        f"- sample filter: {status['sample_filter_start']} -> {status['sample_filter_end']}",
        f"- exact Table1 match: {status['sample_filter_exact']}",
        f"- Table1 gap sum: {status['table1_counts_gap_sum']}",
        "",
        "## Table 2 main",
        "",
        table2.to_markdown(index=False),
        "",
        f"Detailed outputs: {out_dir.name}/",
    ]
    (packet_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    return packet_dir, status
