# Semantic Scholar (semanticscholar.org) 調査レポート（contra への活用可否）

> 本ドキュメントは、学術検索/グラフ API である Semantic Scholar を、contra の**収集ソース／距離軸**
> として正式評価した記録。API 基礎は [`elicit_review.md`](elicit_review.md)（Elicit の基盤として既述）で
> 扱ったため、本稿は**重複を避け、OpenAlex（contra の現行コーパス）に対する固有の差別化点**に絞る。
> 調査手段: api.semanticscholar.org ドキュメント＋ DB 比較文献＋ Web 調査。調査日: 2026-06-14。
> 対象: <https://www.semanticscholar.org/> / API: <https://api.semanticscholar.org/api-docs/>
> 関連: [`elicit_review.md`](elicit_review.md), [`connected_papers_review.md`](connected_papers_review.md)

---

## 0. 結論（最重要）

1. **OpenAlex の置き換えにはならない。だが「初の真に加算的なソース」。**
   contra の中核 `concept_distance.py` は **OpenAlex concepts の L0/L1 階層**に依存しており、S2 に同等の
   概念タクソノミはない。メタデータ完全性も OpenAlex 優位（publication type 付与 86% vs S2 44%）。
   → **母集団は OpenAlex 据え置き**が正しい。

2. **S2 の価値は、OpenAlex に無い3つの加算レイヤー。各々が contra の具体ニーズに対応する。**
   - **(a) SPECTER2 埋め込み** → ドメイン距離軸の連続化（`concept_distance.py` 補強）。※構造一致軸には使わない。
   - **(b) Recommendations API**（seed list → ML 推薦）→ byserendipity/bybridge の候補拡張。
   - **(c) 引用インテント分類＋影響度** → **bybridge の bridge 品質向上（本稿の新発見）**。

3. **(c) が今回の目玉。** S2 は各引用を **cites background / methods / results** に分類し、
   **influentialCitationCount（強い影響を与えた引用）**を持つ。bybridge は現状
   「`referenced_works_count:<max_refs` で intro-citation dump を雑に除外」しているが、これを
   **「methods/results を引く＝意味のある bridge」優先に置き換えられる**。contra が気にする
   Purpose/Mechanism の構造接続に、引用の"質"で踏み込める。

---

## 1. OpenAlex に対する固有差別化点（要点）

| 観点 | OpenAlex（現行） | Semantic Scholar | contra への含意 |
|---|---|---|---|
| 規模 | 250M+ 全分野 | 200M+（AI/ML/CS 強い） | 重複大・相補。母集団は OpenAlex 維持 |
| 概念階層 | concepts L0/L1 あり | 同等なし | `concept_distance.py` は OpenAlex 依存のまま |
| メタデータ完全性 | 高（type 86%） | 低（type 44%、Web 抽出主体） | S2 単独は粗い |
| 参照リンク | ~982.6M（2015–23） | ~994.3M | 互いに取りこぼし → **相互補完の価値** |
| 埋め込み | なし | **SPECTER2** | ドメイン距離軸の連続化 |
| 推薦 | なし | **Recommendations API** | 候補拡張 |
| 引用の質 | referenced_works のみ | **intent 分類＋influential** | **bridge 品質の精緻化** |
| API | 完全オープン | キー要・1 req/s | レート/キー管理が必要 |

---

## 2. contra への活用評価（3用途の枠組み）

### 2-1. 発見コーパス
- **△ 補完候補（置換ではない）**。OpenAlex と参照リンクが互いに取りこぼす事実は、
  「遠ドメイン候補の取りこぼし低減」に S2 併用が効く可能性を示す。ただし概念階層を欠くため、
  **収集の主役は OpenAlex、S2 は加算レイヤー**という役割分担が妥当。

### 2-2. 手法 / インフラ層 ← 本命

**(c) 引用インテント＋影響度 = bybridge の bridge 品質 … ★★★（本稿の主findings）**
- 現状 `collect_citation_candidates`：近傍シードの共有参照を bridge とし、`type:article` ＋
  `referenced_works_count:<max_refs` で「レビュー/intro-citation dump（偽 bridge）」を**ヒューリスティックに**除外。
- S2 の引用 intent（background/methods/results）＋ influential フラグを使えば、
  **「methods/results として引かれている共有参照」だけを bridge に採用**でき、
  「背景として惰性的に引かれただけ（偽 bridge）」を**原理的に**落とせる。
  → contra が狙う「機能的・構造的接続」に、引用の意味で踏み込む精緻化。
- 注意: bybridge の選出ロジック変更は `spec.md` 禁則で**要仕様確認** → 本実装前に確認。PoC/提案レベル。

**(a) SPECTER2 埋め込み = ドメイン距離軸 … ★★（[`elicit_review.md`](elicit_review.md) と同結論）**
- `concept_distance.py`（L0/L1 Jaccard 近傍棄却）の連続化に。**構造一致軸（purpose_sim×mechanism_dist）には
  使わない**（マイオピア助長）。cos 距離は stdlib 手計算可。

**(b) Recommendations API = 候補拡張 … ★★**
- 近傍シード → ML 推薦で候補プールを別アルゴリズムで水増し。推薦は近傍寄り → **遠ドメイン化の距離ゲート必須**。

### 2-3. ポジショニング
S2 は前2例（Elicit/Consensus の「対極の SaaS」）と違い、**素材（API レイヤー）として中立**。
contra はこれを「要約のため」ではなく「**距離測定と bridge 品質のため**」に使う、という用途の差が肝。

---

## 3. フロー別まとめ

| フロー | 引用intent(c) | SPECTER2(a) | Recommendations(b) |
|---|---|---|---|
| bybridge | ★★★（偽 bridge 除去） | ★（遠ドメイン判定補強） | ★★（2-hop 補完） |
| byserendipity | ★（接続検証の材料） | ★★（ドメイン距離連続化） | ★★（候補拡張） |
| byrepo / bynote | — | — | — |

---

## 4. 制約整合・推奨

- **stdlib のみ**: S2 は HTTP+JSON。埋め込み cos 距離は手計算。新規 pip 依存なし。
- **キー/レート**: `SEMANTIC_SCHOLAR_API_KEY` を環境変数化。1 req/s → 論文 ID 単位でキャッシュ前提。
- **禁則**: bybridge 選出ロジック・`concept_distance` の距離設計変更は要確認。`select_track_b` の構造判定不変更。
- **推奨アクション（優先順）**:
  1. **引用インテント/influential で bybridge の bridge 選別を精緻化する PoC**（要仕様確認）。
     現行の `referenced_works_count` ヒューリスティックを、引用の"質"で置換できるか検証。
  2. **SPECTER2 で `concept_distance.py` を補強**（Elicit レポート推奨①と同じ）。
  3. **Recommendations API で候補拡張**（距離ゲート前段）。

---

## 5. 結論の一言

Semantic Scholar は **これまでで唯一、contra に"素材として"加算価値を持つ対象**。母集団は OpenAlex のままで、
S2 は **埋め込み（距離）・推薦（拡張）・引用インテント（bridge 品質）** の3レイヤーを足す。
とりわけ **引用インテントは bybridge の"偽 bridge 除去"をヒューリスティックから原理へ引き上げる**、
今回の調査群で最も実装価値の高い発見。

---

## 付記: 一次情報

- S2 Academic Graph API（埋め込み/推薦/引用）: <https://api.semanticscholar.org/api-docs/>
- 引用インテント分類（background/methods/results）: Ai2 Blog "Citation Intent Classification"
- DB 比較（OpenAlex vs S2 のメタデータ/参照カバレッジ）: arXiv:2406.15154（QSS, MIT Press）
