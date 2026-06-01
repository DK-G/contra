# 「遠い論文を自テーマへ転用する読み方」の体系化とプロンプト設計

> bynote 調査（NotebookLM Deep Research、68ソース、ノート `Serendipity Conditions for Contra` 85d1cd32、2026-06-01）。
> 目的: contra の生成3部（②関連性 / ③役立つ仮説 / ④注意点）が hollow になる問題を、
> 「論文を"自テーマに役立つ点はないか"と読む行為」の確立された手順と、それをLLMに行わせるプロンプト工学から再設計する。

## A. この読み方は何と呼ばれ、どう手順化されているか

| 枠組み | コアな動き | (a) 構造対応の作り方 | (b) 転用仮説の作り方 | (c) 転用が壊れる境界 |
|---|---|---|---|---|
| **構造写像/Design-by-Analogy** (Gentner) | 表層属性を捨て**関係構造**を整列 | object/relationに分解→"mere appearance"(液体である等)を捨て**1対1の関係写像**(camera diaphragm→eye iris) | **structural completion**: baseの因果述語をtargetへ持ち越す(機構をtarget目的へ輸入) | **systematicity欠如**(高次因果でなく孤立事実)、1対1/parallel connectivity違反 |
| **文献ベース発見 LBD** (Swanson ABC) | 分断した2文献を繋ぐ**中間概念B**を発見 | A・Cから用語抽出し交差、外れ値文献を探索、A↔Cが直接共引用しないこと | **推移的三段論法** A→B, B→C ⟹ A→C(魚油→血液粘度→Raynaud) | Bが**意味の偶然一致**(機構でなく表層キーワード)、A→Cが既知=新規性なし |
| **bisociation** (Koestler) | **両立しにくい2つの参照枠**で同時に見る | "out-of-plane"な橋渡しリンク、cross-domain埋め込みの関係ベクトル整列 | ベクトル類推(A1−A2≈C1−X)でXの振る舞いを予測 | 2領域が本当は非両立でない=単なる連想に堕ちる、洞察が非実行的 |
| **概念ブレンディング** (Fauconnier&Turner) | 2入力空間の要素を**融合**し創発 | 対応物をgeneric space(共通抽象構造)へ写像 | blended spaceへ射影し**創発特性**を持つ新概念(surgeon is a butcher) | 要素が非両立で安定融合不能=認知的不整合 |
| **知識ブローカリング/境界横断** (Carlile, Hargadon) | 構造的空隙を跨ぎ transfer→translate→transform | 両コミュニティへ没入し、source既存実践とtarget未解決問題の類推を探す | **translation work**: 共通語彙へ再framingし、組換え実践がtarget課題を解くと仮説化 | 認知的距離が過大、ブローカーの正当性欠如、政治/文化的不整合=翻訳失敗 |
| **道具的/関連性理論的読み** | 遠いテキストを**斜め読みし手がかりを収穫** | 深い理解を迂回し専門語彙・機構名・機関を"glean" | 収穫した専門語彙を検索クエリへ注入し隠れた文献群を開く | 読み負荷/jargon密度で抽出前に圧倒、収穫語がtoo specificで交差しない |
| **情報採餌/情報遭遇** (Erdelez, Pirolli) | 別目的の探索中に**偶然有用情報を発見** | "information scent"(snippet等の予期せぬ刺激)が背景問題への関連を喚起 | 暗黙のコスト便益仮説: 適用価値>抽出コストなら捕獲・適用 | 抽出/適応コストが価値に対し過大、認知過負荷で刺激を捕獲できない |

### 全枠組みに共通する4つの普遍的ムーブ
1. **脱文脈化（背骨の抽象化）**: 表層属性・jargon・無関係詳細を剥がし、核の機能的/関係的/因果構造(generic space, A-B-C triplet)を取り出す。
2. **境界越え整列（橋を架ける）**: 抽象構造とtarget問題を強制写像（数理=ベクトル/Jaccard、構造=1対1述語、社会=翻訳語彙）。
3. **組換えと推論（仮説生成）**: 整列したからこそ source の機構/創発特性/未観測リンクを target へ**falsifiable な candidate inference** として射影。
4. **制約チェック（ノイズのゲート）**: systematicity(因果深度)・認知的距離(本当に新規か)・実装可能性で hollow を能動的に棄却してから受理。

## B. LLMに hollow なく行わせるプロンプト工学（contra 3部に直結）

### ② RELATIONSHIP（構造対応）
- **抽出ステップ**: (1) target/source 双方の Purpose と Mechanism を独立抽出 (2) source の object と高次因果関係(A generates B, C mitigates D)を同定 (3) **機能役割のみ**に基づく1対1写像。
- **指示文**: 「両者の object と関係構造を抽出し、**機能で写像せよ。表層類似で写像するな**（'delivers payload'は可、'is liquid'は不可）。写像後に保存された因果/機構＝'Shared Relational Structure'を明示せよ。」
- **禁止**: 表層・属性一致（"both involve machine learning"/"both are networks"）、many-to-one写像。
- **ルーブリック（Structural Depth 0-10、judge gate）**: 0-2=表層/語彙依存の vague、3-6=個別objectは写像できるが**systematicity欠如**、7-9=因果機構を整列、10=完全な1対1 parallel connectivity。

### ③ USEFULNESS HYPOTHESIS（具体的・falsifiable な転用）
- **抽出ステップ**: (1) 写像した機構を target の目的の空隙へ輸入(candidate inference) (2) 独立変数/従属変数を同定 (3) 二値・経験的に検証可能な文へ整形。
- **指示文**: 「Shared Relational Structure に基づき、source機構を target へ適用する**新規でテスト可能な仮説**を生成。二値検証可能で、**転用する具体機構**と**測定可能な変数/統計関係**を明示。'Statement / Causal Chain / Evidence Summary'で出力。」
- **禁止**: 非検証可能（target に変数/道具がない）、bloat/buzzword（"will enhance performance"）、source に無い能力の hallucination、**カテゴリ一般化**（"Algorithm X family helps Biology Y"。論文固有の手法であること）。
- **ルーブリック（Applicability 0-10）**: 0-2=助けにならない/非検証、3-6=機構は妥当だが指標が曖昧・自明、7-9=測定可能変数で具体機構を直接転用、10=falsifiable な因果連鎖で解を可能にする。

### ④ CAUTION（具体的境界条件）
- **抽出ステップ**: (1) source機構の動作前提・失敗モード・制約(データ型/スケール/温度域)を抽出 (2) target現実へ投影 (3) どの1対1写像/関係が無効化するか特定。
- **指示文**: 「この類推転用が壊れる境界条件を特定せよ。source機構の運用制約/前提を抽出し target に照らし、**どこで1対1写像が破断**するか（物理/論理/データ制約違反）を正確に述べよ。」
- **禁止**: 一般的限界の定型文（"requires more data" / "needs empirical validation" / 文化差・母集団差の紋切り型）、target制約を魔法的に克服できるという hallucination。
- **ルーブリック（Constraint Adherence 0-10）**: 0-2=境界未特定/定型限界、3-6=制約はあるが表層差・因果説明なし、7-9=具体制約(閾値/欠落変数)を明示、10=破断する関係述語/object写像をピンポイント特定。

## C. contra の現状ギャップへの対応（観測 → 処方）

A-1 評価で出た hollow の症状は、上記の **FORBIDDEN パターンそのもの**だった:
- ②「MMORPGの動機が継続を促すのと同様にパズルの動機も継続率に影響」= 禁止された**カテゴリ言い換え/mere appearance**。現プロンプトは「構造の一致」を求めるが、object 1対1写像＋Shared Relational Structure の**明示出力ステップが無く**、"both involve X" を**禁止していない**。
- ③「動機が重要な要因となる可能性」= 禁止された **bloat/非検証**。Statement/Causal Chain/変数の構造化と、カテゴリ一般化の禁止が無い。
- ④「年齢/文化的背景が違うため適用に注意」= 禁止された**定型 caution**。source制約抽出と破断点特定が無い。
- judge(R2) は structural_depth を 0-10 で評価済みだが、現ゲート閾値が低く「3-6帯(systematicity欠如)」を通している → カテゴリ一致が素通り。

### 処方（実装方針）
1. **生成プロンプトを多段構造化**: object-mapping → Shared Relational Structure 明示 → candidate-inference 仮説(変数付き) → 破断点 caution。各部に**FORBIDリスト**を明記。
2. **judge ルーブリックを A/B の0-10基準に合わせて校正**し、カテゴリ一致(<7目安)を hollow として弾く（質優先＝飽和増は周回で許容する方針と整合）。
3. summary は実Abstract援用で既に充足（truncation修正済み）。手を入れない。

## 主要ソース（ノート内）
構造写像/SME、LBD(Swanson)、bisociation埋め込み、概念ブレンディング、知識ブローカリング(Carlile/Hargadon)、Reading For Relevance、情報採餌(Pirolli/Erdelez)、LLM-as-judge ルーブリック(Structural Depth/Applicability)、Unlocking LLM Creativity(AR)、CAM analogy mining 他。ノート `85d1cd32-e992-46be-b6e0-e78bde3c45b7` で `nlm notebook query` により再利用可能。
