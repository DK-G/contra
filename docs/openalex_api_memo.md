# OpenAlex収集・最小API設計メモ（Phase 1）

本メモはPhase 1のCLI実装に必要な最小設計のみを整理する。

## 1. 目的
- テーマ入力から論文候補を安定取得し、500本を分類可能な状態にする。

## 2. 取得の基本方針
- 単一ソース（OpenAlex）に限定
- abstractありを優先（品質優先）
- 取得数の安定化を優先し、過不足時は補充ルールで調整

## 3. 必須フィールド（最小）
- `id`（OpenAlex Work ID）
- `title`
- `publication_year`
- `primary_location.source.display_name`（journal / conference 名）
- `cited_by_count`
- `doi` / `ids`
- `abstract_inverted_index`（abstract復元用）

## 4. 取得フロー（最小）
1. **関連度高**
   - テーマ/キーワードで検索し、関連度順に取得
2. **広域探索（ランダム）**
   - 分野/時代条件を緩め、ランダム取得
3. **無関係枠**
   - 意図的に分野/キーワードをずらして取得

## 5. 抽出と補充ルール
- 500本に満たない場合:
  - abstractなしも一部許容
  - フィルタ条件を段階的に緩める
- 500本を超えた場合:
  - 関連度/被引用数/抽象有無で優先順を決める

## 6. 抽象復元（abstract_inverted_index）
- `abstract_inverted_index`を復元し、全文のabstract文字列を作成
- 復元が失敗した場合はabstract欠損扱い

## 7. CLI実装の最小戻り値
- `Work`の内部表現（例）:
```json
{
  "id": "string",
  "title": "string",
  "year": 2022,
  "venue": "string",
  "doi": "string | null",
  "cited_by_count": 0,
  "abstract": "string | null"
}
```

## 8. リスクと保険
- レート制限: 取得失敗時のリトライ/バックオフ
- 欠損: abstractなしの割合が想定より高い可能性
- 粗い検索: 無関係枠が過剰に離れすぎる可能性

