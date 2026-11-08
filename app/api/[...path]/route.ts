import { createHash, timingSafeEqual } from "node:crypto";
import { ObjectId } from "mongodb";
import { NextRequest, NextResponse } from "next/server";
import { currentUser, clearSession, hashPassword, setSession, verifyPassword } from "@/web/lib/auth";
import { database } from "@/web/lib/db";
import { ModelError, recognizeImage, transcribeAudio, encodeImage } from "@/web/lib/model";
import { MODEL_VERSION } from "@/web/lib/model-settings";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type PersonDocument = {
  _id?: ObjectId;
  ownerId: ObjectId;
  name: string;
  relationship: string;
  templates: Array<{ embedding: number[]; modelVersion: string; createdAt: Date }>;
  createdAt: Date;
  updatedAt: Date;
};

const json = (data: unknown, status = 200) => NextResponse.json(data, { status });
const objectId = (value: string) => ObjectId.isValid(value) ? new ObjectId(value) : null;

function modelError(error: unknown): NextResponse {
  if (!(error instanceof ModelError)) return json({ error: "model_unavailable" }, 503);
  const messages: Record<string, string> = {
    no_face: "no_face",
    multiple_faces: "multiple_faces",
    invalid_image: "invalid_image",
    image_too_large: "image_too_large",
    transcription_unavailable: "transcription_unavailable",
    transcription_audio_resampler_unavailable: "transcription_unavailable",
    transcription_failed: "transcription_failed",
  };
  const status = error.status === 422 || error.status === 413 ? error.status : 503;
  return json({ error: messages[error.code] ?? error.code }, status);
}

async function requireUser() {
  const user = await currentUser();
  return user ? { user, db: await database() } : null;
}

async function auth(method: string, path: string[], request: NextRequest) {
  if (method === "GET" && path[0] === "me") {
    const user = await currentUser();
    return json({ user: user ? { email: user.email } : null });
  }
  if (method === "POST" && path[0] === "logout") {
    await clearSession();
    return json({ ok: true });
  }
  const users = (await database()).collection("users");
  if (method === "POST" && (path[0] === "register" || path[0] === "login")) {
    const body = await request.json().catch(() => ({})) as { email?: string; password?: string };
    const email = (body.email ?? "").trim().toLowerCase();
    const password = body.password ?? "";
    if (!/^\S+@\S+\.\S+$/.test(email) || password.length < 10 || password.length > 160) {
      return json({ error: "invalid_credentials_format" }, 400);
    }
    await users.createIndex({ email: 1 }, { unique: true });
    if (path[0] === "register") {
      if (await users.findOne({ email })) return json({ error: "email_already_registered" }, 409);
      const result = await users.insertOne({ email, passwordHash: await hashPassword(password), createdAt: new Date() });
      await setSession(result.insertedId);
      return json({ user: { email } }, 201);
    }
    const user = await users.findOne({ email });
    if (!user || !await verifyPassword(password, String(user.passwordHash))) {
      return json({ error: "invalid_email_or_password" }, 401);
    }
    await setSession(user._id as ObjectId);
    return json({ user: { email } });
  }
  return json({ error: "not_found" }, 404);
}

function safePerson(person: PersonDocument) {
  return {
    id: person._id?.toHexString() ?? "",
    name: person.name,
    relationship: person.relationship,
    photoCount: person.templates?.filter((item) => item.modelVersion === MODEL_VERSION).length ?? 0,
    createdAt: person.createdAt,
    updatedAt: person.updatedAt,
  };
}

async function people(method: string, path: string[], request: NextRequest) {
  const auth = await requireUser();
  if (!auth) return json({ error: "unauthorized" }, 401);
  const { user, db } = auth;
  const collection = db.collection<PersonDocument>("people");
  if (path.length === 0 && method === "GET") {
    const rows = await collection.find({ ownerId: user._id }).sort({ updatedAt: -1 }).toArray();
    return json({ people: rows.map(safePerson) });
  }
  if (path.length === 0 && method === "POST") {
    const body = await request.json().catch(() => ({})) as { name?: string; relationship?: string };
    const name = (body.name ?? "").trim();
    const relationship = (body.relationship ?? "").trim();
    if (!name || !relationship || name.length > 80 || relationship.length > 80) {
      return json({ error: "name_and_relationship_required" }, 400);
    }
    const now = new Date();
    const result = await collection.insertOne({ ownerId: user._id, name, relationship, templates: [], createdAt: now, updatedAt: now });
    return json({ person: { id: result.insertedId.toHexString(), name, relationship, photoCount: 0, createdAt: now } }, 201);
  }
  const id = objectId(path[0] ?? "");
  if (!id) return json({ error: "not_found" }, 404);
  const filter = { _id: id, ownerId: user._id };
  if (path.length === 1 && method === "PATCH") {
    const body = await request.json().catch(() => ({})) as { name?: string; relationship?: string };
    const update: { name?: string; relationship?: string; updatedAt: Date } = { updatedAt: new Date() };
    if (typeof body.name === "string" && body.name.trim()) update.name = body.name.trim().slice(0, 80);
    if (typeof body.relationship === "string" && body.relationship.trim()) update.relationship = body.relationship.trim().slice(0, 80);
    if (!update.name && !update.relationship) return json({ error: "nothing_to_update" }, 400);
    const result = await collection.findOneAndUpdate(filter, { $set: update }, { returnDocument: "after" });
    return result ? json({ person: safePerson(result) }) : json({ error: "not_found" }, 404);
  }
  if (path.length === 1 && method === "DELETE") {
    const result = await collection.deleteOne(filter);
    if (!result.deletedCount) return json({ error: "not_found" }, 404);
    await Promise.all([
      db.collection("recognitions").deleteMany({ ownerId: user._id, personId: id }),
      db.collection("memories").deleteMany({ ownerId: user._id, personId: id }),
    ]);
    return json({ ok: true });
  }
  if (path[1] === "photos" && method === "POST") {
    const person = await collection.findOne(filter);
    if (!person) return json({ error: "not_found" }, 404);
    const form = await request.formData();
    const photos = form.getAll("photos").filter((item): item is File => item instanceof File);
    if (!photos.length || photos.length > 8) return json({ error: "upload_between_1_and_8_photos" }, 400);
    if (person.templates.some((item) => item.modelVersion !== MODEL_VERSION)) {
      return json({ error: "model_version_mismatch_re_enroll_required" }, 409);
    }
    const outcomes = [] as Array<{ name: string; accepted: boolean; reason?: string }>;
    const embeddings = [] as Array<{ embedding: number[]; modelVersion: string; createdAt: Date }>;
    for (const photo of photos) {
      if (photo.size > 10 * 1024 * 1024 || !["image/jpeg", "image/png", "image/webp"].includes(photo.type)) {
        outcomes.push({ name: photo.name.slice(0, 100), accepted: false, reason: "invalid_image" });
        continue;
      }
      try {
        const encoded = await encodeImage(Buffer.from(await photo.arrayBuffer()));
        embeddings.push({ embedding: encoded.embedding, modelVersion: encoded.model_version, createdAt: new Date() });
        outcomes.push({ name: photo.name.slice(0, 100), accepted: true });
      } catch (error) {
        const reason = error instanceof ModelError ? error.code : "model_unavailable";
        outcomes.push({ name: photo.name.slice(0, 100), accepted: false, reason });
      }
    }
    if (embeddings.length) await collection.updateOne(filter, { $push: { templates: { $each: embeddings } }, $set: { updatedAt: new Date() } });
    return json({ outcomes, acceptedCount: embeddings.length, modelVersion: MODEL_VERSION });
  }
  if (path[1] === "export" && method === "GET") {
    const person = await collection.findOne(filter);
    if (!person) return json({ error: "not_found" }, 404);
    const templates = person.templates.filter((item) => item.modelVersion === MODEL_VERSION).map((item) => item.embedding);
    if (!templates.length) return json({ error: "person_has_no_compatible_photos" }, 409);
    return json({ schemaVersion: 1, exportedAt: new Date().toISOString(), modelVersion: MODEL_VERSION,
      person: { personId: person._id.toHexString(), name: person.name, relationship: person.relationship, templates } });
  }
  return json({ error: "not_found" }, 404);
}

async function workspace(path: string[], method: string, request: NextRequest) {
  const auth = await requireUser();
  if (!auth) return json({ error: "unauthorized" }, 401);
  const { user, db } = auth;
  if (path[0] === "dashboard" && method === "GET") {
    const [peopleRows, recognitionRows, memories] = await Promise.all([
      db.collection<PersonDocument>("people").find({ ownerId: user._id }).sort({ updatedAt: -1 }).toArray(),
      db.collection("recognitions").find({ ownerId: user._id }).sort({ createdAt: -1 }).limit(8).toArray(),
      db.collection("memories").find({ ownerId: user._id }).sort({ createdAt: -1 }).limit(8).toArray(),
    ]);
    return json({ people: peopleRows.map(safePerson), recognitions: recognitionRows.map((row) => ({
      id: row._id.toString(), status: row.status, personName: row.personName ?? null, score: row.score ?? null, createdAt: row.createdAt,
    })), memories: memories.map((row) => ({ id: row._id.toString(), personName: row.personName, content: row.content, createdAt: row.createdAt })) });
  }
  if (path[0] === "recognize" && method === "POST") {
    const form = await request.formData();
    const image = form.get("image");
    if (!(image instanceof File)) return json({ error: "image_required" }, 400);
    if (image.size > 10 * 1024 * 1024 || !["image/jpeg", "image/png", "image/webp"].includes(image.type)) return json({ error: "invalid_image" }, 400);
    try {
      const rows = await db.collection<PersonDocument>("people").find({ ownerId: user._id }).toArray();
      const peopleById = new Map(rows.map((person) => [person._id.toHexString(), person]));
      const gallery: Record<string, number[][]> = {};
      for (const person of rows) {
        const compatible = person.templates.filter((item) => item.modelVersion === MODEL_VERSION).map((item) => item.embedding);
        if (compatible.length) gallery[person._id.toHexString()] = compatible;
      }
      const match = await recognizeImage(Buffer.from(await image.arrayBuffer()), gallery);
      const matchedPerson = match.person_id ? peopleById.get(match.person_id) : undefined;
      const result = {
        ...match,
        status: match.status === "identified" && matchedPerson ? "known" : match.status === "identified" ? "unknown" : match.status,
        person: match.status === "identified" && matchedPerson ? { id: matchedPerson._id.toHexString(), name: matchedPerson.name, relationship: matchedPerson.relationship } : null,
        thresholdStatus: match.threshold_status,
      };
      await db.collection("recognitions").insertOne({ ownerId: user._id, personId: matchedPerson?._id ?? null,
        personName: matchedPerson?.name ?? null, status: result.status, score: match.score, secondScore: match.second_score,
        modelVersion: match.model_version, thresholdStatus: match.threshold_status, createdAt: new Date() });
      return json(result);
    } catch (error) { return modelError(error); }
  }
  if (path[0] === "memories" && method === "GET") {
    const requestedId = request.nextUrl.searchParams.get("personId");
    const requestedObjectId = requestedId ? objectId(requestedId) : null;
    const person = requestedObjectId ? await db.collection("people").findOne({ _id: requestedObjectId, ownerId: user._id }) : null;
    if (!person) return json({ memories: [] });
    const memories = await db.collection("memories").find({ ownerId: user._id, personId: person._id }).sort({ createdAt: -1 }).limit(100).toArray();
    return json({ memories: memories.map((item) => ({ id: item._id.toString(), content: item.content, createdAt: item.createdAt })) });
  }
  if (path[0] === "memories" && method === "POST") {
    const body = await request.json().catch(() => ({})) as { personId?: string; content?: string };
    const id = objectId(body.personId ?? "");
    const content = (body.content ?? "").trim();
    if (!id || !content || content.length > 5000) return json({ error: "person_and_transcript_required" }, 400);
    const person = await db.collection("people").findOne({ _id: id, ownerId: user._id });
    if (!person) return json({ error: "not_found" }, 404);
    const result = await db.collection("memories").insertOne({ ownerId: user._id, personId: id,
      personName: person.name, content, source: "confirmed_local_transcription", createdAt: new Date() });
    return json({ id: result.insertedId.toString(), saved: true }, 201);
  }
  if (path[0] === "transcribe" && method === "POST") {
    const form = await request.formData();
    const audio = form.get("audio");
    if (!(audio instanceof File) || audio.size > 18 * 1024 * 1024) return json({ error: "invalid_audio" }, 400);
    try { return json({ text: await transcribeAudio(Buffer.from(await audio.arrayBuffer())) }); }
    catch (error) { return modelError(error); }
  }
  return json({ error: "not_found" }, 404);
}

async function deviceEvents(method: string, request: NextRequest) {
  if (method !== "POST") return json({ error: "method_not_allowed" }, 405);
  const configured = process.env.DEVICE_SYNC_TOKEN ?? "";
  const supplied = request.headers.get("authorization")?.replace(/^Bearer\s+/i, "") ?? "";
  const expectedHash = createHash("sha256").update(configured).digest();
  const suppliedHash = createHash("sha256").update(supplied).digest();
  if (!configured || !timingSafeEqual(expectedHash, suppliedHash)) return json({ error: "unauthorized" }, 401);
  const body = await request.json().catch(() => ({})) as { deviceId?: string; eventType?: string; status?: string; responseMs?: number; observedAt?: string };
  if (!body.deviceId || !body.eventType || !body.status) return json({ error: "invalid_event" }, 400);
  const responseMs = body.responseMs === null || body.responseMs === undefined ? Number.NaN : Number(body.responseMs);
  await (await database()).collection("deviceEvents").insertOne({
    deviceId: body.deviceId.slice(0, 80), eventType: body.eventType.slice(0, 40), status: body.status.slice(0, 40),
    responseMs: Number.isFinite(responseMs) && responseMs >= 0 ? responseMs : null,
    observedAt: body.observedAt && !Number.isNaN(Date.parse(body.observedAt)) ? new Date(body.observedAt) : new Date(),
    receivedAt: new Date(),
  });
  return json({ queued: true }, 202);
}

export async function GET(request: NextRequest) { return dispatch("GET", request); }
export async function POST(request: NextRequest) { return dispatch("POST", request); }
export async function PATCH(request: NextRequest) { return dispatch("PATCH", request); }
export async function DELETE(request: NextRequest) { return dispatch("DELETE", request); }

async function dispatch(method: string, request: NextRequest) {
  const parts = request.nextUrl.pathname.split("/").slice(2).map(decodeURIComponent);
  if (parts[0] === "auth") return auth(method, parts.slice(1), request);
  if (parts[0] === "people") return people(method, parts.slice(1), request);
  if (["dashboard", "recognize", "memories", "transcribe"].includes(parts[0] ?? "")) return workspace(parts, method, request);
  if (parts[0] === "device" && parts[1] === "events") return deviceEvents(method, request);
  if (parts[0] === "health" && method === "GET") {
    const base = (process.env.MODEL_SERVICE_URL ?? "http://127.0.0.1:8001").replace(/\/$/, "");
    try {
      const response = await fetch(`${base}/health`, { cache: "no-store", signal: AbortSignal.timeout(2500) });
      return json(await response.json(), response.status);
    } catch { return json({ status: "model_service_unavailable", model_version: MODEL_VERSION }, 503); }
  }
  return json({ error: "not_found" }, 404);
}
