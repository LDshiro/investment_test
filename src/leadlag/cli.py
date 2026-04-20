from __future__ import annotations

import argparse
import json
from pathlib import Path

from leadlag.config.loader import load_app_config
from leadlag.data_contract import validate_corrected_bundle, write_validation_outputs
from leadlag.ops import render_runbook_artifacts, validate_shadow_replay
from leadlag.runtime.packets import ensure_packet_layout
from leadlag.runtime.corrected_backtest import inspect_corrected_bundle, run_corrected_backtest
from leadlag.runtime.corrected_shadow import run_corrected_shadow
from leadlag.runtime.corrected_shadow_batch import run_corrected_shadow_batch
from leadlag.reporting.weekly_rule_calibration import calibrate_weekly_rules
from leadlag.reporting.weekly_review import generate_weekly_review
from leadlag.reporting.weekly_rules import generate_weekly_gates


def cmd_validate_config(config_path: str) -> int:
    cfg = load_app_config(Path(config_path))
    print(f"config ok: name={cfg.run.name} mode={cfg.run.mode} source={cfg.data.source}")
    return 0


def cmd_inspect_bundle(config_path: str) -> int:
    cfg = load_app_config(Path(config_path))
    info = inspect_corrected_bundle(cfg)
    print(json.dumps(info['summary'], ensure_ascii=False, indent=2))
    return 0


def cmd_validate_data_contract(bundle_dir: str, contract_path: str, output_dir: str) -> int:
    result = validate_corrected_bundle(Path(bundle_dir), Path(contract_path))
    write_validation_outputs(result, Path(output_dir))
    print(
        json.dumps(
            {
                "passed": result.passed,
                "issue_counts": result.issue_counts(),
                "output_dir": str(Path(output_dir).resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.passed else 1


def cmd_validate_shadow_replay(batch_dir: str, validation_config: str, output_dir: str) -> int:
    result = validate_shadow_replay(
        batch_dir=Path(batch_dir),
        validation_config=Path(validation_config),
        output_dir=Path(output_dir),
    )
    print(
        json.dumps(
            {
                "status": result.status,
                "passed": result.passed,
                "summary": result.summary,
                "output_dir": str(Path(output_dir).resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.status != "FAIL" else 1


def cmd_render_runbook(config_path: str, output_dir: str) -> int:
    result = render_runbook_artifacts(
        path_or_dict=Path(config_path),
        output_dir=Path(output_dir),
    )
    print(
        json.dumps(
            {
                "passed": result.passed,
                "issue_counts": result.issue_counts(),
                "summary": result.summary,
                "output_paths": result.output_paths,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.passed else 1


def cmd_run(config_path: str, trade_date: str | None = None) -> int:
    cfg = load_app_config(Path(config_path))
    if cfg.run.mode == 'backtest' and cfg.data.source == 'corrected_bundle':
        packet_dir, status = run_corrected_backtest(cfg)
        print(f"backtest completed: {packet_dir}")
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0
    if cfg.run.mode == 'shadow' and cfg.data.source == 'corrected_bundle':
        packet_dir, status = run_corrected_shadow(cfg, trade_date_override=trade_date)
        print(f"shadow run completed: {packet_dir}")
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0
    packet_dir = ensure_packet_layout(cfg)
    print(f"run scaffold ready: {packet_dir}")
    print('next step: wire shadow/live adapters')
    return 0



def cmd_run_batch(config_path: str) -> int:
    cfg = load_app_config(Path(config_path))
    if cfg.run.mode == 'shadow' and cfg.data.source == 'corrected_bundle':
        batch_dir, status = run_corrected_shadow_batch(cfg)
        print(f"shadow batch completed: {batch_dir}")
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0
    raise RuntimeError('run-batch currently supports corrected_bundle shadow mode only')


def cmd_weekly_review(batch_summary: str | None, batch_dir: str | None, output_dir: str | None) -> int:
    out_dir, status = generate_weekly_review(
        batch_summary_path=batch_summary,
        batch_dir=batch_dir,
        output_dir=output_dir,
    )
    print(f"weekly review completed: {out_dir}")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0




def cmd_weekly_gates(weekly_summary: str | None, review_dir: str | None, rules_config: str, output_dir: str | None) -> int:
    out_dir, status = generate_weekly_gates(
        weekly_summary_path=weekly_summary,
        review_dir=review_dir,
        rules_config_path=rules_config,
        output_dir=output_dir,
    )
    print(f"weekly gates completed: {out_dir}")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


def cmd_weekly_rule_calibration(weekly_review_dirs: list[str], rules_configs: list[str], output_dir: str) -> int:
    out_dir, status = calibrate_weekly_rules(
        weekly_review_dirs=weekly_review_dirs,
        rules_config_paths=rules_configs,
        output_dir=output_dir,
    )
    print(f"weekly rule calibration completed: {out_dir}")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='leadlag')
    sub = parser.add_subparsers(dest='command', required=True)

    p_validate = sub.add_parser('validate-config')
    p_validate.add_argument('--config', required=True)

    p_inspect = sub.add_parser('inspect-bundle')
    p_inspect.add_argument('--config', required=True)

    p_data_contract = sub.add_parser('validate-data-contract')
    p_data_contract.add_argument('--bundle-dir', required=True)
    p_data_contract.add_argument('--contract', required=True)
    p_data_contract.add_argument('--output-dir', required=True)

    p_shadow_replay = sub.add_parser('validate-shadow-replay')
    p_shadow_replay.add_argument('--batch-dir', required=True)
    p_shadow_replay.add_argument('--validation-config', required=True)
    p_shadow_replay.add_argument('--output-dir', required=True)

    p_runbook = sub.add_parser('render-runbook')
    p_runbook.add_argument('--config', required=True)
    p_runbook.add_argument('--output-dir', required=True)

    p_run = sub.add_parser('run')
    p_run.add_argument('--config', required=True)
    p_run.add_argument('--trade-date', required=False)

    p_run_batch = sub.add_parser('run-batch')
    p_run_batch.add_argument('--config', required=True)

    p_weekly = sub.add_parser('weekly-review')
    p_weekly.add_argument('--batch-summary', required=False)
    p_weekly.add_argument('--batch-dir', required=False)
    p_weekly.add_argument('--output-dir', required=False)

    p_gates = sub.add_parser('weekly-gates')
    p_gates.add_argument('--weekly-summary', required=False)
    p_gates.add_argument('--review-dir', required=False)
    p_gates.add_argument('--rules-config', required=True)
    p_gates.add_argument('--output-dir', required=False)

    p_calibration = sub.add_parser('weekly-rule-calibration')
    p_calibration.add_argument('--weekly-review-dir', action='append', required=True)
    p_calibration.add_argument('--rules-config', action='append', required=True)
    p_calibration.add_argument('--output-dir', required=True)
    return parser



def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == 'validate-config':
        return cmd_validate_config(args.config)
    if args.command == 'inspect-bundle':
        return cmd_inspect_bundle(args.config)
    if args.command == 'validate-data-contract':
        return cmd_validate_data_contract(args.bundle_dir, args.contract, args.output_dir)
    if args.command == 'validate-shadow-replay':
        return cmd_validate_shadow_replay(args.batch_dir, args.validation_config, args.output_dir)
    if args.command == 'render-runbook':
        return cmd_render_runbook(args.config, args.output_dir)
    if args.command == 'run':
        return cmd_run(args.config, trade_date=args.trade_date)
    if args.command == 'run-batch':
        return cmd_run_batch(args.config)
    if args.command == 'weekly-review':
        return cmd_weekly_review(args.batch_summary, args.batch_dir, args.output_dir)
    if args.command == 'weekly-gates':
        return cmd_weekly_gates(args.weekly_summary, args.review_dir, args.rules_config, args.output_dir)
    if args.command == 'weekly-rule-calibration':
        return cmd_weekly_rule_calibration(args.weekly_review_dir, args.rules_config, args.output_dir)
    parser.error('unknown command')
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
