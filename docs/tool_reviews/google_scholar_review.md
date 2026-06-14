# Google Scholar (scholar.google.com) 調査レポート（contra への活用可否）

> 本ドキュメントは、学術検索エンジン Google Scholar を contra の収集ソースとして評価した記録。
> 調査手段: 公式方針 / スクレイピング事情＋ Web 調査。調査日: 2026-06-14。
> 対象: <https://scholar.google.com/>
> 関連: OpenAlex（合法 API の現行ソース）, [`semantic_scholar_review.md`](semantic_scholar_review.md)

---

## 0. 結論（最重要）

**収集ソースとして採用不可（プログラムから合法・安定に使えない）。**
Google Scholar は **公式 API が存在せず、利用規約が自動アクセスを禁止**、超過すると **CAPTCHA / IP ブロック**。
カバレッジ（grey literature・プレプリント・被引用数）は広いが、**契約上も技術上も自動収集に使えない**。
同じ目的は **OpenAlex（現行・477M works・無料公式 API）** が完全に代替する。contra は現状維持でよい。

---

## 1. 要点

| 観点 | Google Scholar | OpenAlex（現行） |
|---|---|---|
| 公式 API | **なし** | あり（REST・無料・1日10万クレジット） |
| 自動アクセス | **ToS で禁止**、CAPTCHA / ブロック | 設計上許可（CAPTCHA なし） |
| 規模/カバレッジ | 広い（灰色文献・書籍・被引用） | 477M works |
| 安定性 | スクレイパは壊れやすい・グレー | 公式・安定 |

- 第三者スクレイパ（SerpApi / Apify 等）は存在するが **有料・規約グレー・不安定**。contra の
  「stdlib・コスト最小・合法・安定」方針に反する。

---

## 2. contra への活用評価

### 2-1. 発見コーパス
- **❌ 不採用**。合法・安定な自動アクセス経路がない。広いカバレッジは魅力だが取得手段がない。

### 2-2. 手法 / 記憶層
- 学ぶべき要素なし（検索 UI 製品）。

### 2-3. 補足（カバレッジの差をどう埋めるか）
- Google Scholar の強み＝**灰色文献・プレプリント・幅広い被引用**。これを合法 API で近づけたい場合の現実解:
  - プレプリント: OpenAlex は arXiv 等を収録済み。
  - 被引用ネットワーク: OpenAlex `cited_by` / Semantic Scholar 引用グラフ。
  - 灰色文献: **CORE (core.ac.uk)**（リスト #11、リポジトリ収集が強い）で一部補完可能。
- → Google Scholar を諦めても、OpenAlex ＋ S2 ＋ CORE の合法 API 群でカバレッジは概ね代替できる。

---

## 3. 結論の一言

Google Scholar は **「広いが触れない」**。公式 API 不在・ToS 禁止・CAPTCHA により contra の収集ソースには
**採用不可**。OpenAlex が合法・無料・安定の上位互換であり、カバレッジの隙間は CORE / S2 で補う方針でよい。

---

## 付記: 一次情報

- 公式 API 不在・自動アクセス禁止・CAPTCHA: ScrapingBee / Scrape.do 各解説
- OpenAlex API（無料・477M works・CAPTCHA なし）: <https://docs.openalex.org/>
