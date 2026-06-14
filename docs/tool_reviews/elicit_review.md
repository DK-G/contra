# Elicit (elicit.com) 調査レポート（contra への活用可否）

> 本ドキュメントは、AI 研究アシスタント Elicit と、その基盤コーパスである Semantic Scholar を調査し、
> contra に取り込める要素があるかを判定した記録である。
> 調査手段: elicit.com / Semantic Scholar API ドキュメント＋ Web 調査。調査日: 2026-06-14。
> 対象: <https://elicit.com/>（商用 SaaS）/ 基盤: <https://api.semanticscholar.org/>
> 関連: [`okf_knowledge_catalog_review.md`](okf_knowledge_catalog_review.md), [`../research/serendipity_conditions.md`](../research/serendipity_conditions.md)

---

## 0. 結論（最重要）

1. **Elicit 自体は contra の「思想的な対極」。検索先にもならない。**
   Elicit は **関連性最大化＝収束（convergence）** のツール — セマンティック検索で「問いに直接答える論文」を
   見つけ、要約・構造抽出する。一方 contra は `spec.md` が明言するとおり **「要約ではなく関係性の再構成」**＝
   **発散（divergence／遠い構造類推）**。両者は正反対の極に位置する。
   加えて Elicit は商用 SaaS（API も商用）で、内部では **OpenAlex / Semantic Scholar / PubMed を集約**している
   ＝contra が既に持つ/直接叩ける母集団の再販。→ **Elicit を新しい検索先にする意味はない。**

2. **真に効くのは Elicit の1階層下、Semantic Scholar (S2AG)。**
   - **無料 REST API（キーあり）/ 2億件超**。OpenAlex と相補的な追加コーパス候補。
   - **SPECTER2 埋め込み（citation-informed の論文ベクトル）** を API で取得可能。`spec.md` 将来構想
     「分散表現で概念アライメント距離」を**学習なし・重依存なし**で前倒しできる。
   - **Recommendations API**（seed list → ML 推薦）= byserendipity/bybridge の候補拡張に使える。

3. **手法としては「構造抽出（define columns → 表に充填）」が参考になる。**
   contra の Purpose/Mechanism 抽出（`classify.py`）を、より検査可能・頑健にする設計の手本。

4. **重要な但し書き**: SPECTER2 埋め込みは**話題的・引用的な類似**を測る → contra の
   **ドメイン距離軸**（`concept_distance.py` の L0/L1 近傍棄却）には合うが、
   **purpose_sim × mechanism_dist の「構造一致」軸には使えない**（埋め込み近接 = マイオピアを呼ぶ）。
   差し込み場所を間違えると逆効果になる。

---

## 1. Elicit とは

- **正体**: 文献レビューを支援する AI 研究アシスタント（商用 SaaS）。
- **コーパス**: **1億3,800万件の論文＋54.5万件の臨床試験**。データ源は **Semantic Scholar / OpenAlex /
  PubMed / ClinicalTrials.gov** の集約。
- **主要機能**:
  - **Semantic Search**: 正しいキーワードを知らなくても関連論文に到達。
  - **Data Extraction**: ユーザーが列（sample size / methodology / key findings / side effects 等）を定義 →
    Elicit が**数十本の論文を横断して表を自動充填**。
  - **Research Briefs / Reports**: 系統的レビューに着想を得たプロセスで研究ブリーフを生成。対象論文・記載項目を
    深くカスタマイズ可能（最大80本）。
  - **API**: 138M 論文の検索と Report 生成を API で提供（商用）。
- **2025 更新**: データ抽出・レポート生成に **Claude Opus 4.5** を採用しハルシネーション低減。

---

## 2. contra への活用評価（3用途の枠組み）

### 2-1. 発見コーパス（検索の走らせ先）

| ソース | 評価 | 理由 |
|---|---|---|
| **Elicit（製品）** | ❌ 不要 | 商用 SaaS。内部は OpenAlex/S2/PubMed の集約＝contra が既に持つ母集団の再販 |
| **Semantic Scholar (S2AG)** | ⭕ 有力な追加候補 | 無料 API・2億件超・OpenAlex と相補。**SPECTER2 埋め込み**と **Recommendations API** が固有の価値 |

→ 「Elicit を検索先に」は No だが、**その下の Semantic Scholar は contra の母集団を補強する実体のある候補**。
これは過去2レポート（OKF / archive.org）では出てこなかった「**新しい検索先になりうる**」初の対象。

### 2-2. 手法 / インフラ層

**(A) Semantic Scholar SPECTER2 埋め込み = ドメイン距離軸の強化 … ★★（差し込み場所限定）**
- `spec.md` 将来構想「Gensim/NumPy（GloVe コンセプト）で概念アライメント距離」を、**学習不要・ベクトル API 取得**で実現できる。
- 適所は **`concept_distance.py`（L0/L1 Jaccard 近傍判定）の補強**＝「分野の遠さ」測定。埋め込み cos 距離で
  近傍/遠ドメインを連続値で評価できる。
- **不適所**: `select_track_b` の purpose_sim × mechanism_dist（構造一致）。埋め込み近接は話題類似であり、
  ここに使うと**マイオピア（近接採用）を助長**する。構造判定は引き続き LLM の役割。
- 依存: cos 距離は手計算（stdlib 内積）で可。ベクトル取得は HTTP+JSON。**numpy 必須ではない**。

**(B) Semantic Scholar Recommendations API = 候補拡張 … ★★**
- seed list（近傍シード論文）→ ML 推薦。bybridge の citation 2-hop / byserendipity の候補プールを
  **別アルゴリズムで水増し**する補助源。ただし推薦は「似たもの」を返す傾向＝遠ドメイン狙いには
  後段の距離ゲートが必須。

**(C) Elicit の構造抽出（define columns → 表充填）= Purpose/Mechanism 抽出の手本 … ★★**
- contra の中核は論文を Purpose/Mechanism に分解すること（`classify.py`）。Elicit の
  「**ユーザー定義スキーマを LLM が論文ごとに充填し、各セルに出典を付けてハルシネーションを抑える**」設計は、
  contra の抽出を**検査可能・再現的**にする参考になる（各抽出値に根拠スパンを添える等）。

### 2-3. ポジショニング上の示唆（プロジェクト同一性）

Elicit は **contra が「何でないか」を明確にする**。
- Elicit = 収束・関連性最大化・要約（研究を**速くする**）
- contra = 発散・遠い構造類推・関係再構成（視座を**広げる**）

両者は競合ではなく**直交**。contra は Elicit を真似て要約器になってはいけない、という設計上の歯止めを再確認できる。
（`serendipity_conditions.md` の「98%は捨て札」「狙えないものの代理変数を上げる」と整合。）

---

## 3. フロー別まとめ

| フロー | SPECTER2 距離(A) | Recommendations(B) | 構造抽出の手本(C) |
|---|---|---|---|
| byserendipity | ★★（ドメイン距離の連続化） | ★★（候補拡張） | ★★（purpose/mechanism 抽出） |
| bybridge | ★（遠ドメイン判定の補強） | ★★（2-hop の補完） | ★ |
| byrepo | — | — | ★（reliability 根拠の構造化） |
| bynote | — | — | ★★（メモ分解の精度） |

---

## 4. 制約整合（contra の禁則との両立）

- **stdlib のみ / 外部依存禁止**: S2 API は HTTP+JSON。SPECTER2 ベクトルの cos 距離は手計算可 → numpy 不要。
  新規 pip 依存なしで実装可能。
- **レート制限**: S2 は未認証 1 req/s、キーで専用枠。キャッシュ前提（埋め込みは論文 ID 単位でキャッシュ可）。
- **`models.py` / スコア設計は不変更**: 埋め込みは `concept_distance.py`（ドメイン距離）に限定して差し込み、
  `select_track_b` の構造判定（purpose_sim × mechanism_dist）には入れない。← **最重要の線引き**。
- **API キー**: `SEMANTIC_SCHOLAR_API_KEY` を環境変数化（既存の OPENAI/GITHUB と同じ運用）。

---

## 5. 推奨アクション（優先順）

1. **SPECTER2 埋め込みで `concept_distance.py` を補強する PoC** — L0/L1 Jaccard と埋め込み cos 距離を
   突き合わせ、近傍棄却の精度が上がるか検証。`spec.md` 将来構想の前倒し。**構造判定軸には入れない**こと。
2. **Semantic Scholar を OpenAlex と並ぶ追加コーパスとして評価** — 同一テーマで両者のヒット差を比較し、
   遠ドメイン候補の取りこぼしが減るか確認。
3. **構造抽出に出典スパンを添える（Elicit 流）** — `classify.py` の Purpose/Mechanism 抽出に根拠を付け、
   hollow judge の検査性を上げる。

---

## 6. 結論の一言

Elicit は **「使う対象」ではなく「自分が何でないかを映す鏡」**。実利は1階層下の **Semantic Scholar** にあり、
とくに **SPECTER2 埋め込みは `spec.md` の将来構想（概念アライメント距離）を低コストで実現する初の具体策**。
ただし **ドメイン距離軸に限定**し、contra の核である構造一致判定には混ぜないこと。

---

## 付記: 一次情報

- Elicit（138M 論文・データ源・API・Reports）: <https://elicit.com/>
- Semantic Scholar Academic Graph API（無料・SPECTER2・Recommendations・データ源）: <https://api.semanticscholar.org/api-docs/>
- SPECTER2（分野横断の科学文書埋め込み）: Ai2 ブログ "SPECTER2"
