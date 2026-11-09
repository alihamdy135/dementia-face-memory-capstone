# FEI Poster Figures

The ten figures were generated from saved evaluation data with Python and Matplotlib. Each figure is available as an SVG for scaling and a PNG rendered at 300 DPI. The figures use aggregate counts and anonymous identity labels.

| No. | Figure title | X axis | Y axis |
| --- | --- | --- | --- |
| 01 | Face identification on FEI | No axes; metric cards | No axes; Known Top-1, Macro F1, and Unknown FPIR values |
| 02 | How the FEI images were split | Image count | Dataset split: Gallery, Validation, and Test |
| 03 | What the system returned | No axes; decision categories | No axes; count for each outcome |
| 04 | Best similarity score by query group | Best cosine similarity | Share of group per bin |
| 05 | Gap between the two best matches | Best score minus second-best score | Share of group per bin |
| 06 | Detection or encoding failures | Failure rate | Image group |
| 07 | How many queries were correct per person? | Correctly identified queries per person | Number of people |
| 08 | Accuracy versus false identification | Unknown false positive identification rate (FPIR) | Known Top-1 accuracy |
| 09 | Image-to-match processing time | Summary statistic: mean, median, p95, or maximum | Milliseconds per query |
| 10 | From an image to an identity | No axes; processing stages | No axes; decision path |

## Figure notes

- **01 — Test metrics:** 1,200 held-out image queries; Known Top-1 is 98.6%, Macro F1 is 99.22%, and 0 of 700 unknown queries were accepted as enrolled people.
- **02 — Dataset split:** 2,800 images of 200 people. The 100 enrolled identities appear in each split; validation and test strangers are disjoint.
- **03 — Test outcomes:** 493 of 500 known queries returned the correct identity, 7 were rejected or otherwise incorrect, and all 700 unknown queries were rejected.
- **04 — Similarity distribution:** highest valid cosine similarity for known and unknown queries. The dashed line shows the threshold locked before test.
- **05 — Margin distribution:** difference between the highest and second-highest identity scores. The dashed line shows the minimum accepted margin of `0.02`.
- **06 — Detection and encoding failures:** rate of face-detection or embedding-extraction failures in the gallery and query groups.
- **07 — Identity recall:** 93 identities had 5 of 5 test images correctly identified; 7 identities had 4 of 5 correctly identified.
- **08 — Validation operating curve:** known-person accuracy at observed unknown FPIR values up to the 5% validation constraint. The selected threshold was locked before test.
- **09 — CPU latency:** image decoding, face encoding, and matching on a local Linux x86-64 CPU. Test p95 was 51.7 ms. This does not measure live capture or audio playback.
- **10 — Decision flow:** input image, YuNet face detection, SFace embedding, cosine-similarity match, then return an identity or abstain.

For a poster with limited space, start with figures **01, 02, 04, and 10**. Use figure 06 for error analysis or figure 08 to explain threshold selection.

## Scope and regeneration

FEI is a fixed-image benchmark. Capture sessions and camera/lens metadata were not documented by the source. Measure live camera-to-audio response separately on the project's camera and Raspberry Pi 2.

The figure source is [`plot_fei_poster.py`](plot_fei_poster.py). It reads the private validation and test JSON reports plus the public aggregate summary. Keep the input reports and manifest in `private_data/`; do not commit them.

```bash
python -m pip install matplotlib numpy
python reports/public/fei_poster_figures/plot_fei_poster.py \
  --validation-report private_data/fei_original/reports/validation.json \
  --test-report private_data/fei_original/reports/test.json \
  --summary reports/public/poster_report.json \
  --output-dir reports/public/fei_poster_figures
```

