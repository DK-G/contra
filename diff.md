# 変更報告書 (Diff)

**開発エージェントは、作業完了後に必ずこのファイルを更新してください。**
レビュー担当者は、このファイルのみを見て変更内容を判断します。

---

## 1. 変更目的 (必須)

*   llm-evolve 2026-11-20 の型 3（bybridge）で、交差候補 60 件が視覚のベンチマーク（RESISC45・DTD・GTSRB・Cars・EuroSAT・SUN）と CLIP の bridge 経由の医療画像・農業・リモートセンシングで埋まり、収穫 0（`D:\dev\agents\reports\contra-survey\failures.md` 11-20、F-85 の 3 例目）。
*   model merging の論文は全部が同じベンチマーク一式で評価するので、データセットの bridge がシード共有数で先頭に並び、60 枠を先に使い切る。被引用は 1.7〜5 千で、上限の処方（F-85 (a)）では外れない。
*   走査の順を「被引用の小さい bridge から」にする opt-in を足し、データセット・基礎モデルの bridge は残りの枠だけを埋めるようにする（F-85-S）。
*   同じ 11-20 の型 1（byserendipity）で、ランダム行列の facet が 38 件中 CS（Signal Processing）26 件で home_converged と判定され、主題どおりの Mathematics 12 件ごと棄却された。近い段を狙う呼び手向けに、ホームの外だけを残す opt-in を足す（F-92）。

---

## 2. 変更概要 (必須)

*   変更ファイル: `src/pipeline/bridge_diagnostics.py`, `src/mcp_server.py`, `tests/test_small_bridges_first.py`（新規）, `src/pipeline/collect.py`, `tests/test_keep_converged_facets.py`（新規）, `scripts/bybridge_replay_cache.py`（新規）, `docs/field_observations_seihai.md`, `DECISION_LOG.md`, `Changelog.md`, `diff.md`, `task.md`
*   `small_bridges_first(pool, cited, keep_tail)`: プールを被引用の小さい順に安定ソート（同値はプール順・不明は群の最後・F-66 の語彙側だけの末尾は末尾のまま）。`render_small_bridges_first`: 診断の 1 行。
*   bybridge の引数 `bridge_order`（"pool" 既定／"small_first"）。被引用は生存確認で既に取っている値（F-85-I）を使うのでリクエストは増えない。既定の出力は不変（F-85 の大きさの行の括弧の文言だけ更新）。
*   byserendipity の引数 `keep_converged_facets`（既定 false）: home_converged の facet でもホーム Field の外のレコードは残す。既定は棄却のままで、警告の行に捨てたホーム外の件数を足す。
*   ハブ側: `D:\dev\agents\routines\llm-evolve-daily.md` の型 3 に `bridge_order:"small_first"`・`home_domain_preference:false`、型 1・2 に `keep_converged_facets: true` を足した（リポ外）。

---

## 3. 確認方法 (必須)

*   `python -m pytest tests/ -q` → 755 passed（新規 9 件）
*   byserendipity: 11-20 の型 1 と同じ引数で実 OpenAlex に再実行。既定 候補 36 件（facet [2] は棄却・警告にホーム外 12 件）→ opt-in 47 件（facet [2] が Mathematics 11 件）。
*   再生（実 OpenAlex を 1 回記録→同じページで引数違い）: `python scripts/bybridge_replay_cache.py . <dir> record` の後 `variants`。llm-evolve 11-20 の引数で、既定の再生は当夜の構成と一致。最小 bridge 5 千以上の候補 11 → 0、主題に沿う題（語での目安）1 → 6（small_first）→ 8（＋home_domain_preference:false）。

---

## 4. 既知の課題・リスク (必須)

*   数字は 1 テーマ・1 回、題の語での目安で、呼び手の採点ではない。効いたかは llm-evolve の次の型 3（金曜）の採点で見る。
*   入れ替わっても雑多な応用（IoT・眼科など）は残る。F-85 の「手法の利用者」は大きさに依らず起きる。
*   F-85-D は CS ホームだと数学・物理を後回しにする（同じ Physical Sciences）。既定は 12-01 頃の判定まで変えず、llm-evolve 側で切る。
*   seihai には効かない／測っていない（既定 "pool" のまま）。
*   F-92 で残るホーム外が主題の兄弟 Field の回もある（seihai の型）ので既定にしていない。llm-evolve で効いたかは次の型 1（月曜）の採点で見る。
