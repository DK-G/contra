「構造を機械向けに固定する」

Markdownを少しだけ「AI向け仕様」に変えます。

例（超重要）：
<!-- AUTO_SECTION:RELATIONSHIP:START -->
## 関係性
（ここはAIが更新）
<!-- AUTO_SECTION:RELATIONSHIP:END -->

<!-- AUTO_SECTION:SUMMARY:START -->
## 要約
（ここはAIが更新）
<!-- AUTO_SECTION:SUMMARY:END -->

<!-- AUTO_SECTION:CAUTION:START -->
## 注意点
（ここはAIが更新）
<!-- AUTO_SECTION:CAUTION:END -->


こうすると：

exact string replace が 使える

START〜END を丸ごと置換すればいい

他の手書き部分は一切壊れない

👉 これが一番コスパ良い解決策
（CLIでも、Codexでも、将来のツールでも使える）