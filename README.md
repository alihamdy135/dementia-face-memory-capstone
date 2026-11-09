# Memento — Personal Memory Assistant

Memento is a capstone prototype that helps a caregiver identify a person from an enrolled face and recall caregiver-provided facts and conversation notes. It is not a medical device and must not be used for diagnosis, safety decisions, or unsupervised care.

The repository contains an English, left-to-right Next.js website; a FastAPI face-processing service; MongoDB-backed user accounts and memories; a Raspberry Pi 2 offline runtime; and reproducible, Python-generated evaluation figures.

## Current face-recognition benchmark

YuNet + SFace was evaluated locally on the original color images from the FEI Face Database. On the locked test split, Known Top-1 accuracy was **98.6%** (493/500), Macro F1 was **99.22%**, and Unknown FPIR was **0%** (0/700). The benchmark threshold, `0.57770098`, was selected on a separate validation split before test evaluation. The Known Top-1 result is above the project's 80% target for this benchmark.

This is a fixed-image research benchmark, not a measurement of the project's live camera, Raspberry Pi 2, or real-world caregiver workflow. FEI does not document capture sessions or camera and lens details, so no session IDs were invented. The website's default threshold, `0.45`, remains provisional and was not calibrated by this benchmark. FEI images and manifests are not included because the source permits research use but prohibits redistribution or reproduction.

See [the public benchmark report](reports/public/README.md) and the [Python-generated figures](reports/public/fei_poster_figures/README.md). All published identity labels in figures are anonymized.

## Features

- Separate accounts with scrypt password hashing and signed session cookies. People, recognitions, and memories are scoped to the signed-in account.
- Add a person with a caregiver-entered name and relationship, then enroll 1–8 images. Each image must contain exactly one face. Original uploads are processed in memory and are not retained; face embeddings and model version are stored.
- Edit or remove a person and the associated embeddings, recognition history, and conversation notes.
- Identify a person from an uploaded image or a single camera snapshot after preview. The camera does not capture automatically. The app can return known, unknown, ambiguous, no-face, multiple-face, or permission-denied outcomes.
- Record an optional voice note only after confirming the identified person and consent. Local Whisper transcription is optional. Audio is temporary; text must be reviewed and confirmed before it is saved.
- Export one selected person's face embeddings as a private JSON file for import on the Pi. Conversation history and source images are not exported.
- Evaluate with separate gallery, validation, and test data. The evaluation CLI supports threshold calibration, open-set metrics, confusion matrices, and latency reporting.
- The Pi runtime can work offline. When a network connection is available, it can upload device status, unknown-result status, and response time; it does not upload images, embeddings, or names.

## Requirements

- Node.js 20.9 or later and npm.
- Python 3.11 or later for the web model service (the standalone package supports Python 3.10+).
- MongoDB Community locally, or Docker Compose with Docker available.
- MongoDB Compass is optional.

## Run locally

From the repository root:

```bash
cp .env.example .env
```

Generate unique local values for `SESSION_SECRET` and `DEVICE_SYNC_TOKEN`; do not use the placeholders from `.env.example`:

```bash
python3 -c 'import secrets; print(secrets.token_hex(32))'
```

Set the generated values in `.env`. Start MongoDB in one of these ways.

### MongoDB with Docker

```bash
docker compose up -d mongodb
```

MongoDB data is stored in the `dementia_mongodb` volume. Compose binds its port to the local machine only.

### Existing local MongoDB

Start MongoDB on `127.0.0.1:27017` and use:

```dotenv
MONGODB_URI=mongodb://127.0.0.1:27017
MONGODB_DB=dementia_face_memory
```

MongoDB Compass can use the same URI. Open the `dementia_face_memory` database. If you change the URI, keep it consistent for the services that use MongoDB.

### Install and start the app

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ./face_memory_system
npm install
python face_memory_system/models/download_models.py
```

The model download script fetches the pinned YuNet and SFace model files and checks their SHA-256 digests. The model weights stay local and are excluded from Git.

In terminal 1, start the face-processing service:

```bash
source .venv/bin/activate
uvicorn face_memory.http_service:app --host 127.0.0.1 --port 8001 --workers 1
```

In terminal 2, start Next.js:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) and create a private account. Camera access is available on `localhost` after browser permission is granted. Check model readiness at [http://localhost:3000/api/health](http://localhost:3000/api/health). A `provisional_not_calibrated` status means the app's default threshold has not been calibrated for your camera.

### Optional local Whisper transcription

Transcription is unavailable unless Whisper and FFmpeg are installed. On a machine with enough memory and processing capacity:

```bash
sudo apt install ffmpeg
source .venv/bin/activate
python -m pip install openai-whisper scipy
```

Whisper downloads its model on first use. Browser recordings are kept temporarily in memory, sent for transcription, then deleted by the app and service. Confirm transcription behavior on the target device before presenting it.

## Evaluation and poster figures

Read the [consented data-collection guide](docs/data-collection.md). Start with [the manifest template](face_memory_system/examples/manifest_template.csv) and keep images, manifests, and detailed per-run reports under `private_data/` only. Required columns are `image_path,person_id,split,session_id`. Use random IDs, not real names.

Calibrate the operating threshold on validation data first. The 5% unknown FPIR below is an example proposed constraint; decide the acceptable value before viewing test results.

```bash
source .venv/bin/activate
face-memory-evaluate \
  --manifest private_data/manifest.csv \
  --mode calibrate \
  --max-unknown-fpir 0.05 \
  --camera "camera and lens description" \
  --device "laptop model and specifications" \
  --output private_data/reports/validation.json
```

Run test once using the locked validation report and unchanged model settings:

```bash
face-memory-evaluate \
  --manifest private_data/manifest.csv \
  --mode test \
  --validation-report private_data/reports/validation.json \
  --camera "camera and lens description" \
  --device "laptop model and specifications" \
  --output private_data/reports/test.json
```

The CLI creates a detailed JSON report and aggregate poster files. Keep detailed reports private if they contain IDs or local file paths. Only the anonymized aggregate results and figures under `reports/public/` belong in the public repository.

## Raspberry Pi 2

From a person's card in the website, choose **Export to Pi**. Transfer the resulting private JSON file to the Pi using a trusted local method, then import and try a local test image:

```bash
python pi/face_memory_pi.py \
  --import-person /path/to/pi-person-<id>.json \
  --image /path/to/local-test.jpg
```

The [Raspberry Pi 2 guide](pi/README.md) covers the operating system, camera and audio wiring, offline operation, event sync, and systemd setup. Pi latency and audio response measurements remain unmeasured until they are collected on the actual Pi 2 hardware.

## Deploy on Vercel and connect MongoDB Atlas

The repository includes a `vercel.json` Services configuration for the Next.js app and a private FastAPI container. On the Vercel import screen shown in the project setup guide, refresh the repository scan after the GitHub update and choose **Import multi-service project**. Do not import the two folders as separate projects for this configuration.

Expand **Environment Variables** in the import form. Add `MONGODB_URI` and paste the Atlas application connection string into its value. Also add `MONGODB_DB` with `dementia_face_memory`, a unique production `SESSION_SECRET`, `DEVICE_SYNC_TOKEN`, and `MODEL_SERVICE_TOKEN`. The `MODEL_SERVICE_TOKEN` value must be identical for the Next.js app and the face-model service. The `MODEL_SERVICE_URL` value is generated automatically by the private Vercel service binding; do not paste a local `127.0.0.1` URL there.

The Atlas URI is a secret. Store it in Vercel's environment variables, never in GitHub, a source file, or a message. See [the deployment guide](docs/vercel-deployment.md) for the exact variable scopes and follow-up checks. Vercel Services and its container runtime are currently beta; verify the plan and deployment limits in your Vercel account before relying on them for a live service.

The repository is prepared for the Vercel import, but this commit does not create or deploy a Vercel project. The Atlas database and model service must be configured and connected in your Vercel project.

## Hardware, privacy, and licensing

- The prototype is not a clinical or safety system. A caregiver must confirm a match before any personal information or audio is used.
- Face embeddings are biometric data. Keep the database private and apply access controls. Do not commit `.env`, database backups, face images, embeddings, voice recordings, or person-export JSON files.
- The FEI Face Database is provided for research use and may not be redistributed or reproduced. The original images, archives, and manifest are excluded from this repository.
- YuNet and SFace model sources, license files, pinned revisions, and SHA-256 hashes are documented in [the model notes](face_memory_system/models/MODELS.md). Model files are downloaded locally and verified before use.
- `Insight .pdf` and the inherited prototype archive are not included in the public repository.

