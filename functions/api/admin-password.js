// POST /api/admin-password  {newPassword}   (owner only)
// Changes the password of the general admin account (username ICB) for everyone.
import { readToken, makeHash, normPass, json, readJson } from "../../lib/auth.js";

export async function onRequestPost({ request, env }) {
  const t = env.OWNER_HASH ? await readToken(env, request) : null;
  if (!t) return json({ ok: false, error: "signed-out" }, 401);
  if (t.r !== "owner") return json({ ok: false, error: "owner-only" }, 403);
  if (!env.ICB_KV) return json({ ok: false, error: "no-storage" }, 503);
  const p = normPass((await readJson(request)).newPassword);
  if (p.length < 6) return json({ ok: false, error: "too-short" }, 400);
  await env.ICB_KV.put("admin_hash", await makeHash(p));
  return json({ ok: true });
}
