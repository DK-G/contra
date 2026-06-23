# Connected Papers (connectedpapers.com) 調査レポート（contra への活用可否）

> 本ドキュメントは、論文の類似度グラフ可視化ツール Connected Papers を調査し、contra に取り込める
> 要素があるかを判定した記録。
> 調査手段: connectedpapers.com /about ＋ Web 調査。調査日: 2026-06-14。
> 対象: <https://www.connectedpapers.com/>（freemium SaaS）
> 関連: [`elicit_review.md`](elicit_review.md), [`okf_knowledge_catalog_review.md`](okf_knowledge_catalog_review.md)（可視化の節）

---

## 0. 結論（最重要）

1. **これまでで最も手法が噛み合う対象。中核アルゴリズム＝ contra の bybridge と同系統。**
   Connected Papers は **共引用（co-citation）＋書誌的結合（bibliographic coupling）** で論文間類似度を測る。
   このうち **bibliographic coupling（＝同じ過去文献を引く論文同士）は、bybridge の
   `_bridge_pool_from_seeds`（近傍シードの共有 referenced_works）とまさに同じ**。
   → contra の citation 2-hop が学術的に妥当な手法であることの裏づけになる。

2. **ただし目的は正反対（収束 vs 発散）。contra は同じエンジンを「逆回し」している。**
   Connected Papers はシードに**似た近傍クラスタ**を集める（収束）。contra は同じ結合シグナルを使いつつ
   **seed の L0 概念を除外して遠ドメインへ押し出す**（`collect_citation_candidates` の `concepts.id:!`）。
   → **「結合は保ち、近さは捨て、遠さを要求する」**のが contra。Connected Papers はその対照確認になる。

3. **実装に効く具体策が2つある。**
   - **(改善) bybridge に co-citation を追加検討**: 現状は bibliographic coupling 系のみ。Connected Papers は
     co-citation も併用 → 「シードと一緒に引用される論文」を bridge プールに足す余地。
   - **(可視化) force-directed グラフの視覚エンコードがそのまま流用可**: ノード色=出版年、サイズ=被引用数、
     エッジ太さ=結合強度。OKF レポート#3（Cytoscape 可視化）の具体的な設計図になる。

4. **検索先（コーパス）にはならない。** 基盤は Semantic Scholar、公開 API は実質なし（無料は月5グラフ）。

---

## 1. Connected Papers とは

- **正体**: シード論文を起点に**関連論文の類似度グラフ**を描く可視化ツール（freemium SaaS）。
- **アルゴリズム**: シード投入で **~50,000 論文**を走査し概念的リンクを探索。
  - **類似度 = co-citation（共に引用される）＋ bibliographic coupling（同じ過去文献を引く）**。
  - 引用・参考文献の重なりが大きい論文ほど関連が高いと推定。
- **可視化**: Force-Directed Graph。ノード=論文、**色=出版年（新しいほど濃い）/ サイズ=被引用数 /
  エッジ太さ=類似度の強さ**。似た論文は引き寄せ、遠い論文は反発。
- **コーパス**: Semantic Scholar Paper Corpus（ODC-BY）。
- **API/価格**: 公開 API は実質なし。無料=月5グラフ、Academic $3–5/月、Business $10–15/月。

---

## 2. contra への活用評価（3用途の枠組み）

### 2-1. 発見コーパス（検索の走らせ先）
- **❌ 不要**。Semantic Scholar 上の SaaS で公開 API なし。母集団としては OpenAlex 直叩きで足りる。

### 2-2. 手法 / インフラ層 ← 本命

**(A) bybridge の方法論的裏づけ＋拡張 … ★★★**
- contra の `collect_citation_candidates` は「近傍シードの共有参照（bridge）を経由し、seed の L0 概念を
  持たない遠ドメイン論文を拾う」。これは **bibliographic coupling を遠ドメイン方向に使う**もの。
  Connected Papers が同じ結合指標を産業的に使っている事実は、**bybridge の妥当性の外部裏づけ**。
- **拡張余地**: Connected Papers は **co-citation も併用**。bybridge は現状 referenced_works（coupling）中心
  なので、「**シードと共に引用される論文**（co-citation）」を bridge プールに加える実験が考えられる。
  ただし co-citation は近傍寄りに引っ張る傾向 → **遠ドメイン化のための L0 除外ゲートは必須**。
  （`spec.md` 禁則: bybridge の選出ロジック変更は要確認 → これは**提案レベル**に留める。）

**(B) 可視化の設計図 … ★★**
- OKF レポート#3 / archive レポートで触れた「contra の bridge をグラフ表示する」案に、
  **そのまま使える視覚エンコード**を提供: ノード色=年、サイズ=被引用、エッジ太さ=結合強度、force-directed。
- contra 流に拡張: **ノード色を「ドメイン距離（近=灰／遠=濃）」**に変えれば、
  「遠いのに結合している＝セレンディピティ候補」が一目で立つ。Connected Papers の "似たものを中央に集める"
  レイアウトを、contra は "遠いのに繋がるものを際立たせる" に**意味反転**して使う。

### 2-3. ポジショニング上の示唆
Connected Papers は **「同じ引用グラフ手法でも、目的関数次第で正反対の道具になる」**ことを示す好例。
- Connected Papers: coupling を**類似発見**に使う（近傍探索）
- contra/bybridge: coupling を**遠隔接続**に使う（L0 除外で far-domain 抽出）
→ contra の独自性は「アルゴリズム」ではなく「**何を遠ざけ何を要求するかという目的設定**」にあることを再確認できる。

---

## 3. フロー別まとめ

| フロー | coupling 手法 | co-citation 追加(提案) | 可視化エンコード |
|---|---|---|---|
| bybridge | ★★★（妥当性裏づけ） | ★★（要確認の拡張案） | ★★ |
| byserendipity | ★（候補拡張の発想） | ★ | ★★ |
| byrepo / bynote | — | — | ★（グラフ提示の流用） |

---

## 4. 制約整合・推奨

- **stdlib のみ**: co-citation も OpenAlex の引用データで取得可（HTTP+JSON）。可視化 HTML は CDN（依存ゼロ）。
- **`spec.md` 禁則**: bybridge の選出ロジック/閾値変更は要確認 → co-citation 追加は**PoC・提案**に留め、
  本実装前に仕様確認。`select_track_b` の構造判定には触れない。
- **推奨アクション**:
  1. **可視化の設計図を採用**（OKF#3 のビューア試作に Connected Papers の視覚エンコードを流用、ただし
     ノード色をドメイン距離に意味反転）。最も低リスク・高表現力。
  2. **co-citation を bridge プールに足す PoC**（要仕様確認）。遠ドメイン候補の取りこぼし低減を検証。

---

## 5. 結論の一言

Connected Papers は **「contra の bybridge を収束方向に回した双子」**。コーパスとしては不要だが、
**bybridge の方法論を裏づけ、co-citation 拡張と可視化設計図という具体的な実装ヒントをくれる**、
これまでで最も技術的に有用な対象。contra の核は同じ引用グラフを**逆回しする目的設定**にある、と再確認できた。

---

## 付記: 一次情報

- Connected Papers の仕組み（co-citation + bibliographic coupling / force-directed / Semantic Scholar）:
  <https://www.connectedpapers.com/about>
- 文献マッピング比較（Connected Papers / Inciteful / Litmaps）: Aaron Tay, Medium
