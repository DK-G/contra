# CLI実行手順（Phase 1）

```
python -m src.cli.main --input data/samples/theme.json --out output
```

- `data/samples/theme.json`: `docs/specs/input_schema.md`に準拠した入力
- `output/normalized_input.json`: 正規化済み入力
- `output/brainstorm_output.md`: Markdown出力
- 生成仕様は`docs/output_markdown_spec.md`を参照

## OpenAlexテスト

```
python -m src.cli.main --openalex-test --query "domain shift" --per-page 3 --mailto you@example.com
```

- `--query`: 検索キーワード
- `--per-page`: 取得件数
- `--mailto`: OpenAlex推奨の連絡先（任意）

## OpenAlex収集テスト

```
python -m src.cli.main --collect-test --input data/samples/theme.json --per-page 5 --max-pages 1 --mailto you@example.com
```

- `--collect-test`: テーマ入力をもとにOpenAlexから収集
- `--per-page`: 1ページあたり取得件数
- `--max-pages`: 最大ページ数
- `--mailto`: OpenAlex推奨の連絡先（任意）

## OA全文補強（provider層・opt-in）

abstract が薄い OA 候補の mechanism 判定を、全文取得で補強する（スコア式・閾値は不変。`--fulltext` 無指定なら従来と同一挙動）。

```
python -m src.cli.main --input data/samples/theme.json --out output --single --fulltext
```

- `--fulltext`: OA全文補強を有効化（既定 off）。「OA かつ abstract が短い」Track B 候補だけ取得する
- `--fulltext-max-abstract`: この文字数未満の abstract を持つ OA 候補のみ取得（既定 280・無駄打ち防止）
- `--fulltext-cache-dir`: 全文キャッシュ先（既定 `data/fulltext`・git追跡外）。hit/miss とも記録し再実行で再取得しない
- provider 解決順: arXiv（キー不要）→ Europe PMC（キー不要）→ IA Scholar（キー不要）→ CORE（`CORE_API_KEY` 設定時のみ）→ oa_url PDF（汎用フォールバック）
- いずれの provider も解決不可なら abstract のみで続行（壊れない）

実ネットワークでの疎通確認（要 outbound）:

```
python scripts/arxiv_fulltext_probe.py --ids 1706.03762
python scripts/arxiv_fulltext_probe.py --doi 10.1371/journal.pone.0000217   # フルチェーン
```
