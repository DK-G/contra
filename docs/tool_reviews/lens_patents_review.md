# Lens.org（および「特許」という新ジャンル）調査レポート（contra への活用可否）

> 一般論文サイト総覧 #10。Lens.org は学術＋**特許**の統合プラットフォーム。本稿は (1) Lens 自体の可否、
> (2) **特許という新ジャンルが contra の中核に効くか**、(3) 特許の無料 API 代替、を評価する。
> 調査手段: about.lens.org / docs.api.lens.org / PatentsView / Google Patents Public Data ＋ Web 調査。調査日: 2026-06-15。
> 対象: <https://www.lens.org/>
> 関連: [`openalex_review.md`](openalex_review.md), [`arxiv_review.md`](arxiv_review.md), [`../research/serendipity_conditions.md`](../research/serendipity_conditions.md)

---

## 0. 結論（最重要）

1. **Lens.org 自体は入口にしない（学術側は冗長・API は有料/申請制）。**
   Lens は学術 210M+（OpenAlex と重複）＋**特許 140M+**を無料 Web 提供するが、**API は有料**
   （プロ用途 $1,000–5,000/年、非商用/学術は申請制トライアル）。コスト最小方針に反し、入口に向かない。

2. **しかし「特許」という genre は、本総覧で arXiv 以来の最有力な新方向。**
   特許は **法的に機構の開示（enablement）が必須**＝**問題→解決（Purpose→Mechanism）が明示**された文書で、
   **全技術分野を横断**する。これは contra の中核 **serendipity = purpose_sim × mechanism_dist** と**構造的に一致**し、
   分野横断のアナロジー転用（TRIZ/類推的イノベーションの古典的源泉）に最適。**OpenAlex が持たない初の新ジャンル**。

3. **特許を採るなら入口は Lens ではなく無料の特許 API。**
   **PatentsView/USPTO（無料・キー不要、ただし現在 USPTO 移行で一時不安定）/ Google Patents Public Data
   （BigQuery、月1TB 無料、90M+・17 か国＋US 全文）/ EPO OPS（要登録・無料）**。CPC/IPC 分類を
   ドメイン距離信号に使える（arXiv カテゴリ・MeSH と同じ役）。

---

## 1. Lens.org とは

- **正体**: 非営利 Cambia の学術＋特許統合プラットフォーム。
- **規模**: 学術（非特許文献）210M+、**特許 140M+（全世界の法域）**、両者のリンク。
- **アクセス**: Web は個人/公益機関に無料。**API は有料**（$1,000–5,000/年）、非商用/学術は申請制トライアル。

---

## 2. contra への活用評価

### 2-1. Lens.org そのもの
- **学術側 = 冗長**（OpenAlex/CORE と重複）。**API = 有料/申請制**で導入摩擦・コスト。→ **入口として不採用**。

### 2-2. 「特許」genre の戦略的価値 ← 本稿の核心
- **機構の可読性が最高水準**: 特許は実施可能性（enablement）要件で**解決手段＝機構を明示**。arXiv 以上に
  「構造の骨格」が読める → 偽 bridge を弾きやすく **精度(precision)が高い**（README 示唆 #9 の極致）。
- **構造が contra そのもの**: 特許は **Problem（Purpose）→ Solution（Mechanism）** で記述。
  「分野は遠いが解決構造が一致する特許」は**最良のセレンディピティ候補**。`serendipity_conditions.md` の
  「遠さ × 接続点の本物さ」を、論文より明示的な形で満たす。
- **新ジャンル**: OpenAlex は特許を持たない。**初めて"母集団を本当に広げる"対象**（recall も precision も新規）。
- **分類**: **CPC/IPC**（特許分類）は精緻な技術タクソノミ → `concept_distance` 相当のドメイン距離に流用可。

### 2-3. 統合コスト（ドロップインではない）
- 特許は論文と**文書構造が別**（claims・法律文体、scholarly citation 2-hop が無い、引用は審査官引用）。
  → contra の既存パイプライン（OpenAlex concepts、citation bridge）は**そのまま適用できない**。
- 必要なのは **特許用の収集・距離（CPC/IPC）・Purpose/Mechanism 抽出**の小サブシステム。
  これは新トラック（例: "bypatent"）級の追加であり、**将来拡張**として位置づけるのが妥当。

---

## 3. フロー別まとめ（将来像）

| 観点 | 評価 |
|---|---|
| byserendipity に特許を混ぜる | ★★★（構造一致の宝庫・分野横断）だが**別パイプライン**が要る |
| distance 信号 | CPC/IPC を流用（★★） |
| 入口 | **PatentsView / Google Patents BigQuery / EPO OPS（無料）**。Lens API は不採用 |

---

## 4. 推奨アクション

1. **「特許トラック（bypatent）」を将来拡張候補として記録**: 最も強い新方向だが、文書構造が異なるため
   独立サブシステム（収集＋CPC/IPC 距離＋Purpose/Mechanism 抽出）が要る。優先度は中〜高（概念適合は高、実装は重い）。
2. **PoC するなら無料 API で**: PatentsView（復旧後）/ Google Patents Public Data（BigQuery 月1TB 無料）/ EPO OPS。
   **Lens API（有料）は使わない**。
3. **Lens.org 自体は不採用**（学術冗長・API 有料）。

---

## 5. 結論の一言

Lens.org は入口にしない（学術冗長・API 有料）が、**それが運ぶ「特許」は arXiv 以来の最有力な新方向**。
特許は **Purpose→Mechanism が明示され全分野を横断する**、contra のセレンディピティに理想的な genre。
ただし論文と構造が違うため**独立トラックの将来拡張**として、入口は**無料特許 API**で検討する。

---

## 付記: 一次情報

- Lens API（有料・申請制、特許 140M+）: <https://docs.api.lens.org/> / <https://about.lens.org/>
- PatentsView/USPTO（無料・キー不要、移行中）: <https://data.uspto.gov/apis/getting-started>
- Google Patents Public Data（BigQuery 月1TB 無料、90M+）: <https://cloud.google.com/blog/topics/public-datasets/google-patents-public-datasets-connecting-public-paid-and-private-patent-data>
