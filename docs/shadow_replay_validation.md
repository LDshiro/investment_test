# shadow_replay_validation

Step 05 の historical shadow continuous validation は、batch replay が連続運転できたかを packet 監査ベースで確認するための layer です。

## 何を確認するか

- legacy shadow path で 60 営業日 replay が完走したか
- Step 04B の canonical sidecar path でも 60 営業日 replay が完走したか
- 各日 packet に required files がそろっているか
- `run.json` の actual run status が許容範囲か
- canonical replay では reconciliation diff が許容範囲に収まっているか

この validator は batch replay 後の artifact を読むだけで、signal / risk gate / weekly rules の挙動自体は変えません。

## Legacy と Canonical の違い

legacy validation は既存 daily packet を監査します。

- `summary.md`
- `run.json`
- `signals.csv`
- `orders_shadow.csv`
- `fills_shadow.csv`
- `positions.csv`
- `pnl.csv`
- `risk_report.json`
- `alerts.json`

canonical validation はこれに加えて Step 04B の sidecar を監査します。

- `canonical_pnl.csv`
- `canonical_simulation_result.json`
- `sim_reconciliation.json`

また canonical では、少なくとも次の diff threshold を確認します。

- `max_abs_net_return_diff_bps`
- `max_abs_gross_return_diff_bps`
- `max_abs_cost_return_diff_bps`

## Batch row の解釈

`batch_summary.csv` では `result` と packet の actual `run_status` を別に扱います。

- `result=completed` はその日の batch 実行が完了したことを意味します
- `result=skipped_existing` は packet を再利用したことを意味します
- `result=failed` は batch 実行自体の failure です

`allow_statuses` は packet 側の actual run status に対して適用します。`SKIPPED` は batch row の状態であり、packet run status ではありません。

## 出力ファイル

validator は次を出します。

- `replay_validation_report.md`
- `replay_validation_report.json`
- `daily_packet_audit.csv`
- `status_counts.csv`
- `alert_summary.csv`
- `risk_gate_summary.csv`

canonical validation ではさらに次を出します。

- `canonical_reconciliation_summary.csv`

## PASS / WARN / FAIL

### FAIL

- `batch_summary.csv` missing
- required packet file missing
- completed / skipped_existing row の packet directory missing
- `failed_days` が config 上限を超える
- duplicate trade dates
- non-monotonic trade dates
- packet run status が allow list 外
- canonical reconciliation status が required 条件を満たさない
- canonical diff が threshold を超える

### WARN

- packet run status が `WARN`
- packet run status が `STOP`
- critical alert が存在する
- triggered gate が存在する

warning-level alert は summary に残しますが、Step 05 ではそれだけで hard fail にしません。

### PASS

構造的な欠損や invalid status がなく、packet run status もすべて許容範囲で、canonical threshold も満たしている状態です。

## 実行方法

legacy replay validation:

```bash
python -m leadlag.cli validate-shadow-replay \
  --batch-dir runs/<legacy_batch_dir> \
  --validation-config configs/validation/shadow_replay_v1.yaml \
  --output-dir artifacts/shadow_replay_validation/step05_legacy_60d/replay_validation
```

canonical replay validation:

```bash
python -m leadlag.cli validate-shadow-replay \
  --batch-dir runs/<canonical_batch_dir> \
  --validation-config configs/validation/shadow_replay_canonical_v1.yaml \
  --output-dir artifacts/shadow_replay_validation/step05_canonical_60d/replay_validation
```

standalone script でも同じ実装を呼べます。

```bash
python scripts/validate_shadow_replay.py \
  --batch-dir runs/<batch_dir> \
  --validation-config configs/validation/shadow_replay_v1.yaml \
  --output-dir artifacts/shadow_replay_validation/debug_run
```

## weekly-review / weekly-gates との関係

Step 05 validator は weekly-review や weekly-gates の代替ではありません。

- weekly-review は週次要約と performance / alert density の確認
- weekly-gates は GO/WARN/STOP と promotion rule の判定
- shadow replay validation は「60 日分の daily packet 群が継続運転として妥当か」の検査

3 つを合わせて見ることで、日次 packet の健全性と週次運用判定の両方を確認できます。

## Step 05 でまだ証明しないもの

- live broker execution quality
- actual order acknowledgement / reject handling
- live borrow availability
- live-vs-shadow slippage decomposition
- production scheduler / ops alerting

Step 05 は historical shadow continuous validation であって、live readiness の最終証明ではありません。
