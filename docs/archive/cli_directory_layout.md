# Phase 1 CLIディレクトリ構成案

目的: 収集→分類→生成→出力の最小パイプラインを小さく分離し、後でWeb化に移行しやすい形にする。

## 1. ルート構成（案）

```
./
  scripts/
    run_cli.ps1
  src/
    cli/
      main.py
    core/
      models.py
      input_schema.py
      output_spec.py
    openalex/
      client.py
      parser.py
    pipeline/
      collect.py
      filter.py
      classify.py
      generate.py
      export.py
  data/
    samples/
  output/
  docs/
    input_schema.md
    openalex_api_memo.md
    output_markdown_spec.md
```

## 2. 役割の整理

- `src/cli/main.py`
  - CLI引数の受付、入力読み込み、パイプライン起動
- `src/core/models.py`
  - Work/Theme/Outputの内部表現
- `src/core/input_schema.py`
  - 入力のバリデーション/正規化
- `src/core/output_spec.py`
  - 出力構成・テンプレート規定
- `src/openalex/client.py`
  - API呼び出し、レート制御
- `src/openalex/parser.py`
  - abstract復元、フィールド正規化
- `src/pipeline/collect.py`
  - 収集フロー（関連/広域/無関係の入口）
- `src/pipeline/filter.py`
  - abstract優先/除外条件
- `src/pipeline/classify.py`
  - 章分類/比率制御
- `src/pipeline/generate.py`
  - 3行構成の生成
- `src/pipeline/export.py`
  - Markdown生成・ファイル出力

## 3. CLI実行イメージ

```
python -m src.cli.main --input theme.json --out output/
```

## 4. メモ
- `docs/`は既存の仕様メモを配置する想定。
- Phase 2以降は`src/cli`をAPI層に差し替え可能。
