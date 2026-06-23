# BASE (base-search.net) 調査レポート（contra への活用可否）

> 一般論文サイト総覧 #7。OpenAlex 基準（[`openalex_review.md`](openalex_review.md)）＋ CORE（[`core_review.md`](core_review.md)）と
> 比較して評価。同じ「OA リポジトリ集約」系のため CORE との差分が論点。
> 調査手段: base-search.net / OAI ＋ Web 調査。調査日: 2026-06-15。
> 対象: <https://www.base-search.net/> / API: <https://api.base-search.net/>

---

## 0. 結論（最重要）

**不採用。CORE と同役だが、API が申請制・制約付きで CORE/OpenAlex に劣後し、固有の信号も無い。**
BASE は **12,000+ 提供元・400M+ 文書**を OAI-PMH で集約する巨大検索エンジン（~60% が OA 全文リンク）。
だが (1) 発見は **OpenAlex が同種リポジトリを内包**、(2) 全文 provider 役は **CORE が API 開放＋全文配信で上**、
(3) BASE API は **利用目的を申請してキー取得**（歴史的に非商用/IP 制約）で**導入摩擦が大きい**。
→ contra に新しい母集団も距離信号も加えず、采用理由がない。

---

## 1. BASE とは

- **正体**: Bielefeld 大学図書館の学術検索エンジン。OAI-PMH で**リポジトリ/誌のメタデータを集約**。
- **規模**: 12,000+ 提供元、**400M+ 文書**。**約60%が OA 全文（リンク）**。
- **アクセス**: ライブ検索 API ＋ OAI-PMH。**API はフォームで申請しキー取得**（用途記載）。
  メタデータは**リンク中心**で、CORE のように全文を配信・ホストするわけではない。
- **分類**: DDC（デューイ）など主題分類あり。

---

## 2. contra への活用評価（OpenAlex / CORE 基準との差分）

| 観点 | BASE | OpenAlex（基準） | CORE | 含意 |
|---|---|---|---|---|
| 母集団 | 400M+（リポジトリ集約） | 250M+（リポジトリ含む） | 400M+ | 重複（OpenAlex が発見を担う） |
| 全文 | ~60% に**リンク** | なし（oa_url） | **32M+ を全文配信** | provider 役は **CORE が上** |
| API 開放度 | **申請制・用途記載・制約** | 無料（polite pool） | 無料（要キー） | BASE は摩擦が大きい |
| 距離/引用 | なし（主題分類のみ） | concepts/topics, 引用 | なし | 固有の距離信号なし |

### 2-2. 手法 / 記憶層
- 学ぶべき独自要素なし。grey literature/リポジトリ網羅という強みも OpenAlex＋CORE で代替済み。

---

## 3. 結論の一言

BASE は **CORE の同類だが API が申請制・制約付きで実装摩擦が大きく、CORE/OpenAlex に劣後**。
発見は OpenAlex、全文は CORE/arXiv/Europe PMC が担うため、**BASE を加える理由はない（不採用）**。

---

## 付記: 一次情報

- BASE 概要（400M+ 文書・12,000+ 提供元・~60% OA）: <https://www.base-search.net/about/en/>
- BASE API（申請制）: <https://api.base-search.net/>
