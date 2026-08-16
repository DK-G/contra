# OKF / Google knowledge-catalog 調査レポート（contra への活用可否）

> 本ドキュメントは、Google の `knowledge-catalog` リポジトリと OKF (Open Knowledge Format) を調査し、
> contra に取り込める要素があるかを判定した記録である。
> 調査手段: GitHub リポジトリの直接確認（SPEC.md / README / ソースツリー）＋ contra 側コード読解。調査日: 2026-06-14。
> 対象: <https://github.com/GoogleCloudPlatform/knowledge-catalog>（Apache 2.0 / *Not an official Google product*）
> 関連: [`byrepo_improvement_strategy.md`](../../research/byrepo_improvement_strategy.md), [`serendipity_conditions.md`](../../research/serendipity_conditions.md)

---

## 0. 結論（最重要）

1. **OKF は「フォーマットの提唱」であり、検索できる公開コーパスではない。**
   OpenAlex（2.5億論文）や GitHub Search（全リポジトリ）は **クエリできる母集団** だが、
   OKF は **Markdown + YAML frontmatter の書き方の約束事** にすぎない。世界中の OKF バンドルを
   横断検索できる索引・レジストリは存在しない。→ **contra の「検索の走らせ先」を増やす用途には使えない（新しい外部ヒットを供給しない）。**

2. **ただしリポジトリ本体には「集めて繋げる」実装が同梱されている。**
   SPEC.md だけが独り歩きしているが、`okf/` には仕様＋**動くリファレンス実装**（収集エージェント＋
   Cytoscape 可視化）まで揃っている。

3. **contra に効くのは「母集団」ではなく「手法」と「記憶層」。**
   - 手法 = enrichment_agent の **Web Pass（LLM を seed URL クローラーとして使い1ヒットを肉付けする）**。
   - 記憶層 = 出力を **OKF バンドル化して自前の蓄積メモリ＝ローカル検索先** にする（`spec.md` の将来構想
     「agentmemory / 探索履歴の永続メモリ」と直結）。
   いずれも **stdlib 原則・外部依存禁止と両立可能**で、`models.py` やスコア設計には触れない外形/収集レイヤーの話。

---

## 1. OKF (Open Knowledge Format) とは

- **正体**: 知識（メタデータ・コンテキスト・キュレーションされた知見）を AI エージェントが読み書きできる
  普遍フォーマットの仕様（v0.1, draft）。
- **動機**: AI 向け知識表現がツール/組織ごとに独自フォーマットへ分裂しつつある。これを
  human-readable / agent-parseable / version-controllable / portable な1形式に統一する。
- **データモデル**: 「Markdown ファイルのディレクトリツリー（Bundle）」。
  - 各 `.md` = 1 概念。**YAML frontmatter + Markdown 本文**。
  - frontmatter 必須は `type`（"BigQuery Table" / "Playbook" 等）のみ。推奨は `title` / `description` /
    `resource`(正規 URI) / `tags` / `timestamp`。
  - 予約ファイル名: `index.md`（目次＝progressive disclosure）、`log.md`（時系列の更新履歴）。
  - 概念間リンクは通常の Markdown リンク（bundle 相対パス推奨）。外部出典は "Citations" 見出し下に番号付き参照。
- **設計思想**: **「壊れていることに寛容」**。`type` が非空でパースできれば適合。optional 欠落・未知 type・
  リンク切れを許容する。厳格スキーマ DB ではなく「ゆるく交換可能」を優先。
- **たとえ**: Markdown 版の OpenAPI / JSON Schema。共通語を決めるだけで、動かすエンジンは各自で用意する
  （あるいは普通のファイルシステム＋git で済ませる）。

---

## 2. リポジトリ全体像

正体は単なるフォーマット提唱ではなく「AI-powered data catalog / メタデータ管理プラットフォーム」。
データ（構造化・非構造化）の知識グラフを作り AI エージェントに意味・業務文脈を与える、という触れ込み。

### トップ階層（4ディレクトリ）

| ディレクトリ | 中身 |
|---|---|
| `okf/` | OKF の仕様 **＋ リファレンス実装一式**（本命） |
| `agents/` | `enrichment` / `mdcode` の2エージェント |
| `toolbox/` | `enrichment`（メタデータ生成・保守）/ `mdcode`（**メタデータをソースコードとして管理し同期**） |
| `samples/` | バンドル再現用のレシピ＆コマンド集 |

### `okf/` の中身（仕様だけではない）

- `SPEC.md` … OKF v0.1 仕様
- `bundles/` … **完成済みサンプルバンドル3つ**（GA4 / Stack Overflow / Bitcoin）。可視化 HTML 付き
- `src/enrichment_agent/` … **動く Python 実装**（Google ADK + Gemini）
- `samples/`, `tests/`, `pyproject.toml`

### リファレンス実装 `enrichment_agent`（CLI 2コマンド）

**① `enrich`（集める・書く側）**
```
python -m enrichment_agent enrich --source bq --dataset <proj>.<dataset> \
    --web-seed-file seeds.txt --out ./bundles/<name>
```
2パスで OKF バンドルを自動生成:
- **BQ Pass**: BigQuery のメタデータから概念ごとに1 `.md` を生成
- **Web Pass**: **Gemini をクローラーとして使い**、seed URL を辿って既存概念を肉付け or 参照ドキュメント
  を追加（**ページ上限・ドメインフィルタ**の暴走防止つき）

内部モジュール `bundle/`: `document.py`（frontmatter+本文パース）/ `index.py`（index 構築）/
`paths.py`（bundle 相対パス＝cross-link 解釈）/ `synthesizer.py`（概念の集約）。`sources/` に
BigQuery コネクタ（プラガブル）。

**② `visualize`（繋げて見せる側）**
```
python -m enrichment_agent visualize --bundle ./bundles/<name>
```
`viewer/generator.py`＋templates/static が **自己完結 HTML を1枚生成**:
- **Cytoscape.js の force-directed グラフ**（概念=ノード、**cross-link=エッジ**）
- 詳細パネル（frontmatter＋marked.js でレンダリングした本文）
- **Backlinks（"Cited by" 逆引き）**、検索、type フィルタ、複数レイアウト
- Cytoscape / marked は CDN 読み込み → 出力 HTML 単体で動作

→ 「フォーマットに沿ったファイルを蒐集して繋げる」ツールは `visualize` がドンピシャで実装済み。

---

## 3. 「決まった検索の走らせ先」にできるか（収集ソース観点）

| ソース | 中身 | contra から見た役割 |
|---|---|---|
| OpenAlex | 2.5億論文を**クエリできる公開コーパス** | 検索先になる ✅（byserendipity / bybridge） |
| GitHub Search | 全リポジトリを**クエリできる公開コーパス** | 検索先になる ✅（byrepo） |
| **OKF / knowledge-catalog** | **フォーマット＋バンドル生成ツール** | **検索できる母集団が存在しない ❌** |

存在するバンドルは **サンプル3つ＋自分で生成した分だけ**。背後の "Knowledge Catalog" 製品（Google Cloud の
メタデータカタログ系）も「**自社の**データ資産」を対象にするもので、外から叩ける公開検索コーパスではない。
→ **byrepo の隣にもう1つ検索先を足して新規ヒットを拾う、という用途には該当しない。**

「外部の新規ヒット源」を増やしたいなら、OKF ではなく別の**クエリできるコーパス**を足す話
（GitHub 検索戦略の多様化、papers-with-code / Hugging Face / Software Heritage など）。

---

## 4. contra への取り込み候補（手法と記憶層）

### アイデアA: Web Pass（LLM クローラーで seed URL を辿り1ヒットを肉付け）

現状フローの収集実装（確認済み）:
- **byrepo** (`pipeline/git_collect.py`): GitHub Search にクエリ1本（最初の include 語＋短い goal＋
  `demo in:readme`）→ README をデコード → 4本柱 Reliability Score。**README 一枚（`[:2000]`）しか見ていない**。
- **byserendipity** (`pipeline/collect.py`): LLM が遠ドメインクエリ生成 → OpenAlex 検索 → **abstract のみ**の
  Work で purpose_sim × mechanism_dist を判定。
- **bybridge** (`pipeline/collect.py: collect_citation_candidates`): OpenAlex の**引用グラフ2-hop**
  （`cites:bridges` ＋ seed の L0 概念を除外）。**`raw_only`＝LLM キー不要**の軽量モードあり。発見は純粋に構造ベース。
- **bynote** (`mcp_server.py: _execute_bynote`): メモを Purpose/Mechanism に分解し類推ドメインと bridge 問いを
  提示する **LLM 推論ヘルパー**。外部収集なし。

| フロー | 価値 | 理由 |
|---|---|---|
| byrepo | ★★★ 高 | README 一枚は薄い。docs サイト/論文/関連 repo を辿れば材料が一気に増える。Google 依存ゼロ |
| byserendipity | ★★☆ 中（条件付き） | abstract だけだと mechanism_dist 判定が薄い。**OA 全文/ランディングを辿れば補強**できるが、論文は paywall＋ノイズで効率が落ちる。主レバーはクエリ生成側。→「abstract が短すぎる / OA がある時だけ」条件付きで入れる |
| bybridge | ★☆☆ 低 | 発見が引用グラフベースなのでクロールは**新しい bridge を増やさない**。判定補強にしか効かず、しかも **`raw_only`（LLM 不要）契約を壊す**。収集段には入れない |
| bynote | — | 外部収集なし（「クロール先ドメインの提案役」として周辺利用は可） |

enrichment_agent から学ぶべき要点: **ページ上限・ドメインフィルタによる暴走防止**を最初から組み込むこと。

### アイデアB: 出力を OKF バンドル化し「自前の蓄積メモリ＝ローカル検索先」にする

特定フローの機能ではなく **4フロー共通の永続層**。`spec.md` 将来構想「agentmemory / 探索履歴の永続メモリ」
そのもの。前述「OKF を検索先にする」が成立する唯一かつ全フロー横断の形。

| フロー | 価値 | 理由 |
|---|---|---|
| byserendipity | ★★★ 高 | 「どの遠ドメイン/クエリが良い bridge を生んだか」の run 横断記憶。既存 `history.py`＋M3 飽和検知の自然な拡張 |
| bybridge | ★★★ 高 | 「過去に越えた bridge 参照」を覚えれば 2-hop 再走査の**重複排除**になり交差発見が効率化 |
| byrepo | ★★☆ 中 | 既出アンカー repo の記憶・重複回避 |
| bynote | ★★☆ 中 | 過去の分解・類推ドメインを供給し提案を厚くできる |

実装イメージ: 1 run = 1 OKF バンドル（論文/repo = concept `.md`、frontmatter に score・track・edge 種別、
`index.md` にテーマ目次、`log.md` に採用履歴）。さらに `visualize` を真似れば
**「論文=ノード、bridge=エッジ」で contra の対置をグラフ可視化**できる（出力 HTML は CDN 読み込みで依存ゼロ）。

---

## 5. 制約整合（contra の禁則との両立）

- **stdlib のみ / 外部依存禁止**: Web Pass は標準 HTTP＋既存 LLM クライアントで実装可。バンドルは `.md` 書き出し。
  可視化 HTML は CDN 読み込みで pip 依存ゼロ。→ いずれも原則に抵触しない。
- **`models.py` のデータクラス / `select_track_b` のスコア設計は不変更**: 本件はすべて
  **収集（source）レイヤーと出力（外形）レイヤー**の話で、判定ロジックの核には触れない。
- **OKF は v0.1 draft**: `type` 等の必須最小限だけに依存し、深くロックインしない。

---

## 6. 推奨アクション（優先順）

1. **byrepo に Web Pass の薄い移植** — README 内リンクを N 件まで辿って文脈追記（上限・ドメインフィルタつき）。
   最小実験で「拾える幅」の効果を検証。`git_collect.py` への追加オプションから着手。
2. **出力の OKF バンドル化＋自前メモリ化** — 全フロー横断・将来構想（永続メモリ）の前倒し。
   既存 `history.py` を OKF バンドル（`index.md` / `log.md`）へ一般化する形が自然。
3. （余力）**バンドル → Cytoscape 可視化ビューア**の試作 — 対置をグラフで提示。`okf/.../viewer` を参考実装にできる。

---

## 付記: 一次情報の所在（再確認用）

- 仕様: `okf/SPEC.md`（OKF v0.1）
- 実装: `okf/src/enrichment_agent/`（`enrich` / `visualize`、`bundle/` パーサ群、`sources/` コネクタ、`viewer/generator.py`）
- 例: `okf/bundles/`（GA4 / Stack Overflow / Bitcoin）
- 周辺ツール: `toolbox/mdcode`（メタデータ＝ソースコード管理、アイデアB の先行事例）
