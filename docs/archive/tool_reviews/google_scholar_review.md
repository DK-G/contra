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

## 2-4. 「他の Google ツールから活用できないか？」（追補・2026-06-14）

提案を受けて検証。**結論: Scholar 固有のデータは、どの Google 公式ツールからも取得できない（設計上の封鎖）。**
ただし Google の汎用ツールで"隣接能力"は正規に得られる（返るのは Scholar ではなく Google の一般 Web/書籍）。

### (a) Scholar データ自体 → どの Google API にも出ていない
- **公式に確認**: Google Scholar の API は存在せず、**他の Google プロダクトも Scholar のデータを公開していない**。
- 理由: Scholar は大学リポジトリ＋出版社など**提供元ごとにライセンス条件が異なる**集約物で、Google は
  整合性保護とスクレイピング防止のため**意図的に API を出していない**。
  → Scholar 固有の資産（**Scholar 被引用グラフ / h-index / Scholar ランキング**）は**取得不可**。元の判定は変わらない。

### (b) Google の汎用ツール（正規）→ ただし Scholar ではなく一般インデックス
| ツール | 何が得られるか | 無料枠 / 価格 | contra での位置づけ |
|---|---|---|---|
| **Custom Search JSON API**（Programmable Search Engine） | Google の**一般 Web 検索**（サイト限定設定可） | 100 query/日 無料 → $5/1000（上限 1万/日） | **Web Pass の合法エンジン**になりうる。ただし有料従量＝コスト最小方針と緊張 |
| **Gemini API: Google検索グラウンディング** | コードから Google 検索で根拠づけ | 5,000 prompt/月 無料（Gemini 3.x）→ $14/1000 query | 同上。Gemini 依存＋従量課金 |
| **Google Books API** | 4,000万冊超の**書籍メタデータ**（全文不可） | 無料 | 教科書メタデータの軽い補完（Anna's Archive の合法代替の一部） |

### (c) contra への含意
- **元の目的（Scholar をコーパスにする）= 依然 No**。どの Google ツールも Scholar の学術グラフを返さない。
- **別の目的（Web Pass の検索エンジン）= 可能だが非推奨寄り**。Custom Search / Gemini grounding は
  **少量無料枠あり**で低volのWeb Pass実験には使えるが、超過は従量課金＝contra の「stdlib・コスト最小・キー最小」
  方針と衝突。既存 LLM クライアント＋標準 HTTP の限定 fetch（Phind レポートの自前再現案）で代替する方が方針整合。
- **Google Books API** は無料で、教科書メタデータの補完に**唯一そのまま使える**（ただし全文は出ない）。

→ まとめ: 「Google サービスだから別の Google ツールで」は **Scholar データに関しては不可**。
得られるのは Google の一般 Web 検索（有料従量）と書籍メタデータ（無料）で、いずれも Scholar の代替ではない。

---

## 3. 結論の一言

Google Scholar は **「広いが触れない」**。公式 API 不在・ToS 禁止・CAPTCHA により contra の収集ソースには
**採用不可**。OpenAlex が合法・無料・安定の上位互換であり、カバレッジの隙間は CORE / S2 で補う方針でよい。

---

## 付記: 一次情報

- 公式 API 不在・自動アクセス禁止・CAPTCHA: ScrapingBee / Scrape.do 各解説
- OpenAlex API（無料・477M works・CAPTCHA なし）: <https://docs.openalex.org/>
