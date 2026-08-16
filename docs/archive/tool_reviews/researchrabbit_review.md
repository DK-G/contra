# ResearchRabbit (researchrabbit.ai) 調査レポート（contra への活用可否）

> 本ドキュメントは、文献発見ツール ResearchRabbit（「論文の Spotify」）を調査し、contra への活用可否を判定した記録。
> 調査手段: 各種レビュー＋ Web 調査。調査日: 2026-06-14。
> 対象: <https://www.researchrabbit.ai/> / アプリ: researchrabbitapp.com（無料・要アカウント）
> 関連: [`connected_papers_review.md`](connected_papers_review.md), [`semantic_scholar_review.md`](semantic_scholar_review.md)

---

## 0. 結論（最重要）

1. **検索先にはならない（SaaS・公開 API なし）。** 基盤は **OpenAlex / Semantic Scholar / PubMed**＝contra が
   既に持つ/叩ける母集団。無料だが Web アプリのみで、プログラム収集には使えない。

2. **価値は「contra を位置づける4接続タイプの分類」。** ResearchRabbit は論文網を
   **(1) 直接引用 / (2) 書誌的結合（共有参照）/ (3) 共著 / (4) 意味的類似（title/abstract）** の4種で構成。
   これに contra を当てると、**どれを使い・どれを反転し・どれを避けるか**が一目で整理できる。

3. **新規の実装示唆は薄い。** 「コレクションから推薦」は S2 Recommendations API（既出）と同等で、
   それは contra の**履歴/メモリ層を seed にした推薦**に対応づく。**共著(3)は近傍シグナル**で Track B には不適。

---

## 1. ResearchRabbit とは

- **正体**: 「論文の Spotify」。seed（論文/キーワード/トピック）→ 関連論文を提示 → コレクションに追加すると
  **選好を学習**してさらに良い推薦を返す（プレイリスト的）。
- **接続4タイプ**: 直接引用 / 書誌的結合 / 共著リンク / AI 意味類似。
- **可視化**: インタラクティブな引用ネットワーク＋**著者コラボネットワーク**。
- **コーパス**: OpenAlex / Semantic Scholar / PubMed。
- **提供**: 無料・要アカウント。公開 API は実質なし。

---

## 2. contra への活用評価

### 2-1. 発見コーパス
- **❌ 不要**。OpenAlex/S2/PubMed の上の無料 SaaS、API なし。母集団は OpenAlex 直叩きで足りる。

### 2-2. 手法 / インフラ層

**(A) 4接続タイプに contra を当てた整理 … ★★（分析的価値）**

| ResearchRabbit の接続 | contra での扱い | 備考 |
|---|---|---|
| 直接引用 | 使用（bybridge の citation） | ○ |
| 書誌的結合（共有参照） | **中核**（bybridge の bridge プール） | ○ Connected Papers 同様、遠ドメイン方向に反転利用 |
| **共著（co-authorship）** | **避ける** | 著者は基本ドメイン内 → **近傍シグナル＝マイオピア要因**。Track B に入れない |
| 意味的類似（title/abstract） | **距離として使う**（SPECTER2 / concept_distance） | 類似度を"近さ"でなく"遠さ"判定に反転 |

→ contra は ResearchRabbit と**同じ部品**を持つが、(2)(4) を**遠ドメイン方向に反転**し、(3) を**意図的に捨てる**点で異なる。
これは「同じ引用グラフ部品でも目的設定で逆の道具になる」（Connected Papers レポートの結論）の補強。

**(B) コレクション→推薦 = メモリ層 seed の発想 … ★（既出の補強）**
- 「貯めたコレクションから学習して推薦」は、contra の**テーマ別採用履歴（`history.py` / OKF メモリ層）を seed に
  遠ドメイン候補を推薦**する案に対応。実装の実体は **S2 Recommendations API**（[`semantic_scholar_review.md`](semantic_scholar_review.md)）。
  推薦は近傍寄り → **距離ゲート必須**。新規性は低く、既出の合流点を補強する程度。

**(C) 可視化 … ★（既出）**
- 引用ネットワーク表示は Connected Papers と同様、contra の bridge グラフ可視化の参考。著者ネットワークは contra 対象外。

### 2-3. ポジショニング
ResearchRabbit は Connected Papers の親戚（収束型の発見/推薦＋可視化）。**共著という近傍軸を足している分、
むしろ contra が"避けるべき軸"を明示してくれる**点で対照的価値がある。

---

## 3. 結論の一言

ResearchRabbit は **新しい部品をくれないが、contra の立ち位置を4接続タイプの座標で明確化してくれる**。
contra は同じ引用グラフ部品のうち **書誌的結合・意味類似を"遠さ"方向へ反転**し、**共著・近傍推薦は避ける**——
その線引きを再確認する材料。実装の実体は既出（S2 Recommendations / 可視化）に集約され、固有の新規実装はない。

---

## 付記: 一次情報

- ResearchRabbit の仕組み（4接続タイプ・コレクション学習・コーパス）: 各レビュー（Aaron Tay, Medium / NIH PMC）
- アプリ（無料）: researchrabbitapp.com
