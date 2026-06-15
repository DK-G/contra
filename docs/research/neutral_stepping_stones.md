# 中立踏み石（neutral stepping-stones）— byserendipity/bybridge の射程拡張設計

> 本ドキュメントは、ブレストで得た「セレンディピティ ⇄ 生物進化の有効変異」という構造類推から導いた
> contra の設計改善案を、批判的検証（自己 anomaly 判定）を経た形で記録する設計メモ。**実装は別途**。
> 由来: 進化生物学の中立進化／中立ネットワーク（木村, Maynard Smith, Schuster/Fontana, Wagner; LTEE Cit+ の
> potentiation）を contra の質ゲートに外適応（exaptation）した。これ自体が「遠ドメイン機構の転用」の実演＝
> 理論の self-validation。
> 前提: [`serendipity_conditions.md`](serendipity_conditions.md)。対象コード: `src/pipeline/classify.py`, `collect.py`。

---

## 0. 核となる主張（批判検証後の最終形）

- **観察**: bybridge は 2-hop（seed → 共有参照 → 遠候補）。質ゲートは **anomaly（`_PURPOSE_SIM_MIN=0.20` 未満）**と
  **hollow（`structural_depth < _STRUCT_DEPTH_GATE=0.50`）**を落とす。一番派手な当たり＝高 mechanism_dist の遠峰は、
  この 2-hop＋ゲートの射程外にあり届かない。
- **写像**: 生物の中立変異＝それ自体は無報酬だが、そこからしか届かない革新がある（LTEE: 中立 potentiating 変異の
  蓄積後に Cit+ が到達可能になった）。contra の **hollow-but-true** な接続も同様の「踏み石」になりうる。
- **重要な線引き（中立 ≠ anomaly）**: 中立ネットワークが歩けるのは**機能（不変量）を保存するから**。
  - **anomaly（purpose_sim<0.20＝偽接続）= 致死変異** → 従来どおり即棄却（踏み石にするとノイズへ崩壊）。
  - **hollow（purpose は保つが mechanism 浅い）= 中立変異** → **捨てず、出力もせず、踏み石として保持**。
  - contra は既に「truly hollow は切るが loose causal は残す」と半分やっている（`classify.py:281`）。本案はこれを
    「**truly hollow も出力はせず多段探索の踏み石に残す**」へ一歩進める。
- **撤回した誤り**: 当初の「betweenness（媒介中心性）の高いノードを踏み石に選ぶ」は**誤り**。高 betweenness＝
  ハブ＝汎用領域＝**マイオピアへの回帰**で、目的を破壊する。生物も innovability を**周縁への拡散**で説明し、
  ハブ集中を支持しない。→ 踏み石の選択は **betweenness ではなく「ドメイン多様性／距離」**。
- **必要条件（load-bearing）**: 多段歩行で seed の Purpose 信号が洗い流されると、末端ゲートは無関係候補への
  後付け合理化になる。→ **歩行を seed の iso-purpose 多様体に拘束する不変量が必須**（→ §2 (b)）。

---

## (a) 最小プローブ実験設計 — 「存在問題」を最小コストで突く

**問い**: 「2-hop では誰も届かないが、iso-purpose 3-hop だけがフル質ゲートを越える本物の構造一致候補」は、
実在するか？（理屈では決まらない＝経験的にしか答えが出ない。）

### 手順
1. **テーマ選定**: 持ち運べる機構（フィードバック/拡散/相転移/探索-活用 等）を核に持つテーマを 1–3 本。
   自分が深く grounding している分野（hit を認識できる sagacity がある領域）。
2. **2-hop 到達プール `P2`**: 通常 bybridge（`collect_citation_candidates`、**raw_only で可・LLM コスト無**）の
   **ゲート前の全到達候補**を保存。← これが「2-hop の射程そのもの」。
3. **2-hop 出力 `B2`**: `P2` にフル質ゲート（percentile + `_SERENDIPITY_GATE` + hollow `_STRUCT_DEPTH_GATE`）を
   かけて通った集合（＝現状の出力）。
4. **中立リザーバ `N`**: 同じ 2-hop run で **anomaly は通る（purpose_sim ≥ 0.20）が hollow（structural_depth<0.50）**の
   ノード。ここから**ドメイン多様性で散らした小サブセット**（K≈10–20、互いに L0/L1 が分散）を取る。**betweenness 不使用**。
5. **iso-purpose 3-hop `H3`**: `N` の各ノードからもう一段だけ bridge 展開（raw_only）。得た候補のうち
   **seed への purpose_sim ≥ θ_p（§b）を満たすものだけ残す**（iso-purpose 拘束＝"生存"条件）。3-hop 上限で打ち切り。
6. **末端ゲート**: `H3` にフル質ゲートを適用 → `H3_pass`。

### 評価指標と判定
- **主指標**: `H3_pass \ P2`（＝**2-hop の射程プールに最初から入っていない**のに 3-hop でゲートを越えた候補）。
- **対照アーム（交絡除去・最重要）**: 単に「2-hop ゲートを緩めれば出る」ものは価値ゼロ。価値は**経路（topology）由来**でなければ
  ならない。→ `H3_pass` が `P2`（**全閾値で 2-hop が到達しうる集合**）の**外**にあることを必須条件にする。
  これで「射程の拡張（経路）」と「閾値の緩み（ゲート）」を分離する。
- **人手判定**: `H3_pass \ P2` の各候補を、grounding ある人間が「本物の構造一致か」を最終選択圧として判定。
- **決定則**:
  - テーマ横断で **1 件でも人間が本物と認める 3-hop-only 候補が出れば** → 中立踏み石は射程を伸ばす＝**払い戻す**。
  - 一貫して **ゼロ** → このコーパス/設定では非実在 → **潔く棄却**（Phase 2 を畳む）。

### コスト制御
- hops は **raw_only（LLM 不要）**、LLM は末端ゲート（小さい `H3`）のみ。K と 3-hop 上限で爆発を抑える。
- 生物のドリフトも全空間を歩かない（遅い有限集団）。**網羅を諦め、末端ゲートを選択圧にする**思想を踏襲。

---

## (b) 不変量＝Purpose の操作的定義（iso-purpose floor θ_p）

**狙い**: 多段歩行を seed の「等 Purpose 面」に拘束し、Purpose 信号の洗い流し（→後付け合理化）を防ぐ。
生物の「等適応度面に拘束された中立ドリフト」と同型にする。

### 定義
- **不変量** = `purpose_sim(node, SEED)`。**既存の purpose_sim 指標をそのまま使う**（`classify.py` の離散アンカー
  level → purpose_sim）。新指標は作らない。直前ノードではなく**常に seed に対して**測るのが肝（誤差の累積＝
  Purpose 漂流を止める）。
- **iso-purpose floor θ_p**: 各 hop で `purpose_sim(node, SEED) ≥ θ_p` を要求。割ったら**その経路は致死＝打ち切り**。
- **変えてよい/伸ばす量** = mechanism_dist（射程）＋ domain distance。Purpose を保ち、機構表現とドメインだけ遠くへ。

### θ_p の値域＝Goldilocks 帯の操作的定義（本案の一番おいしい所）
- θ_p が **高すぎ** → 中立歩行が home 分野を出られず、新しい遠峰に届かない（マイオピア）。
- θ_p が **低すぎ** → Purpose が洗い流され anomaly/ノイズへ崩壊（後付け合理化）。
- よって θ_p には**最適帯**が存在し、これが [`serendipity_conditions.md`](serendipity_conditions.md) の
  「最適認知距離 / Goldilocks」の **operational 定義**になる。定性原理に数値の足場を与える。
- **下限の制約**: 単発の anomaly 床は `_PURPOSE_SIM_MIN = 0.20`。多段で"生存"するには余裕が要るため
  **θ_p ≥ 0.20、かつ単発床より上**に置く（hop ごとに purpose を再要求するため）。
- **既存ノブとの関係**: θ_p は `_SERENDIPITY_GATE(0.20)`（最終スコア床）や `_NEAR_L01_THRESHOLD(0.30)`（ドメイン近傍）
  とは**別物の新ノブ**（hop 単位の seed-purpose 床）。ただし purpose_sim と同一単位で表現する。

### 較正は (a) と結合させる（推測で決めない）
- (a) のプローブで θ_p を小さく掃引（例 0.20 / 0.30 / 0.40）し、各点で `|H3_pass \ P2|`（本物 hit 数）を観測：
  - 低 θ_p: `H3` 大だが末端ゲート通過率→0（ノイズ）。
  - 高 θ_p: `H3` が near-domain に縮退（新規射程ゼロ）。
  - **本物 hit を最大化する θ_p = 操作的 Goldilocks 床**。
- → **(a) は存在検証であると同時に (b) の較正実験**。二つは一体。

---

## 残る不確実性と撤退条件（正直に）

1. **存在は経験的**: cross-domain な iso-purpose 経路が「2-hop が届かず 3-hop で届く」形で実在するかは、
   armchair では決まらない。(a) の `H3_pass \ P2` がゼロなら棄却。
2. **これは初当たりの最短路ではない**: 素の 2-hop bybridge ＋ 良テーマ ＋ 人手読了の方が速い。中立踏み石は
   「素の路が当たると確認できた後」の **Phase 2 射程拡張**。優先度は中。
3. **事後合理化リスク**: 3-hop の鎖は LLM が物語を捏造しうる。→ 末端ゲートは厳格・**経路を可視化**して人間が sanity check。
   中立を許す代わりに**出口の選択圧を上げる**（structural_depth ＋ hollow judge）。

---

## 実装メモ（別途）

- `src/` は本メモでは変更しない。実装時は **収集レイヤー（`collect.py` の bridge 展開）＋ θ_p 拘束**として追加し、
  `select_track_b` のスコア核（purpose_sim × mechanism_dist、各ゲート閾値）は**変更しない**（`spec.md` 禁則）。
- bybridge の選出ロジック変更に該当しうるため、本実装前に**仕様確認**。
