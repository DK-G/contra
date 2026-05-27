# 医用画像診断 ブレインストーミング出力

## 入力サマリ

- テーマ概要: 近年、機械学習を用いた医用画像診断の精度は大きく向上したが、データ分布の偏りや施設間差により、汎化性能が不安定になることが多い。本テーマでは、異なる施設・装置間での性能劣化がどの条件で顕在化するのかを明らかにしたい。さらに、性能低下が起きる要因を特定し、再現性のある評価指標を設計することが目的である。特に小規模データやクラス不均衡の影響を考慮する。加えて、評価の再現性が乏しい現状を踏まえ、施設間のばらつきを説明できる要素を洗い出したい。
- 目的: 施設間・装置間の分布差が診断精度に与える影響を定量化する
- 問題意識: 医療現場での実運用では汎化不全が誤診リスクに直結するため
- アプローチ: experiment
- 前提・仮説:
  - 施設ごとに画像分布が異なる
  - 一部の装置ではノイズ特性が異なる
  - 評価指標が実運用の失敗を十分に反映していない
- スコープ:
  - 分野: 医用画像診断
  - スケール: small
  - 時代: last_10_years
- include: domain shift, generalization, medical imaging
- exclude: natural images
- 不安点: 評価指標の設計が恣意的になり、改善に結びつかないのではないか

## 目次

- 関連度が高い論文（100本）
- 広域探索（200本）
- 無関係論文（200本）
- 無関係論文：反証・対立仮説（50本）
- 無関係論文：測定・評価の地雷（50本）
- 無関係論文：手法転用（50本）
- 無関係論文：制約条件が真逆（50本）

## 関連度が高い論文（100本）

- タイトル: Domain Generalization: A Survey
- 年: 2022
- 掲載: IEEE Transactions on Pattern Analysis and Machine Intelligence
- 被引用: 975
- リンク: https://doi.org/10.1109/tpami.2022.3195549

1) 関係性: キーワード一致（domain shift, generalization, medical imaging）があるため関連性が高い。
2) 要約: Generalization to out-of-distribution (OOD) data is a capability natural to humans yet challenging for machines to...
3) 注意点: データ/評価条件に依存する可能性。

- タイトル: Generalizing Deep Learning for Medical Image Segmentation to Unseen Domains via Deep Stacked Transformation
- 年: 2020
- 掲載: IEEE Transactions on Medical Imaging
- 被引用: 488
- リンク: https://doi.org/10.1109/tmi.2020.2973595

1) 関係性: キーワード一致（domain shift, generalization, medical imaging）があるため関連性が高い。
2) 要約: Recent advances in deep learning for medical image segmentation demonstrate expert-level accuracy. However, application...
3) 注意点: データ/評価条件に依存する可能性。

- タイトル: Progressive Transfer Learning and Adversarial Domain Adaptation for Cross-Domain Skin Disease Classification
- 年: 2019
- 掲載: IEEE Journal of Biomedical and Health Informatics
- 被引用: 162
- リンク: https://doi.org/10.1109/jbhi.2019.2942429

1) 関係性: キーワード一致（domain shift, generalization, medical imaging）があるため関連性が高い。
2) 要約: Deep learning has been used to analyze and diagnose various skin diseases through medical imaging. However, recent...
3) 注意点: データ/評価条件に依存する可能性。

- タイトル: Learning Domain-Agnostic Visual Representation for Computational Pathology Using Medically-Irrelevant Style Transfer Augmentation
- 年: 2021
- 掲載: IEEE Transactions on Medical Imaging
- 被引用: 66
- リンク: https://doi.org/10.1109/tmi.2021.3101985

1) 関係性: キーワード一致（domain shift, generalization, medical imaging）があるため関連性が高い。
2) 要約: Suboptimal generalization of machine learning models on unseen data is a key challenge which hampers the clinical...
3) 注意点: データ/評価条件に依存する可能性。

- タイトル: The reliability of a deep learning model in clinical out-of-distribution MRI data: A multicohort study
- 年: 2020
- 掲載: Medical Image Analysis
- 被引用: 164
- リンク: https://doi.org/10.1016/j.media.2020.101714

1) 関係性: キーワード一致（domain shift, generalization, medical imaging）があるため関連性が高い。
2) 要約: Deep learning (DL) methods have in recent years yielded impressive results in medical imaging, with the potential to...
3) 注意点: データ/評価条件に依存する可能性。

- タイトル: An empirical framework for domain generalization in clinical settings
- 年: 2021
- 掲載: 
- 被引用: 34
- リンク: https://doi.org/10.1145/3450439.3451878

1) 関係性: キーワード一致（domain shift, generalization, medical imaging）があるため関連性が高い。
2) 要約: Clinical machine learning models experience significantly degraded performance in datasets not seen during training,...
3) 注意点: データ/評価条件に依存する可能性。

- タイトル: Domain Generalization via Model-Agnostic Learning of Semantic Features
- 年: 2019
- 掲載: arXiv (Cornell University)
- 被引用: 428
- リンク: https://doi.org/10.48550/arxiv.1910.13580

1) 関係性: キーワード一致（domain shift, generalization）があるため関連性が高い。
2) 要約: Generalization capability to unseen domains is crucial for machine learning models when deploying to real-world...
3) 注意点: データ/評価条件に依存する可能性。

- タイトル: Measuring Domain Shift for Deep Learning in Histopathology
- 年: 2020
- 掲載: IEEE Journal of Biomedical and Health Informatics
- 被引用: 246
- リンク: https://doi.org/10.1109/jbhi.2020.3032060

1) 関係性: キーワード一致（domain shift, generalization）があるため関連性が高い。
2) 要約: The high capacity of neural networks allows fitting models to data with high precision, but makes generalization to...
3) 注意点: データ/評価条件に依存する可能性。

- タイトル: PnP-AdaNet: Plug-and-Play Adversarial Domain Adaptation Network at Unpaired Cross-Modality Cardiac Segmentation
- 年: 2019
- 掲載: IEEE Access
- 被引用: 198
- リンク: https://doi.org/10.1109/access.2019.2929258

1) 関係性: キーワード一致（domain shift, generalization）があるため関連性が高い。
2) 要約: Deep convolutional networks have demonstrated state-of-the-art performance on various challenging medical image...
3) 注意点: データ/評価条件に依存する可能性。

- タイトル: Rethinking Data Augmentation for Single-Source Domain Generalization in Medical Image Segmentation
- 年: 2023
- 掲載: Proceedings of the AAAI Conference on Artificial Intelligence
- 被引用: 86
- リンク: https://doi.org/10.1609/aaai.v37i2.25332

1) 関係性: キーワード一致（domain shift, generalization）があるため関連性が高い。
2) 要約: Single-source domain generalization (SDG) in medical image segmentation is a challenging yet essential task as domain...
3) 注意点: データ/評価条件に依存する可能性。

- タイトル: Domain generalization on medical imaging classification using episodic training with task augmentation
- 年: 2021
- 掲載: Computers in Biology and Medicine
- 被引用: 80
- リンク: https://doi.org/10.1016/j.compbiomed.2021.105144

1) 関係性: キーワード一致（generalization, medical imaging）があるため関連性が高い。
2) 要約: abstract欠損
3) 注意点: データ/評価条件に依存する可能性。

- タイトル: FedDG: Federated Domain Generalization on Medical Image Segmentation via Episodic Learning in Continuous Frequency Space
- 年: 2021
- 掲載: 
- 被引用: 474
- リンク: https://doi.org/10.1109/cvpr46437.2021.00107

1) 関係性: キーワード一致（generalization）があるため関連性が高い。
2) 要約: Federated learning allows distributed medical institutions to collaboratively learn a shared prediction model with...
3) 注意点: データ/評価条件に依存する可能性。

## 広域探索（200本）

- タイトル: Can We Trust Deep Learning Based Diagnosis? The Impact of Domain Shift in Chest Radiograph Classification
- 年: 2020
- 掲載: Lecture notes in computer science
- 被引用: 105
- リンク: https://doi.org/10.1007/978-3-030-62469-9_7

1) 関係性: キーワード一致（domain shift）があるため関連性が高い。
2) 要約: abstract欠損
3) 注意点: データ/評価条件に依存する可能性。

- タイトル: Single-Domain Generalization in Medical Image Segmentation via Test-Time Adaptation from Shape Dictionary
- 年: 2022
- 掲載: Proceedings of the AAAI Conference on Artificial Intelligence
- 被引用: 40
- リンク: https://doi.org/10.1609/aaai.v36i2.20068

1) 関係性: キーワード一致（generalization）があるため関連性が高い。
2) 要約: Domain generalization typically requires data from multiple source domains for model learning. However, such strong...
3) 注意点: データ/評価条件に依存する可能性。

- タイトル: A survey on Image Data Augmentation for Deep Learning
- 年: 2019
- 掲載: Journal Of Big Data
- 被引用: 11477
- リンク: https://doi.org/10.1186/s40537-019-0197-0

1) 関係性: キーワード一致は弱いが関連の可能性がある。
2) 要約: abstract欠損
3) 注意点: データ/評価条件に依存する可能性。

- タイトル: A Foundation Language-Image Model of the Retina (FLAIR): encoding expert knowledge in text supervision
- 年: 2024
- 掲載: Medical Image Analysis
- 被引用: 61
- リンク: https://doi.org/10.1016/j.media.2024.103357

1) 関係性: キーワード一致は弱いが関連の可能性がある。
2) 要約: abstract欠損
3) 注意点: データ/評価条件に依存する可能性。

- タイトル: BayeSeg: Bayesian modeling for medical image segmentation with interpretable generalizability
- 年: 2023
- 掲載: Medical Image Analysis
- 被引用: 70
- リンク: https://doi.org/10.1016/j.media.2023.102889

1) 関係性: キーワード一致は弱いが関連の可能性がある。
2) 要約: abstract欠損
3) 注意点: データ/評価条件に依存する可能性。

- タイトル: CDDSA: Contrastive domain disentanglement and style augmentation for generalizable medical image segmentation
- 年: 2023
- 掲載: Medical Image Analysis
- 被引用: 51
- リンク: https://doi.org/10.1016/j.media.2023.102904

1) 関係性: キーワード一致は弱いが関連の可能性がある。
2) 要約: abstract欠損
3) 注意点: データ/評価条件に依存する可能性。

## 無関係論文（200本）

- タイトル: Generalizable Medical Image Segmentation via Random Amplitude Mixup and Domain-Specific Image Restoration
- 年: 2022
- 掲載: Lecture notes in computer science
- 被引用: 50
- リンク: https://doi.org/10.1007/978-3-031-19803-8_25

1) 関係性: キーワード一致は弱いが関連の可能性がある。
2) 要約: abstract欠損
3) 注意点: データ/評価条件に依存する可能性。

- タイトル: Data clustering
- 年: 1999
- 掲載: ACM Computing Surveys
- 被引用: 13015
- リンク: https://doi.org/10.1145/331499.331504

1) 関係性: キーワード一致は弱いが関連の可能性がある。
2) 要約: Clustering is the unsupervised classification of patterns (observations, data items, or feature vectors) into groups...
3) 注意点: データ/評価条件に依存する可能性。

## 無関係論文：反証・対立仮説（50本）

- タイトル: Generalizable Medical Image Segmentation via Random Amplitude Mixup and Domain-Specific Image Restoration
- 年: 2022
- 掲載: Lecture notes in computer science
- 被引用: 50
- リンク: https://doi.org/10.1007/978-3-031-19803-8_25

1) 関係性: キーワード一致は弱いが関連の可能性がある。
2) 要約: abstract欠損
3) 注意点: データ/評価条件に依存する可能性。

## 無関係論文：測定・評価の地雷（50本）

- タイトル: Data clustering
- 年: 1999
- 掲載: ACM Computing Surveys
- 被引用: 13015
- リンク: https://doi.org/10.1145/331499.331504

1) 関係性: キーワード一致は弱いが関連の可能性がある。
2) 要約: Clustering is the unsupervised classification of patterns (observations, data items, or feature vectors) into groups...
3) 注意点: データ/評価条件に依存する可能性。

## 無関係論文：手法転用（50本）

- （未収集）

## 無関係論文：制約条件が真逆（50本）

- （未収集）

## 付録

- 取得日: 2026-02-11
- 検索条件: domain shift generalization medical imaging
- フィルタ条件: abstract任意
