// GET /api/health  ->  {"ok":true,...}
// First backend endpoint. Shared live data, admin login and alerts
// (Telegram to captains and officials) will be added next to this file.
export function onRequestGet({ env }) {
  return Response.json(
    { ok: true, app: "BlastBhai", event: "ICB 2026", backend: "cloudflare-pages-functions",
      store: env.ICB_KV ? "kv-bound" : "none-yet" },
    { headers: { "Cache-Control": "no-store" } }
  );
}
