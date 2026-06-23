# Scopus / Web of Science 調査レポート（contra への活用可否）

> 一般論文サイト総覧 #12（締め）。商用書誌 DB。OpenAlex 基準（[`openalex_review.md`](openalex_review.md)）が
> これらの開かれた代替たりうるか、の観点で評価。
> 調査手段: Elsevier/Clarivate API 方針＋ OpenAlex 比較文献。調査日: 2026-06-15。
> 対象: Scopus（Elsevier）/ Web of Science（Clarivate）

---

## 0. 結論（最重要）

**不採用（確定）。両者とも機関サブスク必須・再配布禁止の閉じた商用 DB で、contra の方針（無料・合法・配布可）と
根本的に非両立。そして OpenAlex が検証済みの開かれた代替である。**
- Scopus/WoS の API は**機関サブスク前提・認可ユーザー限定・データ再配布不可**。contra は購読も再配布もできない。
- OpenAlex は **参照カバレッジが両者と comparable**、**OA 誌カバレッジは桁違いに広い**（OA 誌で OpenAlex 34,217 vs
  Scopus 7,351 / WoS 6,157）。bibliometrics でも proprietary の代替として受容が進む。

---

## 1. 要点

| 観点 | Scopus / WoS | OpenAlex（基準） |
|---|---|---|
| アクセス | **機関サブスク必須・API キー・再配布禁止** | 無料・キー不要・CC0 |
| 規模/カバレッジ | 厳選・歴史的深さ | 250M+、OA 誌は桁違いに広い |
| 参照カバレッジ | 高 | **comparable** |
| abstract | やや多い | やや少ない（inverted index） |
| contra との適合 | **不可（購読/再配布の壁）** | バックボーン |

- contra は**有料購読を前提にできず**、結果に proprietary データを混ぜると**配布物の合法性が崩れる**。
  → 商用 DB は構造的に採れない。

---

## 2. 結論の一言

Scopus/WoS は **品質は高いが contra には構造的に不採用**（購読・再配布禁止・コスト）。
**OpenAlex がその開かれた代替**であり、参照は comparable・OA は桁違いに広い。商用 DB を諦めても contra は損をしない。

---

## 付記: 一次情報

- OpenAlex vs WoS/Scopus 参照カバレッジ: arXiv:2401.16359 / Scientometrics 2025
- OA 誌カバレッジ比較（OpenAlex 34,217 vs Scopus 7,351 / WoS 6,157）: PLOS One（OpenAlex/Scopus/WoS）
- Scopus/WoS API（サブスク必須）: Elsevier / Clarivate API 方針
