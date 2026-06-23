# OpenCitations (opencitations.net) 調査レポート（contra への活用可否）

> 一般論文サイト総覧 #5。OpenAlex `referenced_works`（[`openalex_review.md`](openalex_review.md)）＋
> S2 引用インテント（[`semantic_scholar_review.md`](semantic_scholar_review.md)）と比較して評価。
> 調査手段: opencitations.net / API ＋ Web 調査。調査日: 2026-06-15。
> 対象: <https://opencitations.net/> / API: <https://api.opencitations.net/index/v2>

---

## 0. 結論（最重要）

**冗長（追加不要）。引用グラフは OpenAlex、引用の"質"は S2 で既に賄えるから。**
OpenCitations は **CC0 のオープン引用データ（~2B、DOI-to-DOI）**を REST/SPARQL/ダンプで提供する優れた基盤だが、
contra が引用に求める2機能——**(1) 共有参照による bridge 検出 / (2) bridge の質（構造的引用か）**——は、
それぞれ **OpenAlex `referenced_works`** と **S2 引用インテント（methods/results）**で既に満たしている。
OpenCitations はこれらに**新しい信号を加えない**。

---

## 1. OpenCitations とは

- **正体**: オープン引用インフラ（非営利）。**COCI / OpenCitations Index / Meta**。~2B 引用、**CC0**。
- **アクセス**: REST API（RAMOSE）、SPARQL エンドポイント、検索 UI、CSV/N-Triples ダンプ。**無料・キー不要**。
- **付帯**: 自己引用フラグ、citation timespan。CiTO オントロジーで**引用の特徴づけが可能**だが、
  **COCI が intent を大規模に付与しているわけではない**（intent の実データは S2/scite が担う）。

---

## 2. contra への活用評価（OpenAlex / S2 基準との差分）

| contra の引用ニーズ | 既存の充足 | OpenCitations の寄与 |
|---|---|---|
| 共有参照→bridge 検出（bybridge） | **OpenAlex `referenced_works`** | 重複（同じ DOI-to-DOI） |
| bridge の質＝構造的引用か | **S2 引用インテント（無料）** | **なし**（COCI は intent 未付与） |
| 引用の態度（支持/反論） | scite（別レポート、優先度低） | なし |

- **母集団/カバレッジ**: OpenAlex と broadly comparable（重複）。OpenAlex は参照無し文献も含む分だけ広い。
- **唯一の小ネタ**: **自己引用フラグ**。bybridge の bridge から自己引用（著者が自著を引く trivial bridge）を除けば
  質が上がりうる。ただしこれは **OpenAlex の著者情報から自前で算出可能**で、OpenCitations を引く必要はない。

### 手法 / 記憶層
- 学ぶべき独自要素なし（オープン引用基盤）。CC0 の徹底は思想的に良いが、contra に欠けている信号は供給しない。

---

## 3. 派生メモ（OpenCitations 不要だが拾える着想）
- **自己引用の除外を bybridge に検討**: bridge プール構築時、シードと著者重複する参照を弱める/外す。
  実装は OpenAlex の `authorships` 突き合わせで可能（要仕様確認＝bybridge 選出ロジック変更）。OpenCitations は不要。

---

## 4. 結論の一言

OpenCitations は **CC0 の立派なオープン引用基盤だが、contra には冗長**。引用グラフは OpenAlex、引用の質は S2 で
完結しており、OpenCitations は新しい信号を足さない。唯一の収穫は「自己引用除外」という着想で、それも
**OpenAlex 内で自前算出**できる。→ **不採用**。

---

## 付記: 一次情報

- OpenCitations Index REST API（CC0・無料）: <https://api.opencitations.net/index/v2>
- データ/ライセンス（CC0・ダンプ・SPARQL）: <https://opencitations.net/querying/>
