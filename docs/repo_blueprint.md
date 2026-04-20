# Repo blueprint

## 1. 目的

この repo は、論文再現・継続シャドー運用・少額 live 候補を **同じ signal / order / gate** で動かすための基盤である。

## 2. ディレクトリ設計

```text
leadlag-stack/
├─ configs/
│  ├─ base.yaml
│  ├─ data/
│  ├─ strategy/
│  ├─ cost/
│  ├─ risk/
│  ├─ broker/
│  ├─ packets/
│  └─ profiles/
├─ docs/
├─ src/leadlag/
│  ├─ cli.py
│  ├─ config/
│  ├─ data/
│  ├─ strategy/
│  ├─ portfolio/
│  ├─ sim/
│  ├─ runtime/
│  ├─ broker/
│  └─ reporting/
└─ tests/
```

## 3. 重要原則

- **canonical simulator** が性能検証の正本
- broker paper/test は配線確認の副本
- daily packet を監査の最小単位とする
- live でも shadow を並走させる
- データ修正は patch table で明示管理する
- config は `base.yaml` + leaf component config の二層で持つ

## 4. データレイヤ

- `raw/`: 取得そのまま
- `normalized/`: 調整済み価格・patch反映後
- `features/`: returns, factors, calendars
- `runs/`: signals, orders, fills, pnl
- `reports/`: daily, weekly, incident

## 5. mode 切替

`run.mode` だけを変える。

- `backtest`: 過去全期間の canonical simulation
- `shadow`: 当日 run + 仮想 fill
- `live_dryrun`: broker adapter に注文内容を流すが送信しない
- `live`: 実送信

## 6. 研究と運用の分離

- `strategy/` 配下のロジックは pure function を優先
- `runtime/` は scheduler, packet, alert だけ
- `broker/` は side-effect を閉じ込める
