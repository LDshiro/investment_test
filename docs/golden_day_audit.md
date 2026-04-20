# Golden Day Audit

`golden day audit` は、current canonical simulator の packet を少数の代表的な trade date で凍結し、rerun して stable-field が一致するかを見る監査手順です。

## golden day とは何か

golden day は、current historical shadow path を比較しやすい代表日です。Step 04A では少なくとも 5 日を選びます。

選定の優先カテゴリは次です。

- latest valid date
- earlier GO day
- non-zero alerts day
- scaling/cap alert day
- holiday-edge day

カテゴリが足りないときは、latest 60 valid dates の中から evenly spaced に補完します。

## どう選ばれるか

1. corrected bundle と exact-match sample filter を解決します。
2. `strategy_output.returns.dropna().index` と sample filter dates の交差を valid trade dates とします。
3. latest 20 valid dates を candidate pool とします。
4. candidate pool から上のカテゴリを deterministic に拾います。
5. 足りない分は latest 60 valid dates から evenly spaced に補います。

current local shadow profile では `allow_short=false` と `max_single_name_abs=0.15` のため、GO day でも `scaled_for_single_name_cap` alert が構造的に出ることがあります。zero-alert GO day が無い場合でも audit は止まりません。

## 実行方法

```bash
python scripts/audit_simulator_golden_days.py \
  --config configs/profiles/shadow_corrected_local.yaml \
  --simulator-contract configs/simulator/canonical_simulator_v1.yaml \
  --output-dir artifacts/simulator_audit/canonical_v1 \
  --refresh
```

## 出力

主な出力は次です。

- `golden_days.csv`
- `audit_summary.csv`
- `audit_summary.json`
- `audit_summary.md`
- `fingerprints.json`
- `packets/<trade_date>/...`

`packets/<trade_date>/` には、selected trade date の current historical shadow packet copy が残ります。

## deterministic rerun check

Step 04A の rerun check は stable-field comparison です。

- `signals.csv`, `orders_shadow.csv`, `fills_shadow.csv`, `positions.csv`, `pnl.csv` は raw bytes hash
- `run.json`, `risk_report.json`, `alerts.json` は normalized JSON hash
- `run.json` では `code_version`, `run_id`, `started_at`, `finished_at`, `bundle_root` を除外

`code_version` を除外するのは、current `hash_tree()` が repo 配下の `.md` を tree-hash に含めるためです。audit packet copy 自体が rerun 時の tree-hash を変えうるので、Step 04A では stable-field comparison に寄せています。

`summary.md` と chart PNG は human review 用に残しますが、fingerprint には入れません。

## 人手で見るべき点

- `summary.md` の narrative と `alerts.json` が一致しているか
- `signals.csv` と `orders_shadow.csv` の selected names / target_weight が一致しているか
- `fills_shadow.csv` と `pnl.csv` で same-day open/close assumption が一貫しているか
- `risk_report.json` の triggered gate が想定どおりか
- primary と rerun の stable fingerprints が一致しているか
