# DOAJ (doaj.org) 調査レポート（contra への活用可否）

> 一般論文サイト総覧 #6。OpenAlex 基準（[`openalex_review.md`](openalex_review.md)）と比較して評価。
> 調査手段: doaj.org / Wikipedia ＋ Web 調査。調査日: 2026-06-15。
> 対象: <https://doaj.org/> / API: <https://doaj.org/api>

---

## 0. 結論（最重要）

1. **源としては冗長（OpenAlex に包含）。** DOAJ は **22,886 OA ジャーナル / 12.7M 論文**の
   コミュニティ査読済みホワイトリスト（無料 API・CC0）。だが **OpenAlex は DOAJ を統合**しており、
   論文/ソースに **`is_in_doaj` フラグ**として既に露出。→ DOAJ を別途叩く必要はない。

2. **唯一の使える信号＝「査読済み OA 誌か（≒ 非ハゲタカ）」。これは caution 用、discovery フィルタにしない。**
   DOAJ は質基準で predatory 誌を排除（再審査で 5,000 誌を除外した実績）。この **legitimacy フラグ**は
   contra の出力「注意点」フィールドに「査読体制が確認された OA 誌ではない」旨を添える材料になる。
   **ただし発見の足切りには使わない**——遠ドメインの良質だが無名な論文を殺し、セレンディピティを損なうため。

---

## 1. DOAJ とは

- **正体**: OA ジャーナルのコミュニティ査読済みディレクトリ（IS4OA 運営）。**ホワイトリスト**＝predatory 誌を排除。
- **規模**: 22,886 誌 / 12.7M 論文。
- **基準**: OA 方針・サイト情報・ISSN・**品質管理プロセス**・ライセンス・著作権を満たす誌のみ収録。
- **API**: 無料（誌/論文メタデータ、ISSN、分野、APC、homepage）。メタデータは再利用可。
- **OpenAlex 統合**: OpenAlex は DOAJ データを取り込み、`is_in_doaj` 等で参照可能。

---

## 2. contra への活用評価（OpenAlex 基準との差分）

| 観点 | DOAJ | OpenAlex（基準） | 含意 |
|---|---|---|---|
| 論文母集団 | 12.7M（OA 誌） | 250M+（DOAJ 含む） | **OpenAlex が内包** |
| legitimacy 信号 | ホワイトリスト | **`is_in_doaj` で露出** | **OpenAlex 経由で取得可** |
| 距離/全文 | なし | concepts/topics, oa_url | DOAJ は寄与なし |

### 2-2. 使える着想（DOAJ 不要、OpenAlex で実現）
- **「注意点」への venue legitimacy フラグ**: `is_in_doaj=false`（かつ非 arXiv 等）の論文には、
  「査読体制が確認された OA 誌ではない」旨を caution に添える。**メタデータ由来で安価・確実**。
- **discovery の足切りには使わない**（serendipity 阻害）。あくまで提示時の留保情報。

---

## 3. 「注意点（caution）信号クラスタ」への位置づけ
本総覧で **出力4部構成の「注意点」を、メタデータ由来の安価な信号で厚くする**スレッドが見えてきた:
- **arXiv**: preprint（未査読）フラグ
- **DOAJ（=OpenAlex `is_in_doaj`）**: 非査読 OA 誌フラグ
- **scite**（優先度低・有料）: 反論引用フラグ
→ いずれも `generate.py` の「注意点」に**留保を1行添える**用途。arXiv/DOAJ は OpenAlex/メタデータで無料に賄える。

---

## 4. 結論の一言

DOAJ は **OpenAlex に包含され源としては不採用**。価値は **`is_in_doaj` を「注意点」フィールドの
venue-legitimacy 信号として軽く使う**ことだけで、これも DOAJ ではなく **OpenAlex から取得**する。
**発見の足切りには絶対に使わない**（無名な遠ドメイン良論文を殺す）。

---

## 付記: 一次情報

- DOAJ 概要（22,886 誌 / 12.7M 論文 / ホワイトリスト）: <https://en.wikipedia.org/wiki/Directory_of_Open_Access_Journals>
- DOAJ API: <https://doaj.org/api>
- OpenAlex の DOAJ 統合（`is_in_doaj`）: <https://docs.openalex.org/api-entities/sources/source-object>
