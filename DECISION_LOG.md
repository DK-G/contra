# DECISION LOG

contra の重要な設計判断を記録する。新しいエントリを先頭に追記する。

---

## 2026-06-09 — OSS探索 (byrepo) 結果に基づく機能導入：MCP・GloVe・agentmemory の採用決定

**決定**: `byrepo` 探索で発見した 3 つの OSS リポジトリから、以下の技術・設計思想を Contra に順次導入・統合することを決定。
1. **MCP サーバー化 (`microsoft/mcp-for-beginners` 参照)**: Contra パイプライン全体を MCP (Model Context Protocol) サーバー化し、外部の IDE エージェント等から直接「視座拡張ツール」として呼び出せる設計へと拡張する。
2. **意味・概念トポロジー距離の統合 (`stanfordnlp/GloVe` 参照)**: ドメイン間の意味的・認定的距離を定量化するため、GloVe 等の分散表現のアライメント思想を採用する（独自ビルドはせず既存ライブラリ経由でベクトル空間アライメントを実装）。
3. **エージェント持続メモリの導入 (`rohitg00/agentmemory` 参照)**: 1回限りの実行で終わらず、過去の探索・選別履歴やユーザーフィードバックを記憶し、周回探索を強化する「持続メモリ」を探索パイプラインへ統合する。

**根拠**:
- 各 OSS のライセンスを調査し、MIT (`mcp-for-beginners`) および Apache-2.0 (`GloVe`, `agentmemory`) ともに商用・私的利用が可能で、Contra にライブラリインポートまたは設計借用として組み込む上で法的に完全に安全であることを確認。
- 実装・検証時にクエリビルドの `NOT` 構文の最適化（バグ修正）および exclusion キーワードの調整を行い、byrepo にて信頼性スコア (Pillars) の精緻な出力とともにこれらのリポジトリを自動発見した。

---


## 2026-06-02 — LLM モデル/プロバイダ方針：マルチプロバイダ化＋品質ランは Claude Haiku 4.5

**決定**: `openai_client` をマルチプロバイダ化し（OpenAI Responses + Anthropic Messages、`--llm-model` でゼロコード切替）、運用は **既定 gpt-4o-mini（激安・探索用）／「本気の1本」は claude-haiku-4-5（最良コスパ）／プレミアムは claude-sonnet-4-6** とする。コード既定は gpt-4o-mini 据え置き（モデルは実行時フラグで選択）。

**根拠（A/B 実測, social 1ラン, ¥150/$, 価格要確認）**:

| モデル | ¥/run | 質 |
|---|---|---|
| gpt-4o-mini | ¥1.8 | 弱い（浅い写像・数値捏造気味） |
| **claude-haiku-4-5** | **¥24** | 優秀 |
| o4-mini | ¥45 | 優秀 |
| claude-sonnet-4-6 | ¥69 | 優秀（僅差で最上） |

- 強3モデル（Haiku/o4-mini/Sonnet）は全て目標品質（深い構造写像・操作化された検証可能仮説・破断点 caution）をクリア。spine 品質の天井は gpt-4o-mini の構造アブダクション限界であり、推論/上位モデルで解消するという R1 調査結論を実証。
- コスパは Haiku 4.5 が最良。1ラン別論文ゆえ強3モデルの質の優劣は統計分離不能（コスト順は信頼可）。

**確認した非結果 / 訂正**:
- prompt caching は両 Claude run で cached_input=0（system ブロックが Anthropic 最小キャッシュ閾値 ~1024tok 未満の可能性）。「caching でコスト相殺」仮説は不成立 → Claude コストは素の値。
- 副次バグ修正: main.py の `--struct-depth-gate default=0.30` が校正値 0.50 を上書きしていた（commit b693223 で定数連動に修正）。

**ローカルLLM却下**: RTX 3060 Ti / VRAM 8GB では、速く動く 7–8B は gpt-4o-mini 以下、効きうる 32B 推論distillは VRAM に乗らず CPU 退避で実用速度が出ない。質の天井対策にはならず却下。

**可逆性**: プロバイダ切替は実行時フラグ、選別ロジック不変。

---

## 2026-06-01 — Track B 生成3部の hollow 対策：転用読みの定石に基づく多段プロンプト化

**決定**: Track B の4部生成のうち②関連性・③仮説・④注意点を、「遠い論文を自テーマへ転用する読み」の確立手順（構造写像/LBD/bisociation/概念ブレンディング/知識ブローカリング/Reading-for-Relevance/情報採餌に共通の4ムーブ）に沿って**多段構造化**し、各部に**FORBIDリスト**を明記する。summary は実Abstract援用で充足済みのため変更しない。

**根拠**: bynote 調査（NotebookLM Deep Research 68ソース、ノート `85d1cd32`、一次資料 `docs/research/reading_for_transfer.md`）。A-1 品質評価で観測した hollow 症状（②カテゴリ言い換え/③"可能性がある"bloat/④定型caution）が、先行研究が明示的に禁止する失敗型と一致した。

**処方**:
1. 生成プロンプト: object-mapping → Shared Relational Structure 明示 → 変数付き candidate-inference 仮説 → 破断点 caution。各部に禁止例を明記。
2. judge ルーブリック（Structural Depth / Applicability / Constraint Adherence 各0-10）でカテゴリ一致を hollow 棄却（次段で校正）。
3. summary は不変。

**トレードオフ / 却下**: 質ゲートを厳しくすると飽和（0件）が増えるが、ユーザー方針「論文選定は重視しない・同一論文の再ピック禁止が効けば周回でカバー」と整合するため許容。プロンプトを勘で調整する案は却下し、定石調査を先行させた。

**可逆性**: プロンプト変更のみ。選別ロジック・データ構造は不変。

**関連**: A-1 評価でのロバストネス修正（commit `28bbecc`）・Abstract truncation 修正（commit `0264d04`）。
