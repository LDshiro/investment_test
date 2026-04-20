# Broker Dry-Run Calibration v1

Step 12 の calibration は、Step 11 で生成した shadow-only / dry-run-only artifacts を再読込して、`orders_shadow.csv` の open-leg rows が broker-neutral intents、NullBroker payloads、NullBroker acknowledgements と一対一で整合するかを確認する手順です。

対象:

- legacy broker-dryrun shadow-ops output
- canonical broker-dryrun shadow-ops output
- per-day shadow packet `orders_shadow.csv`
- per-day `broker_order_intents.csv`
- per-day `broker_payloads.json`
- per-day `broker_acks.json`

この step は paper/live trading ではありません。`PASS` は artifact reconciliation が成立したことを意味するだけで、live-ready を意味しません。

Calibration で確認する主な点:

- `null_broker_v1` / `DRY_RUN` 以外が混入していないこと
- shadow order row と broker intent が一対一で対応すること
- broker intent と NullBroker ack が一対一で対応すること
- reject が 0 件であること
- close-leg fields が metadata のみに残っていること
- deterministic fingerprint が安定していること
- credential-like raw values が artifacts に含まれていないこと

legacy / canonical の扱い:

- standalone CLI では legacy / canonical の両 source をまとめて calibration できます
- optional `shadow-ops` stage では、その run 自身を single-source calibration します

出力 artifacts:

- `calibration_summary.md`
- `calibration_summary.json`
- `calibration_by_source.csv`
- `calibration_by_day.csv`
- `calibration_issues.csv`
- `legacy/` と `canonical/` の source-specific summary

実行例:

```bash
python -m leadlag.cli broker-dryrun-calibration \
  --legacy-shadow-ops-dir artifacts/shadow_ops/<legacy_run_id> \
  --canonical-shadow-ops-dir artifacts/shadow_ops/<canonical_run_id> \
  --calibration-config configs/broker_dryrun/broker_dryrun_calibration_v1.yaml \
  --output-dir artifacts/broker_dryrun_calibration/step12
```

既知の制約:

- `NullBroker` は deterministic dry-run adapter であり、real execution quality は表現しません
- payload / ack reconciliation は NullBroker artifact shape 前提です
- live broker connectivity、credential handling、paper/live order submission はこの step に含みません
