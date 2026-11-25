// POST /api/login  {username, password}  ->  {ok, token, role, name, canChangePassword}
import { OWNER_USER, ADMIN_USER, normUser, checkHash, adminHash, makeToken, who,
         tooManyFails, noteFail, clearFails, json, readJson } from "../../lib/auth.js";

export async function onRequestPost({ request, env }) {
  if (!env.OWNER_HASH) return json({ ok: false, error: "not-configured" }, 503);
  const { username, password } = await readJson(request);
  const u = normUser(username);
  if (await tooManyFails(env, request, u)) return json({ ok: false, error: "too-many" }, 429);
  let role = null;
  if (u === OWNER_USER && (await checkHash(password, env.OWNER_HASH))) role = "owner";
  else if (u === ADMIN_USER && (await checkHash(password, await adminHash(env)))) role = "admin";
  if (!role) {
    await noteFail(env, request, u);
    return json({ ok: false, error: "wrong" }, 401);
  }
  await clearFails(env, request, u);
  return json({ ok: true, token: await makeToken(env, role), ...who(role) });
}
