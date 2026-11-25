// GET /api/me  (Authorization: Bearer <token>)  ->  {ok, role, name, canChangePassword}
import { readToken, who, json } from "../../lib/auth.js";

export async function onRequestGet({ request, env }) {
  const t = env.OWNER_HASH ? await readToken(env, request) : null;
  return t ? json({ ok: true, ...who(t.r) }) : json({ ok: false }, 401);
}
