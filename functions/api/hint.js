// GET /api/hint -> {ok, show}
// show = true while the general admin password is still the first (test) one,
// i.e. the owner has not changed it yet. The app then shows the test login on
// the sign-in screen and in the guided tour; after a change it disappears by itself.
import { json } from "../../lib/auth.js";

export async function onRequestGet({ env }) {
  const changed = env.ICB_KV ? !!(await env.ICB_KV.get("admin_hash")) : false;
  return json({ ok: true, show: !changed });
}
