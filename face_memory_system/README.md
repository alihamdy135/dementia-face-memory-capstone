# Offline Face Memory Prototype

This package implements the face-identification path for the dementia-assistance prototype described in the project brief. It uses pretrained OpenCV Zoo models and does not train a detector or a recognizer.

## Scope

The inference pipeline is:

1. YuNet detects a face and five landmarks in a BGR image.
2. SFace aligns the face and produces a normalized embedding.
3. The embedding is compared with locally enrolled templates using cosine similarity.
4. A calibrated threshold either returns a registered `person_id` or abstains as `unknown`/`ambiguous`.
5. SQLite returns the caregiver-entered name, relationship, and notes for that identity.

Adding a person or an image adds a template to the local gallery. It does not update model weights. The relationship and personal facts are metadata entered by an authorized caregiver; they are never inferred from a face. Because matching uses the best score over each person's enrolled templates, adding many templates can change the score distribution; re-check the validation threshold after substantial gallery changes before enabling automatic speech.

The package stores and retrieves notes deterministically. It does not include an LLM, semantic text RAG, speech transcription, text-to-speech, GUI, or a wearable-camera driver. Those can be added independently after the recognition and privacy requirements are agreed.

## Models and licensing

The pretrained ONNX models are in `models/`. Their source URLs, SHA-256 hashes, and license files are documented in `models/MODELS.md`. YuNet is listed under MIT and SFace under Apache-2.0 in their OpenCV Zoo directories. Review upstream model and training-data provenance before commercial use. The OpenCV documentation reports 99.60% for SFace on the LFW **1:1 verification** benchmark; this is not this project's 1:N identification accuracy.

## Install

Use an isolated environment. The code was authored to support Python 3.10+; dependency compatibility must still be verified on the final target device.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python models/download_models.py
```

The ONNX files are fetched from a pinned OpenCV Zoo revision and checked against their documented SHA-256 digests. Keep them local; they are intentionally excluded from the public Git repository. After dependencies and model files are present, inference does not require a network connection.

## Enroll a person

Use consented, clear face images captured in varied conditions. Each image should contain exactly one face. Repeating `enroll` with the same stable ID adds another face template without replacing previous ones.

```bash
face-memory enroll \
  --image /path/to/consented_face.jpg \
  --person-id contact-001 \
  --name "Alex" \
  --relationship "friend"
```

The profile and embeddings are stored in `data/face_memory.sqlite3` by default. The database contains biometric templates and local file paths; keep it private and protect it with device-level disk encryption and access controls. Do not publish it or commit it to version control.

Add a caregiver note or a link to a locally stored audio recording:

```bash
face-memory add-memory --person-id contact-001 --text "Prefers to be called Alex."
face-memory add-memory --person-id contact-001 --audio /private/audio/alex-introduction.wav
```

The audio file is not copied or transcribed by this prototype; only its path is stored. To remove a person, their templates, and notes:

```bash
face-memory delete --person-id contact-001
```

## Recognition

Recognition is deliberately disabled until a cosine threshold has been selected on validation data. Do not copy the LFW verification threshold into this one-to-many use case.

```bash
face-memory recognize --image /path/to/query.jpg --threshold <validation_threshold>
```

The result includes the status, best and second-best similarity, profile, and saved notes. No face, multiple faces, a weak match, or a close/ambiguous match should not be announced as a person. The current interface accepts a single-person image; it does not select the intended person from a multi-person scene.

## Evaluation protocol

Create a private manifest using `examples/manifest_template.csv`. Required columns:

- `image_path`: absolute path or path relative to the manifest.
- `person_id`: stable, human-verified identity key.
- `split`: `gallery`, `validation`, or `test`.
- `session_id`: optional capture-session/group identifier. When present, all images from one session must remain in one split.

Protocol requirements:

- `gallery` rows are the enrollment templates.
- Known identities appear in gallery and in query splits, but use different capture sessions when session information is available.
- Unknown identities must have no gallery images. Keep unknown identities disjoint between validation and test.
- Include both known and unknown queries in validation and test to report open-set performance.
- Do not use test labels to select a threshold or modify the system. Choose the allowable unknown false-identification rate before calibration.

Calibrate on validation. For example, `--max-unknown-fpir 0.05` is a **proposed operating constraint** of at most 5% unknown false identifications; choose it based on the project safety requirements before examining test results.

```bash
face-memory-evaluate \
  --manifest /path/to/manifest.csv \
  --mode calibrate \
  --max-unknown-fpir 0.05 \
  --output reports/validation.json
```

The report returns `selected_threshold`. Freeze that value, then evaluate the locked test split once:

```bash
face-memory-evaluate \
  --manifest /path/to/manifest.csv \
  --mode test \
  --threshold <selected_threshold> \
  --output reports/test.json
```

Keep manifests and reports private because they contain identity labels and image paths.

## Metrics included

- `overall_accuracy`: exact known identity or correct unknown rejection, divided by all queries.
- `known_top1_accuracy`: correct registered identity / all known queries; abstentions count as errors.
- `known_identification_failure_rate` and `known_wrong_identity_rate`, so a wrong identity is not hidden inside the false-rejection count.
- `known_acceptance_rate` and `known_false_rejection_rate`.
- `unknown_fpir`: fraction of unknown queries incorrectly assigned to any registered identity.
- `unknown_rejection_recall`: fraction of unknown queries rejected correctly.
- `coverage`: fraction of all queries assigned an identity rather than rejected.
- `accepted_identity_precision`, macro precision/recall/F1, per-class scores, and confusion matrix.
- face-detection/embedding failure count and rate.
- mean, median, p95, and maximum recognition time per image, including image decoding and matching but excluding camera capture, audio, and TTS.

A strong known-person accuracy alone is not enough: report unknown false identifications and known-person rejections beside it. For the 2-second project target, measure the complete frame-to-spoken-response path on the actual wearable/target hardware; this image-file benchmark does not establish that requirement. Detector AP/IoU also requires face-box ground truth and is not computed by the identity-only manifest.

## What still needs project data or training

No family photos, target-device samples, or labeled test manifest were supplied, so this package reports **no project accuracy or latency result**. It cannot establish that the 80% target is met. The next evaluation input must be consented images/videos from the intended camera and an identity-disjoint unknown set, annotated by capture session. If the pretrained embeddings perform poorly in that target domain, then consider collecting a larger authorized dataset and evaluating a domain adaptation or fine-tuning proposal; do not fine-tune after every enrollment.

If the embedding model is ever upgraded, regenerate every stored face embedding using the same model version before matching; embeddings from different encoder versions are not assumed compatible.
