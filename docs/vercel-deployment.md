# Deploy with Vercel Services and MongoDB Atlas

The repository is configured as one Vercel multi-service project. The `app` service is the public Next.js website and API. The `face-model` service is a private FastAPI container, reached from Next.js through a Vercel service binding. MongoDB Atlas is used by the Next.js API; the model service does not connect to MongoDB.

Vercel Services and the container runtime are currently beta. Check availability, plan limits, and pricing in your Vercel account before relying on this setup for a live service.

## Import the repository

1. Push the latest `main` branch to GitHub and refresh the repository scan on the Vercel import page.
2. Confirm the root `vercel.json` is present and choose **Import multi-service project**.
3. Keep the repository root as the project root. Do not import `app` and `face_memory_system` as separate projects; the binding connects them inside the same deployment.
4. Expand **Environment Variables** before importing, or add the same values later in Project Settings → Environment Variables.

The `face-model` service is not publicly routed. Only the Next.js app is exposed to visitors. Its binding injects the URL into `MODEL_SERVICE_URL` at runtime.

## Add environment variables

Set these variables for the environments you will deploy. Use separate random secrets for production and preview where practical.

| Name | Value | Used by |
| --- | --- | --- |
| `MONGODB_URI` | Atlas application connection string from Atlas → Connect → Drivers. Replace the password placeholder with the database user's password. | Next.js app |
| `MONGODB_DB` | `dementia_face_memory` | Next.js app |
| `SESSION_SECRET` | A unique random secret, at least 32 random bytes. Do not reuse the example or local development value. | Next.js app |
| `DEVICE_SYNC_TOKEN` | A separate long random token for optional Raspberry Pi event sync. | Next.js app |
| `MODEL_SERVICE_TOKEN` | A long random token; set the identical value for Next.js and the `face-model` service. | Next.js app and face model |
| `MODEL_SERVICE_URL` | Provided automatically by the service binding in `vercel.json`. Do not set this manually in Vercel. | Next.js app |

Generate a random secret locally and paste it directly into the Vercel value field. Never put secrets in GitHub, `vercel.json`, a source file, or a message:

```bash
python3 -c 'import secrets; print(secrets.token_hex(32))'
```

Use the Atlas URI in `MONGODB_URI`. The code selects the database using `MONGODB_DB`; it defaults to `dementia_face_memory`. A typical Atlas URI looks like this:

```text
mongodb+srv://<database-user>:<url-encoded-password>@<cluster-host>/dementia_face_memory?retryWrites=true&w=majority
```

The Atlas password must be URL-encoded if it contains reserved characters. Do not share the completed URI in chat or commit it. In the Vercel import form, the variable name is `MONGODB_URI` and the complete URI goes in its **Value** field.

The Dockerfile listens on port 80 by default, matching Vercel's container routing. `docker-compose.yml` overrides the port for local container use.

## Atlas network access

The Atlas cluster must accept connections from the Vercel runtime. Prefer a Vercel static egress IP or an appropriate private networking option when available on your plan. If the app cannot connect, check Atlas Network Access and the Vercel outbound networking options for this project. Avoid leaving a broad `0.0.0.0/0` rule enabled as a default.

## Before using a live deployment

- Confirm the deployment build shows both services and the face-model service starts successfully.
- Check `https://<your-domain>/api/health`; it should report that the face model is ready.
- Create two separate accounts and confirm each account sees only its own people and memories.
- Check person enrollment, image recognition, unauthenticated requests, and optional transcription using authorized sample images.
- Keep Atlas backups private. The database contains biometric face embeddings and account data.
- Treat the `0.45` website threshold as provisional until it is calibrated and evaluated with consented images from the intended camera and device. FEI fixed-image benchmark results do not establish live-camera or Raspberry Pi 2 performance.

The local application and source configuration are ready for Vercel import. This guide does not mean that a Vercel project has already been created or deployed.
