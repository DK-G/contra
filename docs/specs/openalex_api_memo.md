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

## 3.1 必須フィールドの優先度（取得順）
1. **識別子と表示**: `id`, `title`
2. **年と掲載先**: `publication_year`, `primary_location.source.display_name`
3. **評価指標**: `cited_by_count`
4. **外部参照**: `doi`, `ids`
5. **内容把握**: `abstract_inverted_index`

※ 取得時は `select` を使用して上記のみ取得し、欠損時は空/nullで受け入れる。

## 4. 取得フロー（最小）
1. **関連度高**
   - テーマ/キーワードで検索し、関連度順に取得
2. **広域探索（ランダム）**
   - 分野/時代条件を緩め、ランダム取得
3. **無関係枠**
   - 意図的に分野/キーワードをずらして取得

## 4.1 取得順の明文化（最小方針）
1. **検索取得（関連度高）**
   - `search` + `filter`で主要キーワードを固定
2. **補充取得（広域）**
   - `search`条件を緩めて分野広げ
3. **無関係取得**
   - 異分野キーワードで取得

## 4.2 検索クエリ設計（入力→検索語の生成ルール）
### 入力要素（Theme）
- `title`: 最重要キーワード（必ず検索語に含める）
- `include_keywords`: 補助キーワード（優先度中）
- `exclude_keywords`: 除外条件（除外検索）
- `field`: 分野指定（可能ならfilterに反映）
- `goal`: 背景目的（検索語には使わない、後工程のみ）

### 生成ルール（最小）
1. **ベースクエリ**
   - `title`をそのまま `search` に入れる。
2. **追加クエリ**
   - `include_keywords`を順番に連結して `search` を拡張。
3. **除外**
   - `exclude_keywords`は `filter` の `NOT` 条件で除外。
4. **分野**
   - `field`は可能なら `filter` に反映（例: `concepts.display_name`）。

### 出力形式（最小例）
- `search`: `"title + include_keywords"`
- `filter`: `concepts.display_name:"field", NOT keywords`

## 4.3 検索クエリの拡張（重み付け方針）
### 重み付けの優先度
1. **高**: `title`
2. **中**: `include_keywords`
3. **低**: `goal`（検索語には使わない。後工程で再評価）
4. **除外**: `exclude_keywords`

### 反映ルール（最小）
1. **titleを最優先**: `search`の先頭に置く。
2. **include_keywordsは数を絞る**: 上位3件までを`search`に加える。
3. **goalは検索に使わない**: 出力整形や分類で参照。
4. **exclude_keywordsは必ずfilter除外**: `NOT` で除外。

### 例（擬似）
- `search`: `"title + include1 + include2 + include3"`
- `filter`: `concepts.display_name:"field", NOT (exclude1 OR exclude2)`

## 4.4 ページング/レート制御（最小方針）
### ページング
- `per-page`: 50を基準（必要に応じて調整）
- `page`: 1から順に増加
- `max-pages`: 10を上限の初期値

### レート制御
- 1リクエストごとに短い待機（0.5〜1.0秒）
- 失敗時はバックオフ（4.2節で定義）
- 連続失敗時は中断

## 4.5 リトライ/バックオフ（最小方針）
### リトライ条件
- 一時的なネットワークエラー
- 5xx系のHTTPエラー
- 429（レート制限）

### バックオフ
- 1回目: 1秒
- 2回目: 2秒
- 3回目: 4秒
- 最大3回まで

### 中断条件
- 連続失敗が3回を超えたら中断

## 4.6 重複排除ポリシー（ID/DOI）
### 判定キー
- 最優先: `id`（OpenAlex Work ID）
- 次点: `doi`（正規化して比較）

### ルール（最小）
1. `id` が同一なら重複として除外。
2. `id` が不明な場合は `doi` で判定。
3. `id` も `doi` も無い場合は重複判定しない（残す）。

### DOI正規化（最小）
- 小文字化
- 先頭の `https://doi.org/` を除去

## 4.7 フィールド欠損ポリシー（最小）
### 必須扱い
- `id`, `title` は必須。欠損なら除外。

### 代替/許容
- `publication_year` 欠損: `null` 許容
- `primary_location.source.display_name` 欠損: `venue` を `null`
- `cited_by_count` 欠損: `0` 扱い
- `doi` 欠損: `null`
- `abstract_inverted_index` 欠損: `abstract` を `null`

## 4.8 abstract復元失敗時の扱い（最小）
### 失敗条件
- `abstract_inverted_index` が空/不正
- 復元後に空文字または極端に短い

### ルール
1. 復元失敗は `abstract = null` として扱う。
2. フィルタで abstract有りを優先するが、件数不足時は許容。
3. 復元失敗の件数はログで把握できるようにする。

## 4.9 結果の停止条件（最小）
### 停止条件
- 目標件数に到達（例: 500件）
- 連続して空ページが2回
- 低関連が連続した場合（検索結果の関連度が一定以下）

### 運用
- 停止条件は「十分数」優先、次に「空ページ」。
- 低関連の判定基準は後工程で調整。

## 4.10 取得数制御と補充ルール（最小）
### 目標件数
- 目標: 500件（MVP基準）

### 補充ルール
1. abstract有りを優先して最大件数まで取得。
2. 件数不足時は abstract無しも許容。
3. さらに不足時は検索条件を緩めて再収集。
4. それでも不足なら不足数で終了。

### 過剰時の制御
- 取得数が超過した場合は、関連度高→低の順で切り詰め。

## 5. 分類ルール（関連/広域/無関係）
### 判定軸
- include_keywords一致度
- title/abstract内の一致
- field一致（概念/分野）

### 比率（最小）
- 関連: 60%
- 広域: 30%
- 無関係: 10%

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

