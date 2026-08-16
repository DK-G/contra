# bioRxiv / medRxiv 調査レポート（contra への活用可否）

> 一般論文サイト総覧 #8。PubMed/Europe PMC（[`pubmed_europepmc_review.md`](pubmed_europepmc_review.md)）で
> 「Europe PMC が 31 プレプリントサーバを統合」と確認済み。本稿は**個別に叩く価値があるか**に絞る短評。
> 調査手段: api.biorxiv.org / connect.biorxiv.org ＋ Web 調査。調査日: 2026-06-15。
> 対象: <https://www.biorxiv.org/> / <https://www.medrxiv.org/> / API: <https://api.biorxiv.org/>

---

## 0. 結論（最重要）

**個別採用は不要（Europe PMC に包含）。** bioRxiv/medRxiv は生物・医学のプレプリントサーバで、
**無料・キー不要の API**（メタデータ＋JATS XML＋S3 全文 TDM）を持つ。だが contra から見ると:
- **発見**は OpenAlex（プレプリント収録）＋ **Europe PMC（31 サーバ統合）**でカバー、
- **全文**も Europe PMC の OA 全文で取得可、
- 生物医学ドメインは **Europe PMC を入口に一本化**（#4 の結論）するのが実装上最適。
→ bioRxiv/medRxiv を**個別 provider として足す必要はない**。

---

## 1. 固有機能と、それが contra に効くか

| bioRxiv/medRxiv API の固有要素 | contra への効き |
|---|---|
| **preprint → 出版 DOI のリンク**（published フィールド） | △ プレプリント版と出版版の対応。contra の遠ドメイン構造類推には不要 |
| **バージョン履歴** | △ 改訂追跡。watch モードでわずかに関係する程度 |
| **最新性**（ingestion ラグなし） | △ 最速だが、構造類推に分単位の鮮度は不要 |
| 全文（JATS / S3 TDM） | ◯ だが Europe PMC OA 全文で代替可 |

- いずれも **Europe PMC 経由で大半が賄え**、固有要素（出版 DOI 対応・版履歴・最速性）は contra の中核に効かない。

---

## 2. 結論の一言

bioRxiv/medRxiv は **無料・良 API だが、生物医学プレプリントは Europe PMC が統合済み**。
contra は **Europe PMC を入口に一本化**すれば足り、bioRxiv/medRxiv の個別採用は不要。
（将来 "preprint→published 対応" や最速取得が必要になったときだけ、無料・キー不要の直 API を検討。）

---

## 付記: 一次情報

- bioRxiv/medRxiv API（無料・キー不要・JATS・版/出版 DOI）: <https://api.biorxiv.org/>
- 全文 TDM（S3）: <https://www.biorxiv.org/tdm>
- 統合元: Europe PMC（[`pubmed_europepmc_review.md`](pubmed_europepmc_review.md)）
