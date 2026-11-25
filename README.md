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
tests/test_deploy.py  ← 30 deploy checks (pages, images, headers, API, phone)
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
```

## Note

Admin sign-in is still a client-side curtain (only a hash is in the page). A real login comes with the backend. Change it before match day.
