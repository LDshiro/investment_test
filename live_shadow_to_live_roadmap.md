# Live運用と保守までのステップ設計

## 前提
- 現在地: 再現コード、historical shadow、batch replay、weekly review、weekly gates まで実装済み
- ゴール: 少額 live 運用を安全に開始し、週次・月次の保守と改善サイクルを回せる状態
- 原則: 研究レーンと運用レーンを分離し、`shadow -> tiny live -> calibration -> expansion` の順で進む

## Step 1: ベースライン凍結
目的: 今の再現系を運用基準線として固定する。
主タスク:
- repo の main baseline をタグ付け
- 使用データ、設定、出力物の一覧化
- “現時点の正” の config と README を固定
作業場所: このチャット + ローカル Codex
完了条件: 同じ config で同じ結果を再現できる。

## Step 2: 実行環境の再現性確保
目的: ローカル環境で誰が実行しても同じように動く状態を作る。
主タスク:
- Python バージョン固定
- 依存ライブラリ lock
- `.env.example` と secrets 方針整備
- 実行手順を1本化
作業場所: ローカル Codex 主体、レビューはこのチャット
完了条件: 新しい環境でセットアップから run まで手順通り通る。

## Step 3: データ契約の固定
目的: corrected bundle と今後の更新データの仕様を固定する。
主タスク:
- 必須ファイル一覧と列定義の明文化
- patch table 仕様の固定
- データ検証 CLI の追加/整備
- データ versioning ルール決定
作業場所: このチャット主体
完了条件: データ不備を自動で検出できる。

## Step 4: Canonical simulator の強化
目的: backtest / shadow / live 評価の真実ソースを1つにする。
主タスク:
- cost model の明文化
- slippage 仮定の設定化
- position / fills / pnl の計算経路統一
- golden-day audit の追加
作業場所: このチャット主体、長めの実行はローカル Codex
完了条件: 既知日の hand-check と simulator 出力が一致する。

## Step 5: Historical shadow の拡張検証
目的: 1日 replay ではなく、まとまった期間で daily packet 品質を確かめる。
主タスク:
- 20営業日 replay
- 60営業日 replay
- packet 欠落/異常の確認
- gate 発火理由の棚卸し
作業場所: ローカル Codex 主体、分析はこのチャット
完了条件: 連続 replay が安定し、packet が毎日出る。

## Step 6: Weekly gate / promotion ルールの調整
目的: GO / WARN / STOP と昇格判定を、現実の運用に耐える形へ調整する。
主タスク:
- 過去20〜60営業日で gate の発火妥当性を確認
- stop 条件の見直し
- small live 候補基準の現実化
- false positive / false negative の整理
作業場所: このチャット主体
完了条件: 週次判定が“厳しすぎず甘すぎない”水準に落ち着く。

## Step 7: 運用 Runbook の作成
目的: 人間が何を見るか、いつ止めるかを固定する。
主タスク:
- daily checklist
- weekly checklist
- incident 対応表
- manual override / kill switch 手順
作業場所: このチャット主体
完了条件: 異常時対応が文章で定義される。

## Step 8: Shadow ops profile の一本化
目的: `run-batch -> weekly-review -> weekly-gates` を定型運用にする。
主タスク:
- ops profile の追加
- 週次出力ディレクトリ構造固定
- summary artifact の標準化
- 1コマンド実行化
作業場所: このチャット主体
完了条件: shadow 週次運用がワンコマンドで回る。

## Step 9: ブローカー選定と adapter 設計
目的: live 候補ブローカーに依存しない注文 interface を作る。
主タスク:
- ブローカー候補比較
- 必要機能一覧化
- order / cancel / status / position interface 定義
- PaperBroker / LiveBroker の抽象化
作業場所: 設計はこのチャット、接続はローカル Codex
完了条件: broker adapter の I/F が固まる。

## Step 10: Secrets / 安全設計 / ホスト構築
目的: 実運用に必要な最低限の安全装置を入れる。
主タスク:
- API key / token の保管方針
- 専用実行機の構成
- ログ保存場所と rotation
- 停止スイッチの実装
作業場所: ローカル Codex 主体
完了条件: 秘密情報が repo に混ざらず、運用機が固定される。

## Step 11: Broker dry-run 統合
目的: 実発注なしで注文経路だけ本番に近づける。
主タスク:
- dry-run adapter 実装
- 注文 payload 検証
- 約定レスポンス模擬
- エラー系ハンドリング
作業場所: ローカル Codex 主体、レビューはこのチャット
完了条件: paper/dry-run で end-to-end が通る。

## Step 12: Shadow と broker dry-run の差分校正
目的: 自前 simulator と broker 側の見え方の違いを把握する。
主タスク:
- same-day 比較表作成
- order intent と broker payload の差分整理
- expected cost と observed friction の比較
- alert 文言の改善
作業場所: このチャット主体
完了条件: 差分の理由が説明可能になる。

## Step 13: Small-live 仕様の固定
目的: いくら、何本、どういう条件で live に入るかを固定する。
主タスク:
- max capital
- 1銘柄上限
- long-only / short 可否
- no-trade 条件
- live 中止条件
作業場所: このチャット主体
完了条件: 初回 live の制約条件が明文化される。

## Step 14: Tiny live 開始
目的: 小額で本物の execution friction を測る。
主タスク:
- shadow 並走
- live packet 追加
- expected vs actual fill 差分記録
- 実約定コストの蓄積
作業場所: ローカル Codex 主体、日次レビューはこのチャット
完了条件: 10〜20営業日 live を重大事故なく継続する。

## Step 15: Live / Shadow 校正
目的: どこで理論値と実運用がズレるかを特定する。
主タスク:
- slippage 再推定
- cost model 更新
- gate しきい値調整
- live review レポート作成
作業場所: このチャット主体
完了条件: live と shadow の差が縮まり、説明可能になる。

## Step 16: 昇格判定
目的: tiny live を続けるか、少し広げるか、shadow に戻すかを判定する。
主タスク:
- 20〜40営業日の live 実績評価
- weekly gate と promotion 基準の live 版策定
- 継続 / 拡大 / 停止の意思決定
作業場所: このチャット主体
完了条件: 次の資金段階への判断ができる。

## Step 17: 保守レーンの確立
目的: 週次・月次で“壊れない運用”を続ける体制を作る。
主タスク:
- weekly review
- monthly maintenance
- dependency update 日程
- broker/API 変更監視
- 障害 postmortem
作業場所: ローカル Codex + このチャット
完了条件: 保守タスクが定例化する。

## Step 18: 研究レーンの分離
目的: アルゴリズム改良を運用から切り離して安全に進める。
主タスク:
- research branch / config 分離
- A/B 比較ルール
- promotion to production 条件定義
- rollback 手順整備
作業場所: このチャット主体
完了条件: 改良が運用事故につながらない。

## Step 19: 半自動監督体制の完成
目的: 人間の仕事を“確認と停止判断”に限定する。
主タスク:
- 朝の digest
- 引け後 digest
- 週次 digest
- incident escalation 経路
- AI 伴走テンプレートの固定
作業場所: このチャット主体
完了条件: 日常運用の認知負荷が低く保たれる。

## Step 20: 安定運用フェーズ
目的: live と保守を回しながら、改善余地だけを選んで掘る。
主タスク:
- 定常運用
- live/shadow 比較継続
- 改良テーマ優先順位付け
- 年次監査/棚卸し
作業場所: ローカル Codex + このチャット
完了条件: “回る運用” と “改善する研究” が両立する。

## このチャットで主に進める領域
- 設計
- config
- README / runbook / checklist
- gate ルール
- packet 仕様
- 分析とレビュー
- 改良実験の設計

## ローカル Codex で主に進める領域
- 環境構築
- 長時間 replay
- scheduler
- broker 接続
- secrets 管理
- 実運用機のセットアップ
- live 実行

## 直近の優先順
1. Step 1〜3 を締める
2. Step 4〜8 で shadow 運用を“回るもの”にする
3. Step 9〜12 で broker dry-run を接続
4. Step 13〜16 で tiny live
5. Step 17〜20 で保守と研究レーン分離
