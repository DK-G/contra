# arXiv (arxiv.org) 調査レポート（contra への活用可否）

> 本ドキュメントは、プレプリントサーバ arXiv を調査し、contra への活用可否を判定した記録。
> 「OA 全文 provider 層」スレッド（CORE / IA Scholar / Unpaywall）の文脈で、CORE/OpenAlex との差分に絞る。
> 調査手段: info.arxiv.org（API/bulk/ToU）＋ Web 調査。調査日: 2026-06-14。
> 対象: <https://arxiv.org/> / API: <https://info.arxiv.org/help/api/>
> 関連: [`core_review.md`](core_review.md), [`internet_archive_review.md`](internet_archive_review.md)

---

## 0. 結論（最重要）

1. **発見コーパスとしては不適（STEM 限定でドメイン多様性を狭める）。**
   arXiv は **Astrophysics/Physics/Math/CS/Quant-Bio/Quant-Finance/Statistics** に限定（Math 21% / Physics 20% …）。
   医学・人文・社会科学を欠く。**遠ドメインを最大化したい contra にとって、arXiv 単独は"遠さ"の射程を縮める**。
   発見の母集団は全分野を持つ **OpenAlex 据え置き**が正しい（OpenAlex は arXiv プレプリントも既に収録）。

2. **「OA 全文 provider 層」の第一候補 ⭕（特に STEM）。**
   API は **キー不要**、PDF＋**LaTeX ソース**を S3 で bulk 提供。**ソースは OCR ノイズが無く最もクリーン**。
   → arXiv-id を持つ論文の全文補強では、**CORE/S2（要キー・OCR ノイズ）より先に試すべき最良 provider**。

3. **プレプリント性は「注意点」フィールドに効く。** 未査読 → 提示時に「preprint, 未査読」を caution に添える材料。
   最新性（newest preprints）は Litmaps 由来の watch モード着想とも相性が良い。

---

## 1. arXiv とは

- **正体**: STEM 中心のプレプリントサーバ（~2.4M 件規模）。
- **アクセス**:
  - **arXiv API**: メタデータ＋検索。**キー不要**、Atom XML。**レート 1 req / 3 秒・単一接続**。
  - **OAI-PMH**: 全件メタデータの bulk harvesting（日次更新）。差分取得に最適。
  - **全文**: 処理済み **PDF＋ソース（LaTeX）が Amazon S3 で bulk 提供**。
- **カバレッジ**: 物理・数学・CS・Quant-Bio・Quant-Finance・Statistics・EE。**医学/人文/社会は対象外**。
- **性質**: 未査読プレプリント（査読版は OpenAlex/出版社側で解決）。
- **分類**: arXiv 独自カテゴリ＋**cross-list**（複数分野タグ）。

---

## 2. contra への活用評価

### 2-1. 発見コーパス
- **△〜❌ 主役にしない**。STEM 限定で、contra が狙う「分野は遠いが構造一致」の**遠ドメイン射程を縮める**。
  OpenAlex（全分野＋概念階層 L0/L1）が発見の中核であり続けるべき。arXiv を主検索先にすると STEM 内に閉じる。

### 2-2. 手法 / インフラ層 ← 採用候補（provider 層）

**(A) OA 全文 provider の第一候補（STEM） … ★★★**
- 「abstract が薄く mechanism 判定が弱い」課題（byserendipity/bybridge）への全文補強で、arXiv は:
  - **キー不要**（CORE/S2 は要キー）、**レート緩やか**（1/3s）、**LaTeX ソースでノイズ最小**。
  - → **provider 層の優先順を「arXiv（arXiv-id があれば最優先）→ Unpaywall → CORE → IA Scholar」**とするのが自然。
- 実装（禁則整合）: `core_review.md` と同じく**収集レイヤーの provider 追加**。差し替え可能な共通 IF で実装し、
  `select_track_b` の構造判定核には触れない。キャッシュは arXiv-id 単位。

**(B) 「注意点」への preprint フラグ … ★★**
- 提示論文が arXiv プレプリント（未査読）なら、4部構成の**「注意点」に未査読である旨**を添える。
  scite の「反論引用」より**取得が容易で確実**（メタデータで分かる）。caution 強化の現実的な一手。

**(C) cross-list を STEM 内 bridge 信号に … ★（限定）**
- cs.LG × q-bio.NC のように **cross-list された論文は分野横断の自然な bridge**。bybridge の STEM ケースで
  弱い補助信号になりうる。ただし STEM 内に限られ、contra の真の狙い（STEM 外への遠さ）には届かない。

**(D) 最新性 / watch … ★**
- OAI-PMH 日次更新は、Litmaps 由来の **watch/monitor モード**（新着 bridge の継続発見）と相性が良い（STEM 範囲で）。

### 2-3. ポジショニング
arXiv は CORE と同じ **「発見ではなく全文供給」**の層。違いは **キー不要・LaTeX ソースの清浄さ**で、
**STEM では provider 層の筆頭**。一方カバレッジが STEM 限定なので、**全分野は CORE/IA Scholar/Unpaywall が補完**する
二段構えが要る。

---

## 3. フロー別まとめ

| フロー | 全文 provider(A) | preprint 注意点(B) | cross-list bridge(C) |
|---|---|---|---|
| byserendipity | ★★★（STEM 候補の全文） | ★★ | — |
| bybridge | ★★（STEM 候補の判定補強） | ★★ | ★（STEM 内） |
| byrepo / bynote | — | — | — |

---

## 4. 推奨アクション

1. **全文 provider 層に arXiv を最優先 provider として実装**: arXiv-id がある候補は arXiv ソース/PDF を最初に試し、
   無ければ Unpaywall → CORE → IA Scholar にフォールバック。キー不要なので導入摩擦が最小、**provider 層の着手点**。
2. **「注意点」に preprint フラグ**: arXiv 由来＝未査読を caution に明示（メタデータで自動判定）。
3. （STEM 範囲で）**watch モードの実験基盤**に OAI-PMH 日次差分を使う（優先度中）。

---

## 5. 結論の一言

arXiv は **発見の母集団にはしない（STEM 限定で遠さを縮める）が、OA 全文 provider 層では筆頭候補**。
キー不要＋クリーンな LaTeX ソースという導入摩擦の低さで、**全文補強スレッドの最初の一手として最適**。
カバレッジの穴（医学/人文/社会）は CORE/IA Scholar/Unpaywall が埋める二段構えで運用する。

---

## 付記: 一次情報

- arXiv API（キー不要・レート 1/3s・Atom）: <https://info.arxiv.org/help/api/user-manual.html>
- Bulk data（PDF/ソースの S3 提供・OAI-PMH）: <https://info.arxiv.org/help/bulk_data.html>
- API 利用規約: <https://info.arxiv.org/help/api/tou.html>
