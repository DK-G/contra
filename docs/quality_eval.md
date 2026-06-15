# 品質評価ルーブリック（Phase 1 Done 判断）

> **改訂 2026-06-15**: 本ドキュメントは旧「20本レポート（100/200/200 比率・無関係4章）」前提の観点リストを、
> 2026-05-30 の contrarian 再定義（MVP = **Track B の良質な1本**・4部構成）に合わせて全面刷新したもの。
> 旧版のセクションバランス観点（100/200/200）は廃止。関係性・要約・注意点・再現性の観点は現行構成に引き継いだ。

本ドキュメントは Phase 1 の「Done」判断（spec.md §8 / roadmap #10）を**再現可能な手順とルーブリック**として定義する。
判断には**実 LLM API 認証情報＋人間の品質判断**が必要なため、本ファイルは「人間が実行して埋める」テンプレートとして機能する。

---

## 0. Done の定義（spec.md §8 より）

複数テーマで以下が安定して成立すること:

1. 「分野は遠いが関係構造が一致する」1本が安定して出力される（Gentner の Analogy）。
2. **Anomaly（無意味接続）**と**近接（マイオピア）**の双方が混入しない。
3. 「役に立つ可能性の仮説（usefulness_hypothesis）」が**論文固有の発見**に基づく（テーマの不安点の言い換えでない）。
4. 飽和テーマでは**弱い候補で水増しされず**、飽和ノート（M3）が出る。

---

## 1. 評価対象テーマ（最低4、推奨5）

`docs/research/` の Step 9 検証で使った 4 テーマ＋自己テーマ。analogy-rich / analogy-poor を意図的に混在させる。

| キー | 入力ファイル | 性質（事前想定） |
| :--- | :--- | :--- |
| energy | `data/samples/theme_energy.json` | analogy-rich（系統運用リスク） |
| casual | `data/samples/theme_casual_puzzle_retention.json` | analogy-rich（UX 継続率） |
| social | `data/samples/theme_social.json` | analogy-rich（情報拡散） |
| wind | `data/samples/theme_wind.json` | 測定テーマ（高度差×安定度） |
| contra | `data/samples/theme_contra_level_up.json` | 自己テーマ（構造類推そのもの） |

---

## 2. 実行手順（再現コマンド）

各テーマで「良質な1本」モード（`--single`）を実行する。本番品質は Haiku 4.5（DECISION_LOG 2026-06-02）。

```bash
# 要: 環境変数で LLM プロバイダの API キー（例: ANTHROPIC_API_KEY / OPENAI_API_KEY）
python -m src.cli.main \
  --input data/samples/theme_energy.json \
  --single \
  --llm-model claude-haiku-4-5 \
  --score-votes 3 \
  --out output/eval_energy
```

- `--single`: Track B の最良 1 本（Track A は省略）。本数は質ゲートの出力。
- `--score-votes 3`: R5 自己一貫性投票で borderline のフリップを抑える（コスト約3倍）。
- 飽和時は `output/eval_*/` に**飽和ノート**が出る（`--allow-weak-fallback` は**付けない**＝水増し禁止）。
- 全テーマ分を `--out` を変えて繰り返す。安定性（観点 §3-E）は同一テーマを 2〜3 回実行して確認。

---

## 3. 評価観点（1 本ごと）

出力 4 部（SUMMARY / RELATIONSHIP / HYPOTHESIS / CAUTION）を以下で採点する。各 0–2（0=NG, 1=可, 2=良）。

### A. RELATIONSHIP（遠いが構造一致か）
- 共有される**関係構造**（Purpose-Mechanism 写像）が明示され、表層カテゴリ一致でない（Gentner の literal vs analogy）。
- **NG**: 「どちらも〜を扱う」式のカテゴリ言い換え（hollow）。テーマと同分野の近接論文（マイオピア）。

### B. SUMMARY（要約の忠実性）
- 原著 Abstract の主張・方法・結果に忠実。過剰一般化・逆ニュアンスがない。
- **NG**: Abstract に無い数値の捏造（数値捏造ガード対象）。

### C. HYPOTHESIS（役に立つ仮説の固有性・操作可能性）
- 論文**固有の発見/メカニズム**を起点に、変数付きで**検証可能**な転用仮説になっている。
- **NG**: テーマの不安点の言い換え。「〜の可能性がある」だけの bloat。

### D. CAUTION（転用の破断点）
- 転用が**壊れる条件（破断点）**が具体的。前提・適用限界・反証観点がある。
- **NG**: 定型の一般注意。

### E. 再現性（同入力の安定性）
- 同一入力 2〜3 回で、選出傾向・4 部構成・出力形式が崩れない（borderline のフリップが `--score-votes` で収まる）。

---

## 4. Done 判定ルーブリック（記入式・テーマ横断）

各テーマで Done 条件 1–4 を判定する。判定値: ✅（成立）/ ⚠️（要再走）/ ❌（不成立）/ 🟡（飽和ノート・対象外）。

| テーマ | ①遠いが構造一致の1本 | ②Anomaly非混入 | ③近接(myopia)非混入 | ④仮説の論文固有性 | ⑤飽和時に水増しなし | 採点(A/B/C/D/E) | 選出論文・メモ |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- | :--- |
| energy   |  |  |  |  |  | _/_/_/_/_ |  |
| casual   |  |  |  |  |  | _/_/_/_/_ |  |
| social   |  |  |  |  |  | _/_/_/_/_ |  |
| wind     |  |  |  |  |  | _/_/_/_/_ |  |
| contra   |  |  |  |  |  | _/_/_/_/_ |  |

### Done 成立条件（全テーマ集計）
- 条件①〜④が**過半のテーマで ✅**、かつ ❌ が無い。
- 飽和テーマ（🟡）は条件①の対象外だが、条件⑤（飽和ノートが出て水増ししない）は**必須**。
- E（再現性）が全テーマで 1 以上（順序・形式が崩れない）。

---

## 5. 結果記録

- 実行ログ・選出論文・採点を本ファイル §4 の表に追記し、総評を以下に残す。
- 不成立があれば、原因（ゲート値・プロンプト・候補プールの遠さ）を切り分けて DECISION_LOG に起票し、roadmap #10 を継続。
- Done 成立時は spec.md §8「現在未解決」から Phase 1 Done 判断を外し、roadmap Phase 1.5（bybridge B-0 等）へ移行。

### 総評（記入欄）

> _（実行後に記入）_

---

## 注記

- 本評価は**実 LLM 生成**を伴うため、無認証/自律エージェント単独では実施不可。Codex automation / 人間が API キー在席環境で実行する。
- スコアリングロジック（serendipity = purpose_sim × mechanism_dist、hollow gate、M3 飽和）は実装済み。本評価はその**出力品質の人間確認**であり、コード変更を前提としない。
