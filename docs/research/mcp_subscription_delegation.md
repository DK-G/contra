# 改修案: MCPクライアント委譲によるサブスク運用（多層防御つき）

> 本ドキュメントは、contra の LLM 処理を**従量 API ではなく Claude Max サブスク枠**で回すための改修案。
> 想定ユーザーは当面**作者自身（個人/研究用途）**。実装は別途、本書は設計のみ。
> 由来: ブレストでの「サブスク内で処理する方法」検討 → 案②（MCPクライアント委譲）を、
> 「**安全弁はコードとエージェント両方に持たせる（多層防御）**」という原則で具体化したもの。
> 対象コード: `src/mcp_server.py`, `src/pipeline/classify.py`, `concept_distance.py`, `collect.py`, `docs/agent_rules/`。

---

## 0. 目的と核心（最重要）

- **目的**: LLM 判定・生成を **contra 自身の API キー（従量課金）から外し**、呼び出し側エージェント
  （= Max サブスクで動く Claude Code）の**自分の推論**として実行する。
  → **従量$が消え、最高モデル（Opus 4.8）で判定・生成できる**（API ではコスト理由に小型モデルへ落としていた制約が外れる）。
- **核心原則 = 多層防御（defense in depth）**:
  - **エージェント層（賢いが揺らぐ）**: `docs/agent_rules` に従い、purpose_sim × mechanism_dist の判定・hollow 判定・
    4部構成生成・遠ドメインクエリ生成を行う。さらに**自己フィルタ**（弱い接続は surface しない）。
  - **コード層（決定論・絶対バイパス不可）**: エージェントが返した数値を**ハード閾値で再検証**し、違反は無条件で落とす。
    LLM がどう言い繕っても `purpose_sim < 0.20` の anomaly は**コードが機械的に棄却**する。
  - → **同じ安全弁を二重化**。賢い判断の下に決定論の床を敷く。

---

## 1. アーキテクチャ: contra = 素材プロバイダ / エージェント = 判定者・執筆者

今の contra は MCP ツール内で**自分が LLM を叩く**（従量発生源）。改修後はこれを反転する。

| 工程 | 現状 | 改修後の担当 | LLM? |
|---|---|---|---|
| OpenAlex/GitHub 収集 | contra | **contra ツール** | 不要 |
| concept_distance（L0/L1, 近傍判定） | contra | **contra ツール** | 不要 |
| bybridge citation 2-hop | contra（raw_only既存） | **contra ツール** | 不要 |
| 履歴重複排除 / has-abstract | contra | **contra ツール** | 不要 |
| **遠ドメインのクエリ生成** | LLM(contra) | **エージェント** | LLM |
| **purpose_sim × mechanism_dist 判定 / hollow 判定** | LLM(contra) | **エージェント** | LLM |
| **4部構成生成** | LLM(contra) | **エージェント** | LLM |
| **数値ゲートの最終適用** | contra | **contra ツール（後段検証）** | 不要 |

「**LLM を使う工程は全部エージェント側／決定論は全部 contra 側**」が境界。`raw_only` と `--gen-mode structured`
が既にあるので、contra を"キー無しで完結"に寄せる足場は既存。

---

## 2. 安全弁の二重化（どのゲートをどちらに置くか）

### 原則
- **純粋な数値/集合演算で決まる弁 → コード側で"必ず"適用（pre-filter）**。エージェントに渡す前に弾く。
- **LLM 判断に依存する値（purpose_sim 等）→ エージェントが採点＋自己フィルタ。その返り値にコードが床を再適用（post-gate）**。
  - エージェントの採点を**信用しつつ、信用しない**。賢い判断は活かすが、ハード床は機械が担保する。

### 弁の配置表

| 安全弁（既存定数） | 種別 | コード層 | エージェント層 |
|---|---|---|---|
| 近傍ドメイン棄却 `_NEAR_L01_THRESHOLD=0.30` | 決定論（Jaccard） | **pre-filter で必ず適用** | （agent_rules に明記し意識させる） |
| 近傍 mechanism_dist 上限 `_NEAR_DOMAIN_MECH_CAP=0.5` | 決定論 | **post で必ず cap** | 同上 |
| Anomaly 棄却 `_PURPOSE_SIM_MIN=0.20` | LLM値→閾値 | **post-gate で必ず落とす** | 採点＋自己棄却 |
| serendipity 床 `_SERENDIPITY_GATE=0.20` | LLM値→閾値 | **post-gate** | — |
| hollow 床 `_STRUCT_DEPTH_GATE=0.50` | LLM値→閾値 | **post-gate** | hollow judge を実施 |
| 出力品質フロア `output_floor=0.35` | LLM値→閾値 | **post-gate** | — |
| M3 飽和（0件なら水増し禁止） | 決定論 | **post で判定・飽和ノート** | 弱候補を無理に出さない |

→ **エージェントが甘く採点しても、コードの post-gate が床で刈る**。逆に**コードだけだと拾えない質的判断（構造の本物さ）を
エージェントが補う**。両層が互いの穴を塞ぐ。

---

## 3. 処理フロー（3段）

```
[1] contra ツール: 収集 → 決定論 pre-filter
    （concept_distance 近傍棄却 / 履歴重複排除 / has-abstract / citation 2-hop）
    → "生の候補プール"（スコア無し）を返す。LLM 不使用＝キー不要。
        ↓
[2] エージェント（Max/Opus 4.8）: docs/agent_rules に従い
    遠ドメインクエリ生成・purpose_sim × mechanism_dist 採点・hollow 判定・4部構成生成。
    自己フィルタ（明らかな anomaly/近接は surface しない）。
    → スコア付き候補＋生成本文を、構造化して contra ツールに返す。
        ↓
[3] contra ツール: 決定論 post-gate（最終安全弁）
    anomaly(<0.20) / serendipity-gate / struct_depth(<0.50) / near-domain cap / output-floor を
    エージェントの返り値に"必ず"再適用 → 違反は無条件棄却。0件なら M3 飽和ノート。
    → Markdown 整形・履歴記録。LLM 不使用。
```

要点: **LLM の高コスト工程（[2]）だけがサブスク枠**。安全弁は [1] と [3] の決定論コードに残る。

---

## 4. 注意点（誤解しやすい点の記録）

1. **無制限ではない**: Max は従量$が無い代わりに**使用量上限（rolling-window＋週次キャップ）**がある。値は改定で変わるので
   **現行値は要確認**。候補多数 × `--score-votes` は判定が数十〜百回走り、**重いランは枠を食ってスロットルに当たり得る**。
   → 1ラン当たりの候補数・投票数を抑える設計（pre-filter で母数を絞る[1]が効く）。
2. **再現性トレードオフ**: コード化された数値ゲートは決定論だが、エージェントの採点は揺らぐ。
   → 二重化でハード床は守るが、**ボーダーの揺れは残る**。`docs/agent_rules` を厳密に書くほど安定する。
3. **コンテキスト窓**: 候補の abstract（＋全文）を一度に判定すると窓が膨らむ。→ **バッチ/ストリーム分割**前提。
4. **用途スコープ**: 個人/研究用途（作者自身）なら妥当。**製品バックエンドとして不特定多数に叩かせる形にしない**
   （Claude Code サブスクの想定利用を外れる）。当面ユーザー＝自分、を明記。
5. **`spec.md` 禁則**: `models.py` データクラス・`select_track_b` のスコア設計（purpose_sim × mechanism_dist、閾値）の
   変更は要確認。本改修は**「LLM 呼び出しの場所」を移すのが主**で、**スコア設計値（0.20/0.50/0.35 等）は変えない**前提。
   ゲート値の所在をコード post-gate に集約する形にする。

---

## 5. 改修ポイント（実装は別途）

1. **MCP ツールに "raw/material モード" を一般化**:
   - 既存の bybridge `raw_only` を全フローへ拡張。各 by ツールが**スコア無しの生候補＋距離だけ**返せるモードを持つ。
2. **決定論 pre-filter / post-gate を LLM から分離**:
   - `classify.py` の数値ゲート（anomaly / serendipity / struct_depth / near-domain cap / output-floor / M3）を、
     **LLM 採点とは独立に呼べる純関数**として切り出し、post-gate として再利用。
   - エージェントが返す JSON スキーマ（`purpose_sim`, `mechanism_dist`, `structural_depth`, 4部本文）を定義。
3. **`docs/agent_rules` を"判定指示書"として強化**:
   - 各 by フローの運用定義に、**採点アンカー（離散 purpose_level）・hollow 判定基準・anomaly/近接の自己棄却**を明記。
     コード post-gate と**同じ閾値**を言語化し、二重化の整合を取る。
4. **段階導入**:
   - (a) bybridge raw_only ＋ structured 整形（キー無し）でまず一周。
   - (b) pre-filter / post-gate を純関数化し、エージェント採点を受け取る経路を追加。
   - (c) byserendipity のクエリ生成・採点・生成をエージェントへ委譲。
   - (d) Track A/byrepo は接地が仕事＝エージェント判定と相性良し（前メモの「フロー別に思想を分ける」）から先に。

---

## 6. 結論の一言

案②は「**従量$ → サブスク定額＋最高モデル**」を実現する。鍵は**安全弁の二重化**——
**質的判断と生成はエージェント（Max/Opus 4.8）へ、絶対外せない数値床はコードの決定論ゲートに残す**。
これで「賢いが揺らぐ」上に「機械的で硬い」床を敷き、コスト・品質・安全を同時に取りに行く。
当面ユーザーは作者自身、製品配布はスコープ外。
