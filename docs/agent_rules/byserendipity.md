---
name: byserendipity
description: contra の Track B を使って遠いが構造的に接続する論文を選別・生成する named flow。委譲（キー無し・追加課金ゼロ）が既定。
---

# Byserendipity

この文書は contra における **Track B contrarian / serendipity flow** の運用定義とする。
会話では `byserendipity で回して` または `Track B は byserendipity で` の形で呼び出す。

## Purpose

- 一見無関係だが構造的に接続しうる遠い論文を見つける
- 近接や anomaly を避け、**遠いが効く発想** を抽出する
- contra の中核である Track B を独立フローとして明示する

## Invocation

次のような明示依頼を受けたらこの flow を優先する。

- `byserendipity`
- `byserendipity で回して`
- `Track B は byserendipity で`
- `遠い接続だけ見たい`
- `contrarian 側を回して`
- `構造類推の方で進めて`

## 実行モード（委譲が既定）

**委譲（キー無し・追加課金ゼロ）を既定とする。** contra 自身は LLM を呼ばず、OpenAlex 収集と決定論ゲートだけを回す。標的化抽象・採点・プローズ執筆という LLM 推論は、この flow を実行している **呼び出し側エージェント（Claude）が自分の推論で代行**する。これによりメータ API キーが不要になり、何度回しても従量課金が発生しない。

自己完結（メータ）モード（`byserendipity_discover` を `raw_only` 無しで呼ぶ＝contra が OpenAI/Anthropic を呼ぶ）は、エージェントが介在しない無人バッチ等でのみ使う。

## Workflow（委譲キー無しループ）

エージェント自身が 1・3・5 を推論で担い、contra MCP は 2・4 の決定論部分だけを担う。

1. **（エージェント）標的化抽象**: テーマの核となる関係構造を **ドメイン中立な機能語**で再記述する。構造を規定する制約（閾値・フィードバック・律速・分岐など）は残し、テーマの表層トピック語は外す。抽象は深くしすぎない（〜3階層／"system"・"process" 級まで一般化しない）。続けて、その構造が現れうる **異なる分野の facet を最大3つ**選び、各 facet にその分野の語彙で書いた **〜80語の仮想アブストラクト（HyDE）** を生成する。
   - **生成・観測過程の棚卸し（facet を選ぶ前に）**: テーマのデータが「どう作られ、どう観測されたか」を次の4問に1行ずつ答える。分からなければ「不明」と書き、推測で埋めない。
     1. 入力は誰・何が作ったか（人の判断・制御器や方策・スケジュール・別のモデル）。それは出力や目的変数を見て反応しているか（閉ループか）。
     2. 観測が「ある／ない」「いつ」を決めているのは何か。それは目的変数や潜在状態に依存しうるか（通院・受験・報告・検出の有無）。
     3. 観測値は何の合成か（回数 × 大きさ・多数の事象の和・閾値を越えた分だけ記録・丸めや量子化・打ち切り）。
     4. ラベル・正解はどう作られたか（誰がどの基準で付けたか。学習用と評価用で作り方が違うか）。
   - **生成過程 facet**: 3つの facet のうち **1つは、棚卸しで最も効いていそうな生成・観測過程を研究している分野**に割り当てる。pseudo_abstract はその分野の語彙で「観測・生成の仕組みそのものをモデル化して推定を正す」研究として書く。残りの facet は従来どおり、予測・説明の対象の関係構造で選ぶ。棚卸しの4問がすべて「不明」か自明（単純な計測で、目的変数への依存も合成も無い）なら省略してよい。省略したらその理由を出力に1行残す。
   - 生成過程 facet を立てたら、棚卸しの要点を **`concern` に1〜2文で書く**（例: 「観測の有無が重症度に依存している可能性がある」）。手順3の採点と接地（theme_quote）がこの文を参照できるようにするため。
   - 根拠: 過去コンペ4題の後知恵テスト（2026-09-27）では、勝因の3題が生成・観測過程にあったのに、呼び手の facet は全題で対象の振る舞いの類推に寄った。seihai の採用台帳でも、採用された文献の多くは測定・観測の研究だった（DECISION_LOG 2026-09-27「生成・観測過程 facet」）。
2. **（contra MCP・キー無し）生候補収集**: `mcp__contra__byserendipity_discover` を `raw_only=true` で呼び、`structure`（手順1の構造）と `facets`（`[{domain, pseudo_abstract}]`）を渡す。contra が OpenAlex `search.semantic`（埋め込み検索）で各 facet を引き、ホームドメインをクライアント側で除外し、**生候補の materials（id/title/abstract/concepts/...）を JSON で返す**。`search.semantic` は実験的エンドポイントで一部 facet が 5xx になることがあるが、その facet はスキップされ残りが返る。
3. **（エージェント）採点**: 返ってきた各候補を SOLVENT（purpose × mechanism）で自分の推論で採点する。各候補に次を付与:
   - `purpose_sim`（0–1。問題の因果構造の一致度。**< 0.20 は anomaly として contra 側で棄却**される。none≈0.10 / partial≈0.45 / strong≈0.70 が目安）
   - `mechanism_dist`（0–1。機構の遠さ。別分野・別手法ほど高い）
   - `structural_depth`（0–1。Gentner 構造対応の深さ。**< 0.50 は hollow として棄却**される）
   - `has_causal_pm`（真偽。明示的な因果 Purpose→Mechanism があるか）
   - `connection_label`（接続点チップ・関係/過程を表す）と `serendipity_rationale`（論文固有の発見を埋め込んだ変数対応の1文）
   - **生成過程 facet から来た候補**（materials の `facet` 欄で分かる）の `purpose_sim` は、`concern` に書いた生成・観測過程との因果構造の一致で付け、`theme_quote` もその文から取る。予測対象の振る舞いと一致しないことを理由に下げない。ゲートの閾値は変えない（床と percentile はそのまま効く）。
4. **（contra MCP・キー無し）post-gate と出力**: 採点済み候補（contra が配った materials を echo ＋ 上記スコア）を `mcp__contra__delegate_finalize` に渡す。contra が決定論で硬い床（anomaly / near-domain cap / serendipity / hollow / percentile / output_floor / fallback / M3）を再適用し、Track B markdown を返す。
   - **採点した候補は全件提出する。** percentile ゲートの閾値は「提出した候補（anomaly/hollow 除外後）の上位30%点」で、提出が 6 件以下だと最高点の 1 件しか通らない（通過数が質でなく件数で決まる・F-15）。良さそうな数件に絞って出すと、ゲートが上位 1 件の選択に変わる。
   - 出力に載せたい候補は materials を全欄 echo する（接地検証と描画に要る）。それ以外は **`id` と点数だけでよい**。点数だけの候補も分位の母数に入り、出力に載らなければ警告は 1 行にまとめられる。点数だけの候補は出力枠に入らない（材料付きの候補が 1 件も無いときを除く）。ゲートを全部通った点数だけの候補は `not_selected(no_material)` として名指しされるので、読みたければ材料付きで再投する。
   - 出力は `count` で上限が掛かる。落選内訳の `not_selected(count=…)` は、ゲートを全部通ったが count で切れた候補（点数だけの候補でも1件ずつ名指しされる）なので、出力と同じ重みで読む。post-gate は決定論的検証であって採否の最終権限ではない。
5. **（エージェント）プローズ仕上げ**: 必要なら4部構成（概要 / 関連性 / 仮説 / 注意点）をエージェントが磨く。仮説は論文固有の発見に基づき、テーマ側の具体変数に対応づける（一般化・捏造数値は禁止）。

**MCP が使えない場合のみ**、`D:\dev\repos\contra` で `python -m src.cli.main`（`--gen-mode structured` ならキー無し／`--gen-mode llm` はメータ）にフォールバックする。

## Inputs

- `ThemeInput`（theme_overview / goal / why_problem / scope_field / keywords ...）
- `structure`・`facets`（委譲時にエージェントが生成）
- `track_b_count` / `output_floor`（post-gate 段で使用）

## Output Expectations

- 生成・観測過程の棚卸し（4問の答え）と、生成過程 facet の分野（省略したならその理由）
- Track B section に次を含める
  - 接続点ラベル
  - serendipity score
  - distance / structure score
  - 4部構成

## Non Goals

- 近接論文の網羅
- 実装のしやすさ評価
- GitHub repository の実用性評価
