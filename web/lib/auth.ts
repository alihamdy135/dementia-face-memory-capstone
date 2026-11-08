import { createHmac, randomBytes, scrypt as scryptCallback, timingSafeEqual } from "node:crypto";
import { promisify } from "node:util";
import { cookies } from "next/headers";
import { ObjectId } from "mongodb";
import { database } from "@/web/lib/db";

const scrypt = promisify(scryptCallback);
const COOKIE = "face_memory_session";
const DAY = 60 * 60 * 24;

type SessionPayload = { sub: string; exp: number };

function sessionSecret(): string {
  const secret = process.env.SESSION_SECRET;
  if (!secret || secret.length < 32) throw new Error("SESSION_SECRET must contain at least 32 characters");
  return secret;
}

function signature(value: string): string {
  return createHmac("sha256", sessionSecret()).update(value).digest("base64url");
}

export async function hashPassword(password: string): Promise<string> {
  const salt = randomBytes(16);
  const derived = (await scrypt(password, salt, 64)) as Buffer;
  return `${salt.toString("hex")}:${derived.toString("hex")}`;
}

export async function verifyPassword(password: string, stored: string): Promise<boolean> {
  const [saltHex, hashHex] = stored.split(":");
  if (!saltHex || !hashHex) return false;
  const expected = Buffer.from(hashHex, "hex");
  const actual = (await scrypt(password, Buffer.from(saltHex, "hex"), expected.length)) as Buffer;
  return expected.length === actual.length && timingSafeEqual(expected, actual);
}

export async function setSession(userId: ObjectId): Promise<void> {
  const payload: SessionPayload = { sub: userId.toHexString(), exp: Math.floor(Date.now() / 1000) + DAY * 14 };
  const encoded = Buffer.from(JSON.stringify(payload)).toString("base64url");
  const value = `${encoded}.${signature(encoded)}`;
  const jar = await cookies();
  jar.set(COOKIE, value, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: DAY * 14,
  });
}

export async function clearSession(): Promise<void> {
  const jar = await cookies();
  jar.delete(COOKIE);
}

export async function currentUser(): Promise<{ _id: ObjectId; email: string } | null> {
  const jar = await cookies();
  const token = jar.get(COOKIE)?.value;
  if (!token) return null;
  const [encoded, supplied] = token.split(".");
  if (!encoded || !supplied) return null;
  const expected = signature(encoded);
  const left = Buffer.from(expected);
  const right = Buffer.from(supplied);
  if (left.length !== right.length || !timingSafeEqual(left, right)) return null;
  try {
    const payload = JSON.parse(Buffer.from(encoded, "base64url").toString("utf8")) as SessionPayload;
    if (payload.exp <= Date.now() / 1000 || !ObjectId.isValid(payload.sub)) return null;
    const user = await (await database()).collection("users").findOne(
      { _id: new ObjectId(payload.sub) }, { projection: { email: 1 } },
    );
    return user ? { _id: user._id as ObjectId, email: String(user.email) } : null;
  } catch {
    return null;
  }
}
