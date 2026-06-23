# SciSpace (scispace.com, 旧 Typeset.io) 調査レポート（contra への活用可否）

> 本ドキュメントは、AI 研究アシスタント SciSpace を調査し、contra に取り込める要素があるかを判定した記録。
> Elicit/Consensus と同型の「収束型 SaaS」のため、本稿は**重複を避け、固有の貢献点（生成＝翻訳段への示唆）**に絞る。
> 調査手段: scispace.com ヘルプ/製品ページ＋ Web 調査。調査日: 2026-06-14。
> 対象: <https://scispace.com/>（商用 SaaS）
> 関連: [`elicit_review.md`](elicit_review.md), [`../research/serendipity_conditions.md`](../research/serendipity_conditions.md)

---

## 0. 結論（最重要）

1. **Elicit/Consensus に続く3例目の「収束型 comprehension SaaS」。検索先にはならない。**
   280M+ 論文メタデータ＋50M+ OA 全文 PDF を持つが、機能は **Chat with PDF / 文献レビュー / AI Writer /
   Paraphraser**＝**理解・要約・執筆の高速化（収束）**。母集団は他ツールと同じ ~200–280M 帯で、
   商用 API。**contra の検索先にする価値はない。**

2. **唯一 contra に効く固有点: 「遠い論文を非専門家に翻訳して説明する」機能の設計。**
   SciSpace の看板 **Chat with PDF**（数式・専門用語・表を門外漢に噛み砕く）は、contra の
   **生成段（`generate.py`）と「役に立つ可能性の仮説」フィールド**が担うべき
   **「遠ドメインの発見をユーザーの慧眼(sagacity)が働く形へ翻訳する」**役割の、具体的な手本になる。
   （理論的根拠は [`serendipity_conditions.md`](../research/serendipity_conditions.md) §1: ユーザーは
   自分の専門には準備済みだが**遠いドメインには無防備** → ツールが翻訳して慧眼を肩代わりする。）

3. **その他の機能（Chat with Folder の「矛盾・ギャップ抽出」、50M OA 全文）は、既出の他ツールで代替可。**
   全文補強は IA Scholar（[`internet_archive_review.md`](internet_archive_review.md)）、横断合成は収束方向＝contra 中核と逆。

---

## 1. SciSpace とは

- **正体**: 研究ライフサイクル全体を支援する AI エコシステム（旧 Typeset.io の組版ツールから発展）。商用 SaaS。
- **コーパス**: **280M+ 論文メタデータ＋50M+ OA 全文 PDF**。
- **主要機能**:
  - **Chat with PDF / Chat with Folder**: 単一/複数 PDF に質問。10本以上をまとめて synthesis 質問し、
    **trends / contradictions / gaps を出典つきで抽出**。
  - **Literature Review / Deep Review**: 論文発見＋レビュー支援。
  - **AI Writer / Paraphraser / Citation Generator**（2300+ 形式）。
  - **Super Agent**: 150+ ツールを束ねるエージェント。
- **API**: 280M 論文への検索/レビュー API を提供（商用）。

---

## 2. contra への活用評価（3用途の枠組み）

### 2-1. 発見コーパス
- **❌ 不要**。商用 SaaS で母集団は既存帯と重複。OpenAlex 直叩きで足りる。

### 2-2. 手法 / インフラ層

**(A) 遠ドメインの「翻訳」設計 = 生成段の手本 … ★★（固有の価値）**
- contra の出力4部構成のうち **「2) テーマとの関連性」「3) 役に立つ可能性の仮説」** は、
  **遠い分野の論文をユーザーの土俵へ翻訳する**工程。`serendipity_conditions.md` が言う
  「慧眼の一時的な肩代わり」がここで起きる。
- SciSpace の Chat with PDF は「**専門外の読者に、その論文が何を・なぜ・どう主張するかを噛み砕く**」ことに
  最適化されている。これは contra が**1本の遠ドメイン論文を提示するときの語り口**（前提知識を仮定せず、
  Purpose/Mechanism を平易に橋渡しする）の参考になる。
- 具体化案: `generate.py` の LLM プロンプトに「**読者はこの分野の門外漢**である」前提を明示し、
  専門用語を最小限の翻訳つきで提示する方針を組み込む（既にある場合は強化）。**出力フォーマット自体は不変更**。

**(B) Chat with Folder の「矛盾・ギャップ抽出」 … ★（contra 方向と逆、限定的）**
- 複数論文から contradictions/gaps を出す機能は、近傍ドメイン内の収束的合成。contra の中核（遠ドメイン構造類推）
  とは方向が逆。bynote の「メモから問いを立てる」工程に弱く着想を与える程度。

**(C) 50M OA 全文 … —（既出で代替）**
- byserendipity の「abstract が薄い」問題への全文補強は、**オープンな IA Scholar / S2** で実現すべき
  （SciSpace は商用 SaaS のため不適）。

### 2-3. ポジショニング
SciSpace で「**収束型 SaaS（Elicit/Consensus/SciSpace）はすべて同じ ~200–280M コーパスの上で、
理解・要約・合意・執筆を競っている**」構図が明確になった。contra はこの土俵に乗らず、
**同じコーパスを"遠さ×構造一致"で逆引きする**点でのみ差別化される。

---

## 3. フロー別まとめ

| フロー | 翻訳設計(A) | 矛盾/ギャップ(B) | 全文(C) |
|---|---|---|---|
| byserendipity | ★★（提示の語り口） | — | △（IA Scholar で代替） |
| bynote | ★（メモの平易化） | ★（問い立て） | — |
| bybridge/byrepo | ★（提示の語り口） | — | — |

---

## 4. 制約整合・推奨

- 新規の外部依存・コーパス追加は不要。**(A) はプロンプト方針の調整のみ**で禁則に抵触しない
  （出力フォーマット・スコア設計・データモデルは不変更）。
- **推奨アクション**: `generate.py` の生成プロンプトに「読者は遠ドメインの門外漢」前提を明示し、
  Purpose/Mechanism を翻訳的に橋渡しする語り口を強化（SciSpace Chat with PDF の手本）。低リスク・即効。

---

## 5. 結論の一言

SciSpace は **収束型 SaaS の3例目**で、コーパス・横断合成としては不要。ただし
**「遠い論文を門外漢へ翻訳する」という一点だけは、contra の生成段（関連性・仮説フィールド）が
まさに必要とする能力**であり、語り口の手本として参照価値がある。
（前提理論は `serendipity_conditions.md` の慧眼／プリペアードマインド。）

---

## 付記: 一次情報

- SciSpace 製品概要（280M 論文・Chat with PDF・レビュー）: <https://scispace.com/>
- Chat with PDF の仕組み: <https://scispace.com/help/en/articles/10660595>
- コーパス規模（280M+ / 50M OA 全文）: <https://scispace.com/papers>
