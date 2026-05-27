# 入力仕様の最小セット（確定版）

Phase 1のCLI入力で必須とする最小セットを定義する。

## 1. 必須入力

- **テーマ概要**
  - 3〜6文
  - 200〜1200文字目安
- **目的（何を明らかにしたいか）**
  - 1〜2文
- **問題意識（なぜ問題か）**
  - 1〜2文
- **アプローチ種別**
  - `theory | experiment | application`
- **前提・仮説**
  - 2〜5件
  - 箇条書き
- **スコープ**
  - 分野（選択+自由記述）
  - スケール（`small | large | theoretical`）
  - 時代（`last_10_years | no_limit`）

## 2. 任意入力（精度ブースター）

- include キーワード（0〜5件）
- exclude キーワード（0〜5件）
- 「今いちばん不安な点」（1文）

## 3. 入力例（最小）

```json
{
  "theme_overview": "...",
  "goal": "...",
  "why_problem": "...",
  "approach_type": "experiment",
  "assumptions": ["...", "..."],
  "scope": {
    "field": "...",
    "scale": "small",
    "time_range": "last_10_years"
  }
}
```

## 4. ルール

- `assumptions`が2件未満の場合はエラー
- `theme_overview`が200文字未満の場合はエラー
- `scope`は3項目すべて必須
