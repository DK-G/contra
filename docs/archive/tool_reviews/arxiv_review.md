# arXiv (arxiv.org) 調査レポート（contra への活用可否）

> 本ドキュメントは、プレプリントサーバ arXiv を調査し、contra への活用可否を判定した記録。
> 「OA 全文 provider 層」スレッド（CORE / IA Scholar / Unpaywall）の文脈で、CORE/OpenAlex との差分に絞る。
> 調査手段: info.arxiv.org（API/bulk/ToU）＋ Web 調査。調査日: 2026-06-14。
> 対象: <https://arxiv.org/> / API: <https://info.arxiv.org/help/api/>
> 関連: [`core_review.md`](core_review.md), [`internet_archive_review.md`](internet_archive_review.md)

---

## 0. 結論（最重要）

> 改訂（2026-06-14）: 初版は「発見コーパスとしては不適」としたが、**機構の可読性（mechanism legibility）**という
> 観点を見落としていた。下記のとおり**byserendipity の副次的検索対象として有用**に判定を改める。

1. **byserendipity の副次的検索対象として有用 ⭕（OpenAlex を補完）。**
   arXiv は STEM 限定だが、**物理・数学・CS は機構（式・モデル・アルゴリズム）を明示的に書く文化**＝
   contra が照合したい **Purpose/Mechanism の構造骨格がテキスト上で可読**。これは**精度（precision）の利点**で、
   hollow/anomaly な偽 bridge を弾きやすく、「1論文あたり転用可能な機構が入っている確率」が高い。
   → **OpenAlex = 広さ(recall)／arXiv = 深さ・精度(precision)** の2軸として併用するのが正しい。
   ただし**主役は OpenAlex**（全分野で遠ドメイン射程を最大化）、arXiv は**STEM 構造類推を厚くする副次源**。

2. **唯一の技術的制約（欠陥ではない）: arXiv API は引用エッジを返さない。**
   メタデータ（題/要旨/著者/カテゴリ/リンク）のみ。→ **byserendipity は arXiv 単独で回る**が、
   **bybridge（citation 2-hop）は引用グラフを OpenAlex/S2 から取り、判定材料に arXiv 全文を使う**分担になる。
   なお arXiv 独自カテゴリ＋cross-list は `concept_distance` 用の**クリーンなドメイン距離信号**として利点。

3. **「OA 全文 provider 層」の第一候補 ⭕（特に STEM）。**
   API は **キー不要**、PDF＋**LaTeX ソース**を S3 で bulk 提供。**ソースは OCR ノイズが無く最もクリーン**。
   → arXiv-id を持つ論文の全文補強では、**CORE/S2（要キー・OCR ノイズ）より先に試すべき最良 provider**。

4. **プレプリント性は「注意点」フィールドに効く。** 未査読 → 提示時に「preprint, 未査読」を caution に添える材料。
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

### 2-1. 発見コーパス（改訂: 副次的検索対象として採用候補 ⭕）

**(0) 機構の可読性という質的利点（初版の見落とし）**
- contra の serendipity = purpose_sim × mechanism_dist。判定の質は「**機構がどれだけ明示的に書かれているか**」に依存する。
  arXiv の STEM 論文は式・モデル・アルゴリズムで**機構を明示**するため、**構造一致の判定が容易＝偽 bridge を弾きやすい**。
  → カバレッジ（recall）ではなく**精度（precision）の利点**。`serendipity_conditions.md` の「接続点の本物さ」を上げる方向。
- STEM 内でも距離は十分大きい（例: 統計力学 ↔ ネットワーク理論 ↔ 疫学モデル ↔ ML ↔ 数理ファイナンス）。
  **遠さ × 機構可読性**が両立する領域があり、byserendipity の良質な構造類推源になりうる。

**(1) 位置づけ: OpenAlex の補完（置換ではない）**
- **主役は OpenAlex**（全分野＝遠ドメイン射程の最大化、概念階層 L0/L1）。arXiv は**STEM の構造類推を厚くする副次源**。
- カバレッジの穴（医学/人文/社会）は OpenAlex 側が埋める。arXiv を**唯一の検索先にすると STEM 内に閉じる**ので、
  「OpenAlex（広さ）＋ arXiv（深さ・精度）」の併用が最適。

**(2) 技術的制約（欠陥ではなく分担）**
- arXiv API は**引用エッジを返さない**（メタデータのみ）。→ **byserendipity は arXiv 単独で実装可**だが、
  **bybridge は引用グラフを OpenAlex/S2 から取得**し、arXiv 全文は判定材料として使う。
- 検索意味論は OpenAlex の概念グラフより素朴（カテゴリ＋全文キーワード）。ただし**カテゴリ階層＋cross-list**は
  STEM 内の**クリーンなドメイン距離信号**として `concept_distance` に流用できる利点。

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
arXiv は **2つの役割を兼ねる**: ① byserendipity の**副次的検索対象**（STEM 構造類推の精度源）、
② OA 全文 **provider 層の筆頭**（キー不要・LaTeX ソースの清浄さ）。いずれも **OpenAlex を主役に据えた上での補完**で、
カバレッジの穴（医学/人文/社会）は OpenAlex（発見）と CORE/IA Scholar/Unpaywall（全文）が埋める二段構え。
**OpenAlex = 広さ(recall) / arXiv = 深さ・精度(precision)** の役割分担が要点。

---

## 3. フロー別まとめ

| フロー | 検索対象(2-1) | 全文 provider(A) | preprint 注意点(B) | cross-list bridge(C) |
|---|---|---|---|---|
| byserendipity | ★★（STEM 構造類推・arXiv 単独可） | ★★★（STEM 候補の全文） | ★★ | — |
| bybridge | △（引用は OpenAlex/S2 から、全文のみ arXiv） | ★★（判定補強） | ★★ | ★（STEM 内） |
| byrepo / bynote | — | — | — | — |

---

## 4. 推奨アクション

1. **byserendipity の副次的検索対象として arXiv を追加**: OpenAlex（広さ）と併走させ、STEM 構造類推の質を上げる。
   arXiv 検索 API（キー不要・1/3s）で横断クエリ → 構造スコアは既存 `select_track_b`（核は不変更）。
   カテゴリ/cross-list を `concept_distance` の距離信号に流用。**bybridge は引用を OpenAlex/S2 から取る分担を維持**。
2. **全文 provider 層に arXiv を最優先 provider として実装**: arXiv-id がある候補は arXiv ソース/PDF を最初に試し、
   無ければ Unpaywall → CORE → IA Scholar にフォールバック。キー不要なので導入摩擦が最小、**provider 層の着手点**。
3. **「注意点」に preprint フラグ**: arXiv 由来＝未査読を caution に明示（メタデータで自動判定）。
4. （STEM 範囲で）**watch モードの実験基盤**に OAI-PMH 日次差分を使う（優先度中）。

---

## 5. 結論の一言

arXiv は **OA 全文 provider 層の筆頭候補**であると同時に、**byserendipity の副次的検索対象としても採用候補**。
STEM 限定は「広さ」では弱点だが、**機構の可読性ゆえ構造一致の"精度"が高く**、OpenAlex（広さ）と
**recall × precision の2軸**で補完しあう。唯一の制約（引用エッジ非提供）は bybridge を OpenAlex/S2 と
分担すれば解消し、**構造的欠陥はない**。キー不要・クリーンな LaTeX ソースで導入摩擦も最小。

---

## 付記: 一次情報

- arXiv API（キー不要・レート 1/3s・Atom）: <https://info.arxiv.org/help/api/user-manual.html>
- Bulk data（PDF/ソースの S3 提供・OAI-PMH）: <https://info.arxiv.org/help/bulk_data.html>
- API 利用規約: <https://info.arxiv.org/help/api/tou.html>
