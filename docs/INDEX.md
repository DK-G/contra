# ドキュメント索引（contra）

> contra の文書地図。文書は「使う瞬間」に開く。新規文書は安易に増やさない。
> 高度順: 不変核(WHY) → 仕様 → 運用 → 実行 → 参照 → アーカイブ。

## IDENTITY / SPEC（不変核・仕様）

| 文書 | 役割 |
|---|---|
| [DIRECTION.md](../DIRECTION.md) | 不変核：売り P1–P3・非目標・真の目的vs代理指標・採否リトマス。スコア核に触れる前に読む |
| [spec.md](../spec.md) | AI向け開発仕様（技術スタック・決定ログ・禁則） |
| [plan.md](../plan.md) | マスター仕様（目的・設計原則・パイプライン・出力仕様）。書き換えは提案のみ |
| [README.md](../README.md) | 利用者向け概要・使い方 |
| [CHECKS.md](../CHECKS.md) | 受け入れゲート（自動 / 独立検証 / 人間判断） |

## PROCESS / AGENT（運用ルール）

| 文書 | 役割 |
|---|---|
| [agent.md](../agent.md) | プロジェクト管理エージェント運用ルール |
| [Gemini.md](../Gemini.md) | レビュー/思考素材エージェントの役割（**編集禁止**） |
| [agent_rules/](agent_rules/) | by* named flow 正本（byserendipity / byrepo / bybridge）＋ gemini_output_guide |
| [AGENT_COORDINATION.md](../AGENT_COORDINATION.md) | 複数エージェントの交代・協調プロトコル |

## LIVE（更新され続ける作業文書）

| 文書 | 役割 |
|---|---|
| [task.md](../task.md) | 作業タスクリスト |
| [diff.md](../diff.md) | 直近の変更報告（毎タスク上書き） |
| [roadmap.md](../roadmap.md) | フェーズ別ロードマップ |
| [DECISION_LOG.md](../DECISION_LOG.md) | 重要な設計判断ログ（追記） |
| [Changelog.md](../Changelog.md) | diff スナップショットのアーカイブ（追記） |
| [memo.md](../memo.md) | 調査モードの共有メモ |
| [review.md](../review.md) | レビュー結果記録（**編集禁止**） |

## REFERENCE（参照資料）

| 文書 | 役割 |
|---|---|
| [research/](research/) | 理論的基盤・設計研究（serendipity_conditions ほか） |
| [specs/](specs/) | 入力スキーマ・出力仕様・OpenAlex メモ・Track A 設計 |
| [cli_usage.md](cli_usage.md) | CLI 実行手順 |
| [quality_eval.md](quality_eval.md) | Phase 1 Done 判定ルーブリック（DoD） |
| [bybridge_concept.md](bybridge_concept.md) | bybridge（第3方式）コンセプト（実装未着手） |
| [TOOL_CONFIG_GUIDE.md](../TOOL_CONFIG_GUIDE.md) | 精鋭6ツールのセットアップ |

## ARCHIVE（退避・歴史）

- [archive/](archive/) — `Template/`（ひな形複製）・`tool_reviews/`（使い捨て評価集）・旧仕様（`input_min_spec` / `cli_directory_layout`）・一発点検（`structure_inspection_2026-06-01`）・初版 `first.md` 等。
