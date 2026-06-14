# tool_reviews — 提案ツール/サイトの見解レポート集

> このフォルダは、外部ツール・サイト・サービスを「contra に活用できるか」という観点で評価した
> 調査レポートを集約する場所。**会話スコープの作業ディレクトリ**であり、検討が一段落したら
> 中身を `docs/research/` へ昇格させるか、フォルダごと処分してよい。

## 進め方（このフォルダの運用ルール）

1. ユーザーが調査対象（ツール / サイト / API）を提案する。
2. 対象を調査し、**contra への活用可否の見解**を作成する。
3. 1対象 = 1 Markdown として本フォルダに格納し、コミットする。

判定の共通枠組み（過去レポートで確立）: 各対象を
- **発見コーパス（検索の走らせ先）** … クエリできる新しい母集団になるか
- **手法（technique）** … 収集/判定の作り方として真似る価値があるか
- **記憶層（memory）** … 出力を蓄積し横断検索できる永続層に効くか

の3用途で評価する。制約（stdlib のみ・`models.py`/スコア設計は不変更）との整合も必ず確認する。

## レポート一覧

| 対象 | レポート | 一言結論 |
|---|---|---|
| OKF / Google `knowledge-catalog` | [`okf_knowledge_catalog_review.md`](okf_knowledge_catalog_review.md) | 公開コーパスではない。効くのは Web Pass（手法）と OKF バンドル化（記憶層） |
| Internet Archive (archive.org) | [`internet_archive_review.md`](internet_archive_review.md) | 発見コーパスは弱。Wayback が byrepo Web Pass のリンク切れを埋める（堅牢化層） |
| Elicit (elicit.com) | [`elicit_review.md`](elicit_review.md) | 製品は contra の対極（収束型）。実利は基盤の Semantic Scholar = SPECTER2 埋め込み（初の有力な追加コーパス／距離軸強化） |
| Consensus (consensus.app) | [`consensus_review.md`](consensus_review.md) | 名前ごと contra の対極（合意=収束）。OpenAlex 再販で検索先にならず。価値は同一性の対照例 |

## 横断的な示唆（現時点）

- 「新しい検索先（母集団）を増やす」系の提案は長らく本命になっていなかったが、**Elicit 調査で初めて
  実体ある候補＝Semantic Scholar (S2AG)** が出た。とくに **SPECTER2 埋め込み**は `spec.md` 将来構想
  「概念アライメント距離」を低コストで実現しうる。ただし**ドメイン距離軸限定**で、構造一致判定には混ぜない。
- 一方で **byrepo の Web Pass（README リンク追跡）** が複数レポートの合流点になっている:
  OKF からは手法、archive.org（Wayback）からは堅牢化層が乗る。最初の実装候補として有力。
- **出力の OKF バンドル化 = 自前メモリ層** も横断テーマ。`history.py` の一般化＋Save Page Now による
  citation 恒久化がここに重なる。
