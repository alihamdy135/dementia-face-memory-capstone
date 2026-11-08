import { IDENTITY_THRESHOLD, MIN_MARGIN } from "@/web/lib/model-settings";

const MODEL_URL = (process.env.MODEL_SERVICE_URL ?? "http://127.0.0.1:8001").replace(/\/$/, "");

export type MatchPayload = {
  status: "identified" | "unknown" | "ambiguous";
  person_id: string | null;
  score: number;
  second_score: number;
  margin: number;
  model_version: string;
  threshold_status: string;
};

async function callModel(path: string, init: RequestInit): Promise<Response> {
  const headers = new Headers(init.headers);
  if (process.env.MODEL_SERVICE_TOKEN) headers.set("x-model-token", process.env.MODEL_SERVICE_TOKEN);
  return fetch(`${MODEL_URL}${path}`, { ...init, headers, cache: "no-store", signal: AbortSignal.timeout(45_000) });
}

export async function encodeImage(bytes: Buffer): Promise<{ embedding: number[]; model_version: string }> {
  const response = await callModel("/encode", {
    method: "POST",
    headers: { "content-type": "application/octet-stream" },
    body: new Uint8Array(bytes),
  });
  const payload = await response.json().catch(() => ({})) as { detail?: string; embedding?: number[]; model_version?: string };
  if (!response.ok) throw new ModelError(payload.detail ?? "model_unavailable", response.status);
  if (!payload.embedding || !payload.model_version) throw new ModelError("model_unavailable", 503);
  return { embedding: payload.embedding, model_version: payload.model_version };
}

export async function recognizeImage(
  bytes: Buffer,
  gallery: Record<string, number[][]>,
): Promise<MatchPayload> {
  const response = await callModel("/recognize", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      image_base64: bytes.toString("base64"),
      gallery,
      threshold: IDENTITY_THRESHOLD,
      min_margin: MIN_MARGIN,
    }),
  });
  const payload = await response.json().catch(() => ({})) as MatchPayload & { detail?: string };
  if (!response.ok) throw new ModelError(payload.detail ?? "model_unavailable", response.status);
  return payload;
}

export async function transcribeAudio(bytes: Buffer): Promise<string> {
  const response = await callModel("/transcribe", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ audio_base64: bytes.toString("base64") }),
  });
  const payload = await response.json().catch(() => ({})) as { detail?: string; text?: string };
  if (!response.ok) throw new ModelError(payload.detail ?? "transcription_unavailable", response.status);
  return payload.text ?? "";
}

export class ModelError extends Error {
  constructor(public readonly code: string, public readonly status: number) { super(code); }
}

export const MODEL_DEFAULTS = { threshold: IDENTITY_THRESHOLD, minMargin: MIN_MARGIN };
