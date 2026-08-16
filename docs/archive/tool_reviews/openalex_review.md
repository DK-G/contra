# OpenAlex (openalex.org) 調査レポート（contra の現行バックボーン・基準）

> 本ドキュメントは、contra の現行収集ソース OpenAlex を**基準（baseline）**として総覧し、
> 強み・依存・リスク・他ソースとの役割分担を整理した記録。以後の論文サイト評価はこの基準と比較する。
> 調査手段: docs.openalex.org ＋ Web 調査。調査日: 2026-06-15。
> 対象: <https://openalex.org/> / API: <https://docs.openalex.org/>
> 関連: [`semantic_scholar_review.md`](semantic_scholar_review.md), [`arxiv_review.md`](arxiv_review.md), [`core_review.md`](core_review.md)

---

## 0. 結論（最重要）

1. **OpenAlex は contra のバックボーンとして妥当。引き続き主役。**
   **全分野・250M+ works・無料・APIキー不要**（polite pool＝email 添付で高速化）。概念階層・引用・OA リンクを一体提供し、
   contra が必要とする「広さ(recall)＝遠ドメイン射程の最大化」を唯一満たす。

2. **⚠ 重要リスク: OpenAlex は Concepts を Topics へ移行中。** contra の `concept_distance.py` は
   **Concepts の L0/L1 階層**（19 ルート＋6層、約65k）に依存しているが、OpenAlex は新しい **Topics**
   （約4,500、階層 Topic→Subfield→**Field**→**Domain**）へ軸足を移し、**Concepts は凍結/非推奨方向**。
   → **concept_distance を Topics/Domain-Field 階層へ移行する計画が必要**（本総覧で最大の実務的発見）。

3. **「abstract が薄い」根本原因も OpenAlex 側にある。** 法的制約で **abstract は inverted index のみ（プレーンテキスト無し）**。
   これが byserendipity の mechanism 判定の薄さの根。→ 全文 provider 層（arXiv/CORE/IA Scholar）で補う設計が正当化される。

---

## 1. OpenAlex の構成（contra 視点の要点）

| 要素 | 内容 | contra での使われ方 |
|---|---|---|
| 規模/分野 | 250M+ works、**全分野** | 遠ドメイン射程の母集団（広さ＝recall） |
| アクセス | 無料・**キー不要**、polite pool（email）で高速。~100k/日・~10/s | 既存収集の基盤 |
| **Concepts** | 約65k・**19 ルート(L0)＋6層** | **`concept_distance.py` の L0/L1 Jaccard 近傍判定**（←移行リスクあり） |
| **Topics**（新） | 約4,500・Topic→Subfield→**Field(~26)**→**Domain(4)** | 移行先候補。Domain≒新 L0、Field≒新 L1 |
| 引用 | `referenced_works`（外向き）/ `cited_by_count` | **bybridge の citation 2-hop / bridge プール** |
| abstract | **inverted index のみ**（法的制約） | 復元して使用。薄さの根→全文 provider で補強 |
| OA | `best_oa_location` / `oa_url` | **全文 provider 層の入口**（→ arXiv/Unpaywall/CORE/IA Scholar） |
| bulk | データスナップショット（全件ダンプ） | 大規模実験時の選択肢 |

---

## 2. contra への含意（基準として）

### 2-1. 強み（維持すべき理由）
- **広さ（recall）**: 全分野ゆえ「分野は遠いが構造一致」の遠ドメイン探索に必須。arXiv（STEM 精度）等はこれを**補完**する立場。
- **オープン性**: キー不要・無料・ダンプ公開。contra の「コスト最小・合法・安定」方針に最も合致。
- **一体性**: 概念階層・引用・OA リンクが1 API に揃う（距離・bridge・全文入口を同時に賄える）。

### 2-2. リスク／要対応
- **(R1) Concepts → Topics 移行 … ★最重要**:
  - `concept_distance.py` は Concepts L0/L1 前提。Concepts 非推奨化が進むと**距離計算が陳腐化/不安定化**。
  - 対応: **Topics 階層（Domain/Field）への移行設計**。Domain(4)≒L0、Field(~26)≒L1 として Jaccard を組み直す。
    粒度が変わる（Concepts 65k → Topics 4.5k）ため、**近傍棄却の閾値（`_NEAR_L01_THRESHOLD=0.30` 等）の再較正**が要る。
  - `spec.md` 禁則（`concept_distance` の距離設計変更は要確認）に従い、**仕様確認の上で計画的に**。
- **(R2) abstract の薄さ**: inverted index のみ。mechanism 判定の質は全文 provider 層（arXiv/CORE）で補う（既出スレッド）。
- **(R3) polite pool 運用**: email 添付推奨。レート/リトライは既存クライアントで吸収済みか確認。

### 2-3. 他ソースとの役割分担（基準の確認）
- **発見の広さ**: OpenAlex（主）＋ arXiv（STEM 精度の副次）。
- **引用の質**: OpenAlex `referenced_works`（基本）＋ S2 引用インテント（bridge 精緻化）。
- **距離信号**: OpenAlex Topics/Domain-Field（移行後）＋ SPECTER2（連続化、距離軸限定）。
- **全文**: OpenAlex `oa_url` → arXiv/Unpaywall/CORE/IA Scholar の provider 層。

---

## 3. 推奨アクション

1. **(最優先・要仕様確認) concept_distance の Topics 移行を計画**: Concepts 非推奨化に備え、Domain/Field 階層で
   近傍判定を組み直す設計と閾値再較正。移行前に現行 Concepts 依存箇所を棚卸し。
2. **polite pool の徹底**: 全リクエストに contact email を付与（高速・安定）。
3. **全文 provider 層の入口を `oa_url` に固定**: OA 解決の起点を OpenAlex に統一し、provider にフォールバック。

---

## 4. 結論の一言

OpenAlex は **contra の正しいバックボーン**（全分野・無料・キー不要・概念/引用/OA を一体提供）。
ただし **Concepts → Topics 移行は距離計算の足元に関わる最重要リスク**で、計画的な移行が要る。
abstract の薄さは全文 provider 層で補う——この基準を軸に、他の論文サイトは「OpenAlex に何を加算するか」で評価する。

---

## 付記: 一次情報

- Works/Concepts/Topics ドキュメント: <https://docs.openalex.org/api-entities/works/work-object> /
  <https://docs.openalex.org/api-entities/concepts> / <https://docs.openalex.org/api-entities/topics>
- API 概要（無料・polite pool）: <https://docs.openalex.org/>
