# Anna's Archive (annas-archive.org) 調査レポート（contra への活用可否）

> 本ドキュメントは、シャドウライブラリ検索エンジン Anna's Archive を調査し、contra への活用可否を判定した記録。
> 調査手段: Wikipedia / 報道 / 訴訟資料＋ Web 調査。調査日: 2026-06-14。
> 対象: <https://annas-archive.org/>
> 関連: [`internet_archive_review.md`](internet_archive_review.md), `core.ac.uk`（合法な OA 代替）

---

## 0. 結論（最重要）

**contra に統合してはならない。** Anna's Archive は **Z-Library / Sci-Hub / Library Genesis を束ねる
著作権侵害のシャドウライブラリ**であり、2026-04-15 に **$322M の判決＋恒久差止命令**を受け、ドメイン登録業者等への
サービス停止が命じられている。技術的には「論文・教科書の**全文**」という contra が欲しい素材を持つが、
**法的・倫理的に採用不可**。同じ「全文アクセス」目的は **合法な OA 経路（CORE / Unpaywall / IA Scholar /
OpenAlex の OA リンク）**で満たすべき。本対象は **不採用（reject）** が確定的な結論。

---

## 1. Anna's Archive とは

- **正体**: 影の図書館（shadow library）の**メタ検索エンジン**。Z-Library / Sci-Hub / LibGen 等の
  メタデータを横断索引し、第三者ホストの DL へリンクする。
- **content**: 書籍・雑誌・**論文（Sci-Hub 由来）**・教科書・コミック・メタデータ。
- **法的状況**:
  - 「ファイルを直接ホストしないので非該当」と主張するが、**大規模著作権侵害**として各国でブロック・提訴。
  - **2026-04-15: $322M の欠席判決＋恒久差止**。レジストラ等にサービス停止命令。ドメインも失っている。

---

## 2. contra への活用評価

### 2-1. 発見コーパス / 全文ソース
- 技術的には **論文・教科書の全文**を提供 → byserendipity の「abstract が薄く mechanism 判定が難しい」課題や、
  byrepo の周辺資料に効く"素材"ではある。
- **しかし採用不可**。理由:
  - **違法**: 著作権侵害コンテンツ。判決・差止対象。
  - **持続性ゼロ**: ドメイン差押え・ブロックで API/URL が不安定。インフラとして信頼できない。
  - **プロジェクト方針との衝突**: contra は公開・共有を志向するツール。海賊版依存は配布・利用者に法的リスクを波及させる。
  - `spec.md` のセキュリティ/倫理方針（鍵・PII を漏らさない等）の精神にも反する。

### 2-2. 手法 / 記憶層
- 学ぶべき手法・記憶層の要素は**なし**（単なる海賊版メタ検索）。

---

## 3. 合法な代替（同じ「全文/教科書」目的を満たす）

| 目的 | 違法（不採用） | 合法な代替 |
|---|---|---|
| 論文の全文 | Anna's Archive（Sci-Hub 経由） | **CORE (core.ac.uk)** / **Unpaywall** / **IA Scholar** / OpenAlex の `oa_url` |
| 教科書・書籍 | Anna's Archive（LibGen/Z-Lib） | **Internet Archive**（貸出）/ DOAB（OA 書籍）/ OpenStax |

→ contra が全文補強をしたいなら、**OpenAlex の OA リンク＋ Unpaywall ＋ CORE** を辿るのが正道
（[`internet_archive_review.md`](internet_archive_review.md) の IA Scholar も同列）。本リスト #11 の **core.ac.uk**
がまさに合法版の本命なので、そちらで詳細評価する。

---

## 4. 結論の一言

Anna's Archive は **「欲しい素材（全文）を持つが、法的に触れてはいけない」典型例**。
contra の収集ソースには**採用しない**。全文アクセスは合法 OA 経路（CORE / Unpaywall / IA Scholar / OpenAlex OA）で
代替する、という方針を確認するための記録に留める。

---

## 付記: 一次情報

- 概要・法的経緯: <https://en.wikipedia.org/wiki/Anna's_Archive>
- $322M 判決・恒久差止（2026-04）: TorrentFreak / 出版社訴訟資料
