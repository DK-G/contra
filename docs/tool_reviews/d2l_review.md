# Dive into Deep Learning (d2l.ai) 調査レポート（contra への活用可否）

> 本ドキュメントは、無料の対話型深層学習教科書「Dive into Deep Learning」(D2L) を調査し、
> contra への活用可否を判定した記録。**これは検索/論文ソースではなく「開発者向け学習リファレンス」**であり、
> 評価軸が他レポートと異なる。
> 調査手段: d2l.ai / github.com/d2l-ai/d2l-en ＋ Web 調査。調査日: 2026-06-15。
> 対象: <https://d2l.ai/>（CC BY-SA 4.0 / コードは modified MIT）
> 関連: [`elicit_review.md`](elicit_review.md), [`semantic_scholar_review.md`](semantic_scholar_review.md)（SPECTER2）, `spec.md` §2.1

---

## 0. 結論（最重要）

1. **データソース/コーパス/ツールとしては対象外（統合しない）。**
   D2L は**1冊の教科書＋コード**であり、API もクエリ可能な母集団も無い。contra の収集パイプライン（OpenAlex 等）に
   組み込む種類のものではない。「発見コーパス/記憶層」の枠には当てはまらない。

2. **ただし "開発者リファレンス" としては高価値。** D2L は **word2vec/GloVe・Attention/Transformer・表現学習**を
   数式＋実行可能コードで教える。これは contra の **将来ロードマップ（`spec.md` §2.1「分散表現で概念アライメント距離」）**
   と **Semantic Scholar SPECTER2 活用**（[`semantic_scholar_review.md`](semantic_scholar_review.md)）を実装する際の
   **最良級の無料・厳密・runnable な学習資料**。

3. **重要な但し書き（依存）。** D2L の手法は **PyTorch/NumPy/Gensim** 等を前提＝contra の現行「stdlib のみ」方針と衝突。
   ただし `spec.md` §2.1 は **Gensim/NumPy を将来追加予定**として既に明記済み → D2L は**その将来フェーズの道標**。
   なお SPECTER2 を S2 API から**取得して使う軽量経路**なら、自前学習＝D2L は不要（モデルを作り込む場合のみ要参照）。

---

## 1. D2L とは

- **正体**: 対話型の深層学習教科書。数式・図・実行可能コード・議論を統合。**PyTorch / NumPy(MXNet) / JAX / TensorFlow**
  のマルチフレームワーク実装。
- **採用**: 70カ国・**500大学**（Stanford/MIT/Harvard/Cambridge 等）。Cambridge University Press から書籍版も。
- **ライセンス**: 本文 **CC BY-SA 4.0**、コード **modified MIT**（=改変・流用しやすい）。
- **カバレッジ**: DL 基礎・最適化・CNN・RNN・CV・**NLP（word2vec/GloVe・Attention/Transformer・事前学習）**・
  **推薦システム**・GAN。

---

## 2. contra への活用評価

### 2-1. 発見コーパス / 記憶層
- **— 対象外**。教科書＋コードリポジトリであり、収集ソースにはならない。
  （d2l-ai/d2l-en リポジトリが byrepo の ML テーマでアンカーとして拾われる可能性はあるが、特別扱いはしない。）

### 2-2. 開発者リファレンスとしての価値 ← 本質
contra の技術ロードマップの難所に、D2L の各章が直接対応する。

| contra の課題（出典） | D2L の該当章 | 効き方 |
|---|---|---|
| 概念アライメント距離＝**分散表現**（`spec.md` §2.1, "GloVe コンセプト"） | **word2vec / GloVe（NLP 事前学習）** | この機能を実装する**ど真ん中の教材** |
| **SPECTER2 埋め込み**の理解・活用（Elicit/S2 レポート） | **Attention / Transformer** | 埋め込みの仕組みを理解し正しく使うため |
| 候補拡張＝**推薦**（S2 Recommendations / ResearchRabbit） | **推薦システム** | 推薦ロジックの基礎 |

- コードが **modified MIT** で runnable なので、PoC の踏み台にしやすい。

### 2-3. 依存・方針との整合（最重要の留意）
- D2L 流の実装は **PyTorch/NumPy/Gensim** 前提 → **現行 contra（stdlib のみ）とは非両立**。
- ただし **`spec.md` §2.1 が Gensim/NumPy を将来追加予定**と明記済み。D2L は**「いつ・何を入れるか」を学ぶ道標**であって、
  今すぐ依存を増やす話ではない。
- **軽量経路の存在**: 概念アライメント距離は、自前学習せず **S2 の SPECTER2 ベクトルを取得して cos 距離（stdlib 手計算）**
  で済ませられる（[`semantic_scholar_review.md`](semantic_scholar_review.md) の推奨）。
  → **当面はこの軽量経路が第一候補**。D2L が要るのは「独自の表現学習/構造マッチングを作り込む」より深いフェーズ。

---

## 3. 推奨アクション

1. **「将来フェーズの学習資料」として記録に留める**（今すぐ統合しない）。`spec.md` §2.1 の概念アライメント距離に着手する
   段階で、word2vec/GloVe・Transformer 章を参照する。
2. **当面は軽量経路を優先**: 概念距離は SPECTER2 ベクトル取得＋stdlib cos で。自前モデルが必要になって初めて D2L。
3. （任意）ML 周辺の用語・設計の共通参照として、開発メモから D2L へリンクしておく。

---

## 4. 結論の一言

D2L は **contra の"中に入れる"ものではなく、開発者が"将来 ML 機能を作るとき開く"無料・厳密・runnable な教科書**。
`spec.md` §2.1 の概念アライメント距離や SPECTER2 活用の実装フェーズで真価を発揮する。
ただし当面は **SPECTER2 を API 取得して使う軽量経路**で足り、D2L が必須になるのは独自表現学習に踏み込むときだけ。

---

## 付記: 一次情報

- D2L 本体（CC BY-SA 4.0・マルチフレームワーク・500大学採用）: <https://d2l.ai/>
- コード（modified MIT）: <https://github.com/d2l-ai/d2l-en>
