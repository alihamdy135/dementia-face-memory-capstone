# FEI Face Recognition Benchmark

## Results

YuNet + SFace was evaluated on the original color images from the [FEI Face Database](https://fei.edu.br/~cet/facedatabase.html). The threshold was selected on validation data, then locked before the test split was evaluated.

| Split | Known Top-1 | Macro F1 | Unknown FPIR | Queries |
| --- | ---: | ---: | ---: | ---: |
| Validation | 98.4% | 99.02% | 0.14% (1/700) | 500 known + 700 unknown |
| Test | **98.6%** | **99.22%** | **0% (0/700)** | 500 known + 700 unknown |

Known Top-1 exceeded the capstone's 80% target on this test split. Seven of 500 known test queries failed to return the correct identity. This includes known-face detection or encoding failures. Across test queries, 7 known and 9 unknown images failed face detection or embedding extraction; 6 of 400 gallery images also failed encoding.

## Evaluation protocol

- The dataset contains 2,800 images of 200 people. Each of 100 enrolled identities contributed 4 gallery, 5 validation, and 5 test images.
- Fifty stranger identities were used for validation only and a separate 50 for test only, with 14 images per stranger.
- The split used fixed seed `20261108`. Exact SHA-256 duplicates were grouped, and within-person near-duplicate images (OpenCV pHash Hamming distance ≤ 2) remained in the same split.
- The test set contains 500 known and 700 unknown queries. The gallery contains 394 encoded templates; 6 of its 400 images failed detection or encoding.
- The selected cosine similarity threshold was `0.57770098`; it was selected on validation with a maximum unknown FPIR constraint of 5%, then locked before test. `min_margin` was `0.02`; model version was `yunet-sface-2021dec-v1`.
- FEI does not document capture sessions or camera/lens details. No session IDs were invented. This is a fixed-image benchmark, not an evaluation of the project's live camera protocol or Raspberry Pi 2.

The threshold used by the website remains `0.45` and is marked provisional. The FEI threshold above is specific to this benchmark and must not be presented as a live-camera calibration.

## Python-generated figures

All ten poster figures are rendered with Python and Matplotlib from the evaluation reports. Each is available as a scalable SVG and a 300-DPI PNG. The source and figure descriptions, including the X and Y axes, are in [the figure guide](fei_poster_figures/README.md); the generator is [plot_fei_poster.py](fei_poster_figures/plot_fei_poster.py).

| Figure | SVG | PNG |
| --- | --- | --- |
| Test metrics | [Open](fei_poster_figures/01_test_metrics.svg) | [Open](fei_poster_figures/01_test_metrics.png) |
| Dataset split | [Open](fei_poster_figures/02_dataset_split.svg) | [Open](fei_poster_figures/02_dataset_split.png) |
| Test outcomes | [Open](fei_poster_figures/03_test_outcomes.svg) | [Open](fei_poster_figures/03_test_outcomes.png) |
| Similarity distribution | [Open](fei_poster_figures/04_similarity_distribution.svg) | [Open](fei_poster_figures/04_similarity_distribution.png) |
| Margin distribution | [Open](fei_poster_figures/05_margin_distribution.svg) | [Open](fei_poster_figures/05_margin_distribution.png) |
| Detection and encoding failures | [Open](fei_poster_figures/06_detection_encoding_failures.svg) | [Open](fei_poster_figures/06_detection_encoding_failures.png) |
| Identity recall | [Open](fei_poster_figures/07_identity_recall.svg) | [Open](fei_poster_figures/07_identity_recall.png) |
| Validation operating curve | [Open](fei_poster_figures/08_validation_operating_curve.svg) | [Open](fei_poster_figures/08_validation_operating_curve.png) |
| CPU latency | [Open](fei_poster_figures/09_cpu_latency.svg) | [Open](fei_poster_figures/09_cpu_latency.png) |
| Decision flow | [Open](fei_poster_figures/10_decision_flow.svg) | [Open](fei_poster_figures/10_decision_flow.png) |

The aggregate test confusion matrix and validation threshold curve are also available as [SVG files](confusion_matrix.svg) and [SVG files](accuracy_fpir_threshold.svg). The structured aggregate data is in [poster_report.json](poster_report.json) and [poster_metrics.csv](poster_metrics.csv).

## Source and use terms

The source is the [official FEI Face Database page](https://fei.edu.br/~cet/facedatabase.html). FEI permits research use but does not permit redistribution or reproduction of the database. This repository contains no FEI images, face embeddings, private manifest, personal identifiers, or detailed per-image reports. Original data and detailed reports remain local under the Git-ignored `private_data/` directory.

