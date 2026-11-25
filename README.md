# BlastBhai · ICB 2026

Tournament system for Indoor Cricket Blast 2026 (Hamburg, 26–27 Dec): live draw, tournament map, schedule, team posters, live page, results with Man of the Match posters, and the rules presentation.

Hosted on **Cloudflare Pages**. Every push to `main` goes live in about a minute.

## Folders

```
site/                 ← everything visitors see (Cloudflare serves this folder)
  index.html          ← the BlastBhai app (one file)
  logos/ brand/       ← team crests, ICB logo
  rules/              ← rules presentation (Rules tab)
  _headers            ← caching: app page always fresh, images cached 1 day
functions/            ← backend (Cloudflare Pages Functions), served under /api
  api/health.js       ← GET /api/health — proves the backend works
  api/login.js        ← sign-in (checks passwords on the server)
  api/me.js           ← "am I still signed in?"
  api/admin-password.js ← owner only: change the general admin password
  api/plan.js         ← shared match-day plan (breaks, times, format): everyone reads, admins save
lib/auth.js           ← password hashing + signed sign-in tokens
tools/make-hash.mjs   ← makes a password hash for the Cloudflare secrets
tests/test_deploy.py  ← 30 deploy checks (pages, images, headers, API, phone)
tests/test_auth.py    ← 48 login checks (admin, owner, password change, lockout)
tests/test_breaks.py  ← 28 checks: breaks in every match list, Live break banner, shared plan
wrangler.toml         ← Cloudflare project settings
```

Later additions slot in without moving anything:
- **Widget / one-pager:** `site/widget/` → `https://<site>/widget/`
- **Shared live data, real admin login:** `functions/api/*.js` + Cloudflare KV or D1
- **Alerts to captains and officials (Telegram):** a small scheduled Cloudflare Worker in `workers/alerts/` that reads the same data

## Cloudflare Pages settings (one-time)

| Setting | Value |
| - | - |
| Framework preset | None |
| Build command | *(empty)* |
| Build output directory | `site` |
| Production branch | `main` |

## Test locally

```
npm i -g wrangler
wrangler pages dev --port 8788      # from the repo root
python3 tests/test_deploy.py        # needs: pip install playwright
ADMIN_PASS=... OWNER_PASS=... python3 tests/test_auth.py   # + .dev.vars with OWNER_HASH, ADMIN_HASH
```

## Breaks and the shared plan

- Breaks (prayer, lunch, buffer…) show in the full schedule, Results and Officials lists, and as a banner on Live ("Break now" / "Next break").
- Admins change them in Admin → Setup → Match day plan. The change is saved to the server and every open screen picks it up within a minute (Live also refreshes itself every 30 s).
- Free-plan note: each open screen asks once a minute while visible; fine for match day, watch the Cloudflare usage page.

## Sign-in

- Two accounts: general admin **ICB** and the owner **ZHIMON**. Usernames count in CAPITALS, passwords in small letters (the form converts while typing).
- Passwords are checked on the server. Only hashes are stored, as Cloudflare **secrets** `OWNER_HASH` and `ADMIN_HASH` (dashboard → blastbhai → Settings → Variables and secrets).
- Only the owner can change the admin password (Admin → Setup). The new one is kept in KV (`blastbhai-data`) and old admin sign-ins end at once.
- 10 wrong tries from one connection → blocked for 15 minutes.
- To change the **owner** password: `node tools/make-hash.mjs "new password"` → paste the result into the `OWNER_HASH` secret → redeploy.
- Without the server (local file / claude.ai preview) nobody can sign in.

Local test secrets go in `.dev.vars` (never committed).
