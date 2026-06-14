# Consensus (consensus.app) 調査レポート（contra への活用可否）

> 本ドキュメントは、AI 研究検索エンジン Consensus を調査し、contra に取り込める要素があるかを判定した記録。
> 調査手段: consensus.app ブログ / ヘルプ＋ Web 調査。調査日: 2026-06-14。
> 対象: <https://consensus.app/>（商用 SaaS）
> 関連: [`elicit_review.md`](elicit_review.md)（同じ「SaaS over 既存コーパス」型）

---

## 0. 結論（最重要）

1. **Consensus は名前からして contra の対極＝「コンセンサス（合意）」を測るツール。**
   中核機能 **Consensus Meter** は Yes/No の問いに対し**文献の合意/不合意を集約・可視化**する。これは
   「主流派が何に同意しているか」を求める **収束（convergence）の極致**。一方 contra（= contrarian）は
   主流から**遠い構造類推の外れ値**を狙う。**名前のレベルで正反対。**

2. **検索先にもならない。** Consensus は **Semantic Scholar / OpenAlex ＋自前クロール**を基盤にした商用 SaaS
   （250M 論文）。**contra が既に持つ OpenAlex の再販**であり、新しい母集団を供給しない（Elicit と同型）。

3. **取り込む価値があるのは1点だけ: 再ランキング・パイプラインの考え方（弱）。**
   「1,500 件を粗選別 → 上位を大きいモデルで精密再ランク（recency / 被引用 / ジャーナル impact を加味）」は、
   contra の質ゲート / 自己一貫性投票（`--score-votes`）の設計参考になる程度。

---

## 1. Consensus とは

- **正体**: 学術研究向け AI 検索エンジン（商用 SaaS）。250M 論文超（一部は出版社ライセンス全文を含む）。
- **コーパス**: **Semantic Scholar データセット＋ OpenAlex ＋自前 Web クロール**。
- **検索**: ハイブリッド（BM25 キーワード ＋ AI 埋め込みセマンティック）→ 上位 1,500 件を**精密モデルで再ランク**
  （研究品質シグナル: recency / citation / journal impact）。
- **Consensus Meter**: 上位 ~20 件の結論を「支持/不支持」で分類し、**合意度を可視化**。方法論・新しさ・掲載誌・
  impact の注釈つき（Meter 2.0）。
- **規模/利用**: 170+ 大学図書館、1,000万人規模の利用。Deep Search モードあり。
- **API**: 製品 API は商用。基盤の S2AG API は別途（100 req / 5 min）。

---

## 2. contra への活用評価（3用途の枠組み）

### 2-1. 発見コーパス（検索の走らせ先）
- **❌ 不要**。基盤は Semantic Scholar / OpenAlex で、contra は OpenAlex を既に直接叩いている。
  Consensus 経由にすると商用 API・収束バイアス（人気/合意の高い論文を上位化）が乗るだけで、
  **contra が欲しい「遠い外れ値」を逆に押し下げる**。

### 2-2. 手法 / インフラ層
- **再ランキング・パイプライン … ★（弱）**: 「粗選別 → 精密モデルで上位だけ再評価」の二段構えは
  `classify.py` の percentile-gate ＋ hollow judge ＋ `--score-votes` に発想が近い。ただし Consensus は
  **precision（的中率）最適化**で、contra は **diversity/distance 最適化**。目的関数が逆なので**そのままは流用不可**、
  「二段評価でコストを集中配分する」骨格だけ参考になる。
- **Consensus Meter（合意/不合意分類） … ✗ 不適**: 「論文が主張を支持するか」を測る機構。contra の
  hollow judge（構造マッピングが本物か）や anomaly 棄却とは目的が違い、転用できない。

### 2-3. ポジショニング上の示唆（最も価値がある部分）
Consensus は **contra の存在理由を逆側から照らす最良の対照例**。

| | Consensus | contra |
|---|---|---|
| 目的 | 合意の確認（収束） | 遠い構造接続（発散） |
| 良い結果 | 主流・高被引用・最新 | 分野は遠いが構造一致 |
| バイアス | 人気/合意を強化 | 人気/近接を**棄却**（マイオピア排除） |

→ contra は「検索品質 = precision」という業界標準の評価軸を**採ってはいけない**ことを再確認できる。
（`serendipity_conditions.md`「98% は捨て札／狙えないものの代理変数＝距離×接続点の本物さ」と整合。）
なお contra の入力 `assumptions` に対して「文献の合意/不合意」を見る発想は一見魅力的だが、それは
**近傍ドメイン内の検証**であり、contra の中核（遠ドメイン構造類推）とは別物。混同しないこと。

---

## 3. フロー別まとめ

| フロー | 再ランク骨格(参考) | Consensus Meter | コーパス |
|---|---|---|---|
| 全フロー | ★（二段評価の発想） | ✗ | ❌（既存 OpenAlex で十分） |

実質、特定フローに足す実装提案はない。**学びは「やらないことの確認」**に集約される。

---

## 4. 制約整合・結論

- 新規実装の必要なし → 禁則との衝突もなし。
- **結論の一言**: Consensus は Elicit に続く2例目の「**収束型 SaaS over 既存コーパス**」で、しかも
  **名前ごと contra の対極**。実利は薄く、価値は **contra の同一性（contrarian = 反・合意）を最も鮮明に
  確認できる対照例**であること。収集ソースとしては OpenAlex 直叩きで足り、Consensus を挟む理由はない。

---

## 付記: 一次情報

- Consensus の仕組み / コーパス: <https://consensus.app/home/blog/how-consensus-works/>
- Consensus Meter: <https://help.consensus.app/en/articles/10069920-the-consensus-meter>
- 基盤 S2AG API: <https://api.semanticscholar.org/api-docs/>
