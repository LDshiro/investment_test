# Operating model

## 日次ジョブ

1. `us_post_close`
   - 米国当日 close-to-close 情報を確定
   - corrected bundle / 当日データの QC
   - signal 下書き作成

2. `jp_pre_open`
   - tradable universe 確定
   - hard gate 判定
   - order intent 出力
   - shadow fill 仮定の準備

3. `jp_post_close`
   - open-to-close 実現収益を計算
   - packet / daily summary を確定
   - WARN / STOP を incident に昇格

## GO / WARN / STOP

- GO: hard gate 全通過
- WARN: 実行は可能だが注意喚起あり
- STOP: 1つでも critical gate が発火
