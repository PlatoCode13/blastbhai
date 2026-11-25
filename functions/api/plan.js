// Match-day plan shared by everyone: breaks, start/close times, match length,
// turnover, knockout format.
//   GET  /api/plan            -> {ok, plan|null, v}
//   POST /api/plan {plan}     -> {ok, v}     (signed-in admin or owner)
import { readToken, json, readJson } from "../../lib/auth.js";

const int = (x, lo, hi) => Number.isInteger(x) && x >= lo && x <= hi;

function cleanPlan(p) {
  if (!p || typeof p !== "object") return null;
  const dp = p.dp;
  if (!dp || typeof dp !== "object") return null;
  const day = (a) => Array.isArray(a) && a.length === 2 && a.every((x) => int(x, 0, 1440));
  if (!int(dp.d1, 0, 20) || !day(dp.start) || !day(dp.close)) return null;
  if (!Array.isArray(dp.br) || dp.br.length !== 2) return null;
  const br = [];
  for (const list of dp.br) {
    if (!Array.isArray(list) || list.length > 12) return null;
    const out = [];
    for (const b of list) {
      if (!b || typeof b.l !== "string" || !int(b.a, 0, 20) || !int(b.m, 0, 240)) return null;
      out.push({ l: b.l.slice(0, 40), a: b.a, m: b.m });
    }
    br.push(out);
  }
  if (!int(p.len, 20, 120) || !int(p.ch, 0, 30)) return null;
  if (typeof p.alone !== "boolean" || !["A", "B", "C"].includes(p.fmt) || ![4, 5].includes(p.mpt)) return null;
  return { dp: { d1: dp.d1, start: dp.start, close: dp.close, br }, len: p.len, ch: p.ch, alone: p.alone, fmt: p.fmt, mpt: p.mpt };
}

export async function onRequestGet({ env }) {
  if (!env.ICB_KV) return json({ ok: true, plan: null, v: 0 });
  const raw = await env.ICB_KV.get("plan");
  if (!raw) return json({ ok: true, plan: null, v: 0 });
  const { plan, v } = JSON.parse(raw);
  return json({ ok: true, plan, v });
}

export async function onRequestPost({ request, env }) {
  const t = env.OWNER_HASH ? await readToken(env, request) : null;
  if (!t) return json({ ok: false, error: "signed-out" }, 401);
  if (!env.ICB_KV) return json({ ok: false, error: "no-storage" }, 503);
  const plan = cleanPlan((await readJson(request)).plan);
  if (!plan) return json({ ok: false, error: "bad-plan" }, 400);
  const v = Date.now();
  await env.ICB_KV.put("plan", JSON.stringify({ plan, v, by: t.r }));
  return json({ ok: true, v });
}
