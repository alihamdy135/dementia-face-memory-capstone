# Model assets and provenance

The ONNX files in this directory are pretrained inference models; this project does not train or fine-tune them.

| File | Role | Source | SHA-256 | Published source license |
|---|---|---|---|---|
| `face_detection_yunet_2023mar.onnx` | Face detection and landmarks | [OpenCV Zoo YuNet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet) | `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4` | MIT, see `LICENSE-YUNET.txt` |
| `face_recognition_sface_2021dec.onnx` | Face embeddings | [OpenCV Zoo SFace](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface) | `0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79` | Apache-2.0, see `LICENSE-SFACE.txt` |

The files were obtained from OpenCV Zoo's Hugging Face mirror at repository revision `d4938dfc9d4ec5d098bfa33e98b3f3345a236586`. The SFace README reports a 99.60% LFW verification result; that is a published 1:1 benchmark result, not a measurement of this project's 1:N identification system or its target camera. Review model and training-data provenance before any commercial deployment.
