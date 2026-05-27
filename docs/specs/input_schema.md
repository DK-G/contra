# 入力仕様スキーマ（草案）

本スキーマはPhase 1のCLI入力を想定する。

## 1. 入力（ユーザー提供）

```json
{
  "theme_overview": "3〜6文でテーマ概要",
  "goal": "何を明らかにしたいか",
  "why_problem": "なぜ問題か",
  "approach_type": "theory | experiment | application",
  "assumptions": [
    "前提/仮説1",
    "前提/仮説2"
  ],
  "scope": {
    "field": "分野（選択+自由記述）",
    "scale": "small | large | theoretical",
    "time_range": "last_10_years | no_limit"
  },
  "keywords": {
    "include": ["任意"],
    "exclude": ["任意"]
  },
  "concern": "今いちばん不安な点（任意）"
}
```

## 2. 内部表現（正規化後）

```json
{
  "theme_overview": "string",
  "goal": "string",
  "why_problem": "string",
  "approach_type": "theory | experiment | application",
  "assumptions": ["string"],
  "scope": {
    "field": "string",
    "scale": "small | large | theoretical",
    "time_range": "last_10_years | no_limit"
  },
  "keywords": {
    "include": ["string"],
    "exclude": ["string"]
  },
  "concern": "string | null"
}
```

## 3. バリデーション（最小）

- `theme_overview`: 3〜6文（CLIでは最小長=200文字、最大=1200文字目安）
- `assumptions`: 2〜5件
- `approach_type`: 必須
- `scope.field`: 必須
- `scope.scale`: 必須
- `scope.time_range`: 必須

## 4. 既定値

- `keywords.include`: 空配列
- `keywords.exclude`: 空配列
- `concern`: null
