# Internet Archive (archive.org) 調査レポート（contra への活用可否）

> 本ドキュメントは、Internet Archive (archive.org) が提供する API / コーパスを調査し、
> contra に取り込める要素があるかを判定した記録である。
> 調査手段: archive.org / scholar.archive.org / Wayback API ドキュメント＋ Web 調査。調査日: 2026-06-14。
> 対象: <https://archive.org/>（米国の非営利デジタル図書館）
> 関連: [`okf_knowledge_catalog_review.md`](okf_knowledge_catalog_review.md), [`byrepo_improvement_strategy.md`](../research/byrepo_improvement_strategy.md)

---

## 0. 結論（最重要）

1. **「論文の発見コーパス（検索の走らせ先）」としては弱〜中。OpenAlex を置き換える話ではない。**
   IA Scholar（scholar.archive.org）は OA 論文 2,500万件超の全文検索を持つが、**OA 部分集合で OpenAlex と
   カバレッジが重複**し、構造（abstract / citations / concepts）も OpenAlex ほど整っていない。
   一般 archive.org コーパス（書籍・テキスト・Web・ソフト）は OCR ノイズが多く非研究中心で、contra の
   構造類推パイプラインには噛み合わない。

2. **真価は「発見コーパス」ではなく、2つのインフラ層として効く。**
   - **Wayback Machine = Web Pass クローラーの堅牢化層**（README/docs のリンク切れを復旧）。
     前回レポートの推奨①「byrepo Web Pass」を直接強化する。**最有力（★★★）**。
   - **IA Scholar 全文 = OA 論文候補の肉付け層**（abstract だけでは薄い mechanism_dist 判定を全文で補強）。
     前回 byserendipity の課題に効くが OA 限定・ノイズあり（条件付き ★★）。
   - 補助: **Wayback Save Page Now で OKF バンドルの citation/resource URI を恒久ピン留め**（記憶層の耐久性 ★★）。

3. **すべて API キー不要・素の HTTP で叩ける → stdlib 原則と両立。** ただし **レート制限（CDX 15 req/min 等）**が
   あり、enrichment_agent と同じく **上限・フィルタによる暴走防止**を前提に組む必要がある。

---

## 1. Internet Archive が提供するもの（API / コーパス）

| サービス | 内容 | キー | 備考 |
|---|---|---|---|
| **Advanced Search API** | `archive.org/advancedsearch.php?q=...&output=json`。一般アイテム（書籍/テキスト/Web/ソフト/音声映像）を検索 | 不要（読み取り） | 構造は緩い。研究メタデータ用ではない |
| **Metadata API** | `archive.org/metadata/<identifier>`。任意アイテムの JSON メタデータ | 不要 | |
| **Wayback Availability API** | `archive.org/wayback/available?url=...`。指定 URL のアーカイブ有無を即判定 | 不要 | エラーハンドラ向けの軽量 API |
| **Wayback CDX API** | `web.archive.org/cdx/search/cdx`。スナップショットを日付/ステータス/MIME/URL マッチで詳細クエリ | 不要 | **15 req/min（429）**、`limit=` 既定挙動、上限 ~150,000 |
| **Save Page Now** | URL を即時アーカイブしスナップショット URL を発行 | 一部キー/制限あり | citation の恒久化に使える |
| **IA Scholar (scholar.archive.org)** | **OA 研究論文 2,500万件超の全文検索**。fatcat カタログ上に構築 | — | 全文クエリ可。検索 JSON API は未成熟 |
| **fatcat (fatcat.wiki)** | 学術成果の오ープンカタログ。**read/write REST API・CLI・バルクメタデータダンプ**・ファイル単位の保存メタデータ | 読み取り不要 | Rust バックエンド＋Python クライアント |

要点:
- archive.org は「**Web/書籍/メディアの巨大アーカイブ**」＋「**学術全文の保存（IA Scholar / fatcat）**」＋
  「**Web のタイムマシン（Wayback）**」の3層から成る。
- contra に関係するのは主に後者2つ（IA Scholar / Wayback）。

---

## 2. contra への活用評価（前回 2 レポートの枠組みに接続）

前回までの整理: ソースには「**クエリできる母集団（corpus）**」「**手法（technique）**」「**記憶層（memory）**」
の3用途がある。archive.org を各用途で評価する。

### 2-1. 発見コーパス（検索の走らせ先）としての評価

| ソース | contra での役割 | 評価 |
|---|---|---|
| OpenAlex | 2.5億論文の構造化メタデータ＋abstract。byserendipity / bybridge の母集団 | 既存・中核 |
| **IA Scholar / fatcat** | OA 論文 2,500万件の**全文**。OpenAlex と重複・OA 限定・構造が緩い | **置き換え不可（★☆）** |
| **archive.org 一般コーパス** | 書籍/テキスト/Web。OCR ノイズ・非研究中心 | **不適（歴史/人文テーマで稀に補助）** |

→ **「byrepo/byserendipity の隣にもう1つ検索先を足して新規ヒットを増やす」用途としては弱い。**
（前回 OKF レポートの結論と同じ理由: 新規の構造化ヒットを安定供給する母集団にはならない。）

### 2-2. 手法 / インフラ層としての評価 ← 本命

**(A) Wayback Machine = Web Pass クローラーの堅牢化層 … ★★★**
- 前回推奨①「byrepo の Web Pass（README 内リンクを N 件辿って文脈追記）」の最大の弱点は
  **リンク切れ（link rot）**。現実の README リンクは docs サイト移転・404 が頻発する。
- **Availability API** で対象 URL のアーカイブ有無を即判定し、生きていなければ **CDX API** で
  最新スナップショットへフォールバック → **死んだリンクからも文脈を回収できる**。
- キー不要・素の HTTP（stdlib 可）。レート 15 req/min は「辿るリンク数 N に上限」を課す設計と整合。
- **byserendipity/bybridge には弱い**（収集が OpenAlex API / 引用グラフで Web リンクを辿らないため）。

**(B) IA Scholar 全文 = OA 論文候補の肉付け層 … ★★（条件付き）**
- 前回レポートで byserendipity は「**abstract だけでは mechanism_dist 判定が薄い**」と評価した。
  IA Scholar は OA 論文の**全文**にアクセスできるため、候補論文の Purpose/Mechanism をより正確に判定する
  材料になりうる。
- 制約: **OA 論文限定**（paywall 論文は不可）、全文はノイズが多い、検索 JSON API が未成熟で fatcat 経由の
  取得になる。→ 「OpenAlex で見つけた候補のうち OA で abstract が薄いものだけ、fatcat で全文を引いて補強」
  という**条件付き enrichment** が現実的。bybridge にも同様に効く（判定補強のみ、発見は増やさない）。

**(C) Wayback Save Page Now = OKF 記憶層の耐久性 … ★★**
- 前回アイデア B「出力を OKF バンドル化して自前メモリ＝検索先にする」で、バンドルの `resource:` URI や
  Citations はいずれリンク切れする。**Save Page Now で採用時に URL をピン留め**すれば、過去 run の
  citation が将来も解決可能になる（OKF の「resource = 正規 URI」「Citations」と相性が良い）。

### フロー別まとめ

| フロー | Wayback(A) | IA Scholar 全文(B) | Save Page Now(C) |
|---|---|---|---|
| byrepo | ★★★（リンク復旧） | — | ★（repo 外リンクのピン留め） |
| byserendipity | — | ★★（OA 候補の全文補強） | ★★（citation 恒久化） |
| bybridge | — | ★★（判定補強のみ） | ★★ |
| bynote | — | — | — |

---

## 3. 制約整合（contra の禁則との両立）

- **stdlib のみ / 外部依存禁止**: 全 API がキー不要・素の HTTP（`urllib.request`）で叩ける。新規 pip 依存なし。
- **レート制限**: CDX 15 req/min、Save Page Now にも制限。enrichment_agent と同じく
  **上限・キャッシュ・ドメインフィルタ**を最初から組み込む（暴走防止）。
- **`models.py` / スコア設計は不変更**: 本件は収集の堅牢化層・enrichment 層・出力の耐久化層であり、
  Track B 判定ロジックの核には触れない。
- **安定 URL の倫理**: Save Page Now は外部サービスへ URL を送る＝公開アーカイブ化する行為。
  個人情報や非公開 URL をピン留めしない運用ルールを設ける。

---

## 4. 推奨アクション（優先順）

1. **Wayback フォールバックを Web Pass に組み込む** — byrepo の README リンク追跡（前回推奨①）に
   「404 なら Availability/CDX で最新スナップショットへフォールバック」を足す。**最小・高効果**。
2. **OA 候補の全文補強（条件付き）** — byserendipity/bybridge で「OA かつ abstract が短い候補」に限り
   fatcat 経由で全文を引き、mechanism 判定の材料にする実験。効果が薄ければ撤退しやすい範囲で。
3. **OKF バンドルの citation を Save Page Now でピン留め** — 記憶層（前回アイデア B）の耐久性オプション。

---

## 5. 結論の一言

archive.org は **「contra に新しい論文ヒットをくれる検索先」ではなく、「既存の収集・出力を壊れにくくする
インフラ」** として価値がある。とりわけ **Wayback は前回推奨①（byrepo Web Pass）の弱点（リンク切れ）を
ちょうど埋める**ので、OKF 調査の流れと自然に接続する。

---

## 付記: 一次情報

- Wayback Machine APIs: <https://archive.org/help/wayback_api.php>
- CDX レート制限（15 req/min）: smartial.net "How to Control Result Limits in Wayback Machine CDX Queries"
- IA Scholar（全文検索 2,500万件超）: <https://scholar.archive.org/>
- fatcat（オープンカタログ・REST API・バルクダンプ）: <https://fatcat.wiki/>
