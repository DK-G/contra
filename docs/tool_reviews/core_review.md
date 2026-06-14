# CORE (core.ac.uk) 調査レポート（contra への活用可否）

> 本ドキュメントは、世界最大の OA 集約サービス CORE を調査し、contra への活用可否を判定した記録。
> 本バッチ（リスト #1–11）で**初の「採用候補」**。Anna's Archive の合法代替であり、繰り返し出た
> 「abstract が薄く mechanism 判定が難しい」課題への正規の全文ソース。
> 調査手段: api.core.ac.uk/docs/v3 / CORE 論文・ドキュメント＋ Web 調査。調査日: 2026-06-14。
> 対象: <https://core.ac.uk/>
> 関連: [`internet_archive_review.md`](internet_archive_review.md)（IA Scholar）, [`annas_archive_review.md`](annas_archive_review.md)（合法代替）

---

## 0. 結論（最重要）

1. **採用候補 ⭕。ただし「発見コーパス」ではなく「合法・無料の全文レイヤー」として。**
   CORE は **10,000+ リポジトリ**を集約した世界最大の OA 全文集約（**300M+ メタデータ / 40M+ 全文**）。
   **無料 API v3（キー1分で取得）**あり。OpenAlex を置き換えるのではなく、**OA 論文の"全文"を供給する層**として効く。

2. **繰り返し出た課題への正規解。** byserendipity/bybridge の弱点
   「**abstract だけでは purpose_sim × mechanism_dist の構造判定が薄い**」を、**OA 論文の全文取得**で補強できる。
   Anna's Archive が違法に担っていた全文を、**合法・無料**で代替する本命。

3. **位置づけ: 合法全文スタックの中心。** OpenAlex（発見＋`oa_url`）→ **CORE / IA Scholar / Unpaywall**（全文）。
   CORE は API がよく整備され、全文と全文検索を持つため**この層の第一候補**。

---

## 1. CORE とは

- **正体**: 世界最大の OA 研究集約サービス。機関/分野リポジトリ・OA/ハイブリッド誌を横断集約。
- **規模**: 300M+ メタデータレコード、40M+ 全文論文、10,000+ データ提供元。
- **アクセス**:
  - **API v3**: 無料・要 API キー（登録1分）。フェアアクセスのためのレート quota（高速化は要相談）。
  - **データダンプ**: 全件ダンプあり（~395GB 圧縮 / 展開 2.1TB）。
  - 全文検索・recommender・Discovery（無料 PDF 発見）。

---

## 2. contra への活用評価

### 2-1. 発見コーパス
- **△ 置き換えではない**。発見は OpenAlex（概念階層 L0/L1 を持つ）が中核。CORE は**全文供給**で補完する役。

### 2-2. 手法 / インフラ層 ← 採用候補

**(A) OA 全文レイヤー＝ mechanism 判定の補強 … ★★★（採用候補）**
- byserendipity/bybridge の候補論文のうち **OA かつ abstract が薄いもの**について、CORE API で**全文を取得**し、
  Purpose/Mechanism の構造判定（`select_track_b`）の材料を厚くする。
- これは IA Scholar（[`internet_archive_review.md`](internet_archive_review.md)）/ S2 全文と同じ狙いだが、
  **CORE は API が整備され全文カバレッジが最大**で、**無料**。→ **全文補強の第一候補**。
- 実装方針（禁則整合）:
  - **収集レイヤーの追加**であり `models.py` / スコア設計の核には触れない（全文は判定の入力材料）。
  - `CORE_API_KEY` を環境変数化（既存 OPENAI/GITHUB と同じ運用）。HTTP+JSON で stdlib のみ。
  - **OA 限定・レート quota・全文ノイズ（抽出/OCR）**に留意 → 論文 ID 単位でキャッシュ、全文は要点抽出して使う。
  - `select_track_b` の閾値・構造判定を変える場合は `spec.md` 禁則に従い**要仕様確認**（材料追加自体は周辺実装）。

**(B) Discovery（無料 PDF 発見） … ★**
- OpenAlex の `oa_url` が無い/切れた論文に対し、CORE Discovery / Unpaywall で全文 PDF を補完。
  archive レポートの Wayback（リンク切れ復旧）と同系統の堅牢化。

### 2-3. ポジショニング
本バッチは大半が「収束型 SaaS」「違法/触れない/代筆」で**棄却**だったが、CORE は**合法・無料・API 整備の
インフラ**で、初めて**素直に採用を検討できる対象**。Semantic Scholar（前バッチ）と並ぶ"素材として加算価値"のある2例目。

---

## 3. フロー別まとめ

| フロー | 全文補強(A) | PDF 発見(B) |
|---|---|---|
| byserendipity | ★★★（mechanism 判定の材料） | ★ |
| bybridge | ★★（遠ドメイン候補の判定補強） | ★ |
| byrepo / bynote | — | — |

---

## 4. 推奨アクション

1. **CORE を「OA 全文補強」ソースとして PoC**: byserendipity で「OA かつ abstract が短い候補」に限り CORE API で
   全文を引き、構造判定の精度が上がるか検証。IA Scholar / S2 と**同一インターフェースの差し替え可能な provider**として実装。
2. **合法全文スタックの確立**: OpenAlex(`oa_url`) → Unpaywall / CORE / IA Scholar の優先順で全文を解決する薄い層を用意。
   Anna's Archive 等の違法経路は**恒久的に不採用**と明記。

---

## 5. 結論の一言

CORE は **本バッチ唯一の素直な採用候補**。発見は OpenAlex のまま、CORE は**合法・無料・最大カバレッジの OA 全文層**として、
contra が繰り返しぶつかってきた「abstract が薄い」課題を正面から埋める。Anna's Archive の合法代替の本命でもある。

---

## 付記: 一次情報

- CORE API v3 ドキュメント: <https://api.core.ac.uk/docs/v3>
- 規模・集約（300M+ メタ / 40M+ 全文 / 10,000+ 提供元）: <https://en.wikipedia.org/wiki/CORE_(research_service)>
- データダンプ: <https://core.ac.uk/documentation/dataset>
