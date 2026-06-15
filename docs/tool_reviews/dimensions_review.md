# Dimensions (dimensions.ai) 調査レポート（contra への活用可否）

> 一般論文サイト総覧 #11。OpenAlex 基準＋ Lens/特許（[`lens_patents_review.md`](lens_patents_review.md)）と比較。
> 調査手段: dimensions.ai / docs.dimensions.ai ＋ Web 調査。調査日: 2026-06-15。
> 対象: <https://www.dimensions.ai/>（Digital Science）

---

## 0. 結論（最重要）

**不採用。出版物は OpenAlex と冗長、固有の特許は #10 の無料 API で対応済み、有用 API は有料/申請制。**
Dimensions は出版物・助成金・臨床試験・**特許**・政策文書を**横断リンク**した最大級の研究 DB（~350M オブジェクト）。
だが contra から見ると:
- **出版物**は OpenAlex と重複、
- 固有価値の **特許**は [`lens_patents_review.md`](lens_patents_review.md) のとおり**無料特許 API（PatentsView 等）で採るべき**で Dimensions 不要、
- 助成金/政策/臨床試験は contra の構造類推に**非整合**、
- 有用な **Analytics API は機関課金/申請制**（無料は Metrics API のみ）。
→ 新しい母集団も距離信号も**実用上**加えない。

---

## 1. Dimensions とは

- **正体**: Digital Science の連結研究 DB。出版物・助成金・臨床試験・特許・政策・データセットをリンク。~70% 全文索引。
- **アクセス**:
  - **無料 Web**: 出版物・データセットの検索のみ。
  - **Metrics API**: 無料（citation 指標：RCR/FCR 等）。
  - **Analytics API**: **機関サブスク**（適格な scientometric 研究は申請で無料）。
- **対 OpenAlex**: 特許・助成金の統合が差別化点。出版カバレッジは Lens/Google Scholar に近い。

---

## 2. contra への活用評価

| 観点 | Dimensions | 既存の充足 | 含意 |
|---|---|---|---|
| 出版物 | ~140M+ | OpenAlex（250M+） | 冗長 |
| **特許** | 統合あり | **無料特許 API（#10）** | Dimensions 不要 |
| 助成金/政策/臨床試験 | 統合あり | — | 構造類推に非整合（資金/governance 記録） |
| 有用 API | Analytics（有料/申請） | OpenAlex（無料） | コスト最小方針に反す |

- **手法/記憶層**: 学ぶ独自要素なし。横断リンク自体は魅力だが、contra に効くのは特許のみで、それは無料経路で足りる。

---

## 3. 結論の一言

Dimensions は **横断リンクが立派な商用 DB だが、contra には冗長**。出版物は OpenAlex、唯一効く特許は
**無料特許 API（#10）**で採るのが筋で、Dimensions の有料 API を挟む理由がない。**不採用**。

---

## 付記: 一次情報

- Dimensions（連結 DB・無料版/API 階層）: <https://www.dimensions.ai/products/all-products/>
- API（Metrics 無料 / Analytics サブスク・申請）: <https://docs.dimensions.ai/dsl/api.html>
