// Shared login helpers for the /api functions (Cloudflare Pages Functions).
//
// Secrets (Cloudflare dashboard → Settings → Variables and Secrets, type "Secret"):
//   OWNER_HASH  hash of the owner's password   (owner username: ZHIMON)
//   ADMIN_HASH  hash of the first general admin password (username: ICB)
// KV binding ICB_KV (optional but needed to change the admin password and to
// slow down guessing). Hashes are made with tools/make-hash.mjs.
//
// Rules: usernames are compared in CAPITALS, passwords in small letters.

export const OWNER_USER = "ZHIMON";
export const OWNER_NAME = "Zhimon";
export const ADMIN_USER = "ICB";
const ITER = 100000;                 // Cloudflare's PBKDF2 maximum
const SESSION_SECONDS = 12 * 3600;
const MAX_FAILS = 10, FAIL_WINDOW = 15 * 60;

export const normUser = (u) => String(u || "").trim().toUpperCase();
export const normPass = (p) => String(p || "").trim().toLowerCase();

const enc = new TextEncoder();
const b64 = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf)));
const unb64 = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
const b64url = (s) => btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const unb64url = (s) => atob(s.replace(/-/g, "+").replace(/_/g, "/"));

async function pbkdf2(pass, salt, iter) {
  const key = await crypto.subtle.importKey("raw", enc.encode(pass), "PBKDF2", false, ["deriveBits"]);
  return crypto.subtle.deriveBits({ name: "PBKDF2", hash: "SHA-256", salt, iterations: iter }, key, 256);
}

export async function makeHash(pass) {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  return `pbkdf2$${ITER}$${b64(salt)}$${b64(await pbkdf2(normPass(pass), salt, ITER))}`;
}

function same(a, b) {               // constant-time compare
  if (a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

export async function checkHash(pass, stored) {
  const [kind, iter, salt, hash] = String(stored || "").split("$");
  if (kind !== "pbkdf2" || !hash) return false;
  return same(b64(await pbkdf2(normPass(pass), unb64(salt), +iter)), hash);
}

export async function adminHash(env) {
  return (env.ICB_KV && (await env.ICB_KV.get("admin_hash"))) || env.ADMIN_HASH || "";
}

// ---- signed session tokens (no database needed) ----
async function hmacKey(env) {
  const secret = env.SESSION_SECRET || env.OWNER_HASH;
  if (!secret) throw new Error("not configured");
  return crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
}
async function sign(env, data) {
  return b64url(String.fromCharCode(...new Uint8Array(await crypto.subtle.sign("HMAC", await hmacKey(env), enc.encode(data)))));
}
// A general-admin token carries a fingerprint of the admin password, so it
// stops working as soon as the owner changes that password.
const fp = (h) => h.slice(-12);

export async function makeToken(env, role) {
  const body = { r: role, exp: Math.floor(Date.now() / 1000) + SESSION_SECONDS };
  if (role === "admin") body.v = fp(await adminHash(env));
  const data = b64url(JSON.stringify(body));
  return `${data}.${await sign(env, data)}`;
}

export async function readToken(env, request) {
  const m = /^Bearer\s+(\S+)$/.exec(request.headers.get("Authorization") || "");
  if (!m) return null;
  const [data, sig] = m[1].split(".");
  if (!data || !sig || !same(await sign(env, data), sig)) return null;
  let body;
  try { body = JSON.parse(unb64url(data)); } catch { return null; }
  if (!body || body.exp < Date.now() / 1000) return null;
  if (body.r === "admin" && body.v !== fp(await adminHash(env))) return null;
  if (body.r !== "admin" && body.r !== "owner") return null;
  return body;
}

export const who = (role) =>
  role === "owner" ? { role, name: OWNER_NAME, canChangePassword: true } : { role, name: "Admin", canChangePassword: false };

// ---- slow down password guessing (needs KV) ----
// Counted per connection AND per username: at the venue everyone shares one
// internet address, so someone guessing "ICB" must not lock the owner out.
const failKey = (request, user) =>
  "fail:" + (request.headers.get("CF-Connecting-IP") || "local") + ":" + (user === OWNER_USER ? "owner" : "other");
export async function tooManyFails(env, request, user) {
  if (!env.ICB_KV) return false;
  return (+(await env.ICB_KV.get(failKey(request, user))) || 0) >= MAX_FAILS;
}
export async function noteFail(env, request, user) {
  if (!env.ICB_KV) return;
  const k = failKey(request, user), n = (+(await env.ICB_KV.get(k)) || 0) + 1;
  await env.ICB_KV.put(k, String(n), { expirationTtl: FAIL_WINDOW });
}
export async function clearFails(env, request, user) {
  if (env.ICB_KV) await env.ICB_KV.delete(failKey(request, user));
}

export const json = (data, status = 200) =>
  Response.json(data, { status, headers: { "Cache-Control": "no-store" } });

export async function readJson(request) {
  try { return await request.json(); } catch { return {}; }
}
