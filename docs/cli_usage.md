# CLI実行手順（Phase 1）

```
python -m src.cli.main --input data/samples/theme.json --out output
```

- `data/samples/theme.json`: `docs/input_schema.md`に準拠した入力
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
