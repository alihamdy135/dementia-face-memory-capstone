# Consented Evaluation Data Guide

Do not evaluate on family or patient images without explicit, specific permission for temporary storage and evaluation. Explain the purpose, retention period, and withdrawal process to each participant or their guardian. Store files locally under `private_data/`, outside the public repository, and delete them when they are no longer needed.

## Split the images

- Use random IDs such as `known-001` and `stranger-val-01`, never a person's real name.
- `gallery`: enrollment images for each known person, captured in one or more sessions.
- `validation`: later images of known people from new sessions, plus strangers that do not appear in the gallery.
- `test`: independent later sessions for known people, plus a completely different set of strangers from validation.
- Keep each `session_id` in one split. Do not put images from one video or capture session into multiple splits.
- Record the camera, lens, image resolution, lighting, and device. Do not tune the threshold after viewing test results.
- Each row must describe one image with a human-verified identity. A face-detection failure counts as an evaluation failure; do not remove failed cases after seeing the results.

Some research datasets do not publish a capture session for each image. In that case, leave `session_id` blank and do not invent session IDs. Use `--allow-unrecorded-sessions` only for a clearly labeled image-level benchmark. State that it does not measure independent camera sessions. Do not use this option for project-camera evaluation when capture sessions are available.

## Manifest template

Copy `face_memory_system/examples/manifest_template.csv` to the private data directory. The following example lists file names only; it does not include evaluation images:

```csv
image_path,person_id,split,session_id
gallery/known-001-a.jpg,known-001,gallery,session-01
validation/known-001-b.jpg,known-001,validation,session-02
validation/stranger-val-01-a.jpg,stranger-val-01,validation,session-03
test/known-001-c.jpg,known-001,test,session-04
test/stranger-test-01-a.jpg,stranger-test-01,test,session-05
```

Each known identity must appear in `gallery`, `validation`, and `test`. A stranger appears only in validation or test, and stranger IDs must not overlap between those splits.

## Select a threshold and report metrics

Choose the threshold on validation data only. `unknown_fpir ≤ 0.05` is an example proposed target; select the acceptable limit before running test. Freeze `model_version` and `min_margin` before testing. The test report must use the validation calibration report.

- `known_top1_accuracy`: correct known-person identifications divided by all known queries. Rejecting a known person or returning the wrong identity is an error.
- `macro_f1`: the unweighted mean F1 across known identity classes and the `Unknown` class.
- `unknown_fpir`: the share of stranger images incorrectly assigned to any enrolled person.
- Record the sample size, known and unknown counts, enrolled identities, detection or embedding failures, camera, and device.
- The image evaluation CLI measures the image-to-match path. It does not measure end-to-end latency from a live camera frame to spoken audio on a Pi.

Do not claim the 80% goal is met until an eligible test report demonstrates it. The website's default threshold is a provisional demo setting, not a threshold validated for real use.
