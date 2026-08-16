# Litmaps (litmaps.com) 調査レポート（contra への活用可否）

> 本ドキュメントは、文献マッピングツール Litmaps を調査し、contra への活用可否を判定した記録。
> Connected Papers / ResearchRabbit と同じ引用マッピング系のため、本稿は**差分（時系列軸・モニタリング）**に絞る。
> 調査手段: litmaps.com / ヘルプ＋ Web 調査。調査日: 2026-06-14。
> 対象: <https://www.litmaps.com/>（freemium SaaS）
> 関連: [`connected_papers_review.md`](connected_papers_review.md), [`researchrabbit_review.md`](researchrabbit_review.md)

---

## 0. 結論（最重要）

1. **検索先にはならない（SaaS・公開 API なし）。** 基盤は **Semantic Scholar / OpenAlex / Crossref**（270M+）＝
   contra が既に持つ/叩ける母集団。母集団は OpenAlex 直叩きで足りる。

2. **本バッチ初の新しい軸＝「モニタリング（継続発見）」。** Litmaps Monitor は保存した検索を**毎日バックグラウンドで
   監視**し、**新着の関連論文を通知**する。これは contra が現状持たない「**ワンショット → 継続**」の発想で、
   contra の **テーマ別履歴（`history.py`）＋ M3 飽和検知**の自然な拡張＝**"contra watch モード"** に対応づく。

3. **時系列マップは軽い可視化改良。** Litmaps は論文を**出版日で配置**（後=引用側／前=被引用側）。contra の
   bridge グラフに**時間軸**を足す案の参考になるが、contra の主軸は**ドメイン距離**なので副次的。

---

## 1. Litmaps とは

- **正体**: seed（論文/キーワード）→ 関連論文を**時系列の litmap**で可視化する文献レビュー支援（freemium）。
- **seed maps の類似度**: 共有引用・参考（書誌的結合）/ 共著パターン / abstract・title 類似。
- **時系列軸**: 論文を出版日で配置 → 引用グラフを**時間マップ化**。
- **Monitor/Alerts**: 保存検索を毎日監視し新着を通知（継続的な文献サーベイランス）。
- **コーパス**: Semantic Scholar / OpenAlex / Crossref（270M+）。
- **価格**: 無料（月2マップ・100論文）/ Pro $8/月。公開 API は実質なし。

---

## 2. contra への活用評価

### 2-1. 発見コーパス
- **❌ 不要**。S2/OpenAlex/Crossref 上の SaaS、公開 API なし。

### 2-2. 手法 / インフラ層

**(A) モニタリング = "contra watch モード" の着想 … ★★（本バッチ唯一の新軸）**
- 現状の contra は**ワンショット**: テーマ入力 → 収集・選別・生成 → 出力。
- Litmaps Monitor の「保存検索を継続監視し新着を通知」を contra 流に翻訳すると:
  - テーマを定期再実行し、**前回履歴（`history.py` の採用 ID）に無い新しい遠ドメイン bridge** が
    閾値超えで現れたら surface する **watch/monitor モード**。
  - これは既存の **M3 飽和検知**（良候補ゼロ時の扱い）と表裏で、「飽和後に時間が経って新候補が出たら再通知」を担える。
  - **OKF メモリ層**（採用履歴のバンドル化）があれば差分検出が素直。
- 留意: contra はローカル CLI/MCP ツールで、ホスト型アラートサービスではない。実体は「**cron 的再実行＋履歴 diff**」で、
  プロダクト範囲の判断（やるかどうか）が要る。**優先度は中**（核ではないが、履歴/メモリ層が育てば自然に乗る）。

**(B) 時系列マップ … ★（可視化の軽い改良）**
- contra の bridge グラフ（Connected Papers レポートの可視化案）に**時間軸**を足せる:
  例）x=出版年、y=ドメイン距離 → 「古い共有参照(bridge)から、近年の遠ドメイン論文が派生している」流れを見せる。
  ただし contra の決定的軸は距離であり、時間は副次。

**(C) その他接続（共著・類似）**
- ResearchRabbit と同様。共著は近傍シグナルで**避ける**、類似は**距離（遠さ）として反転利用**。新規性なし。

### 2-3. ポジショニング
可視化系（Connected Papers / ResearchRabbit / Litmaps）の3つ目。3者で固有なのは Litmaps の
**「継続モニタリング」**だけで、それが contra に唯一の新しい設計アイデア（watch モード）を供給する。

---

## 3. 結論の一言

Litmaps は **可視化系の3例目で、コーパス・大半の手法は既出と重複**。唯一の収穫は **モニタリング（継続発見）** で、
contra の **履歴/M3/メモリ層を土台にした "watch モード"** という将来拡張の着想をくれる（優先度・中、核ではない）。
時系列軸は bridge 可視化の軽い改良に留まる。

---

## 付記: 一次情報

- Litmaps の仕組み（seed maps・時系列・コーパス）: <https://www.litmaps.com/>
- Monitor/Alerts: <https://docs.litmaps.com/en/articles/9126249-monitor-get-alerts-for-important-research>
- 文献マッピング比較（Connected Papers / Inciteful / Litmaps）: Aaron Tay, Medium
