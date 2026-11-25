"""Deploy checks for BlastBhai on Cloudflare Pages.

Runs against `wrangler pages dev` (same engine as Cloudflare), so it tests
the real setup: static site from site/, headers from site/_headers and the
API from functions/.

    npx wrangler pages dev --port 8788 &      # from the repo root
    python3 tests/test_deploy.py              # BASE=http://127.0.0.1:8788

App behaviour itself (draw, tour, fixtures map...) is covered by test_app.py.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://127.0.0.1:8788").rstrip("/")
ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
TEAMS = ["BB", "BD", "BK", "CB", "CK", "EF", "FB", "HH", "NL", "PH", "ST", "TU"]
results = []


def check(name, ok, info=""):
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (f"  ({info})" if info and not ok else ""))


def ctype(h):
    return {k.lower(): v for k, v in h.items()}.get("content-type", "")


def get(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=15) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


# --- 1. Repo layout -------------------------------------------------------
check("site/index.html exists", (SITE / "index.html").is_file())
check("12 team logos in site/logos", all((SITE / f"logos/{t}.jpg").is_file() for t in TEAMS))
check("rules presentation in site/rules", (SITE / "rules/index.html").is_file())
check("nothing private inside site/ (no tests, configs, .py)",
      not any(p.suffix in {".py", ".toml", ".md"} or p.name.startswith(".env")
              for p in SITE.rglob("*")))
check("API code is outside site/ (not served as a file)",
      (ROOT / "functions/api/health.js").is_file() and not (SITE / "functions").exists())

# --- 1b. Draw fairness: the wheel and the shuffle use crypto randomness
html = (SITE / "index.html").read_text()
check("draw uses crypto.getRandomValues", "crypto.getRandomValues" in html and "w=Math.floor(rnd()*n)" in html
      and "Math.floor(rnd()*(i+1))" in html)

# --- 2. HTTP: pages, assets, headers --------------------------------------
s, h, body = get("/")
check("GET / -> 200", s == 200, s)
check("home page is BlastBhai", b"BlastBhai" in body)
cc = {k.lower(): v for k, v in h.items()}.get("cache-control", "")
check("app page not cached (updates show at once)", "no-cache" in cc, cc)

# Note: Pages answers unknown paths with index.html (200), so check the type too
for t in TEAMS:
    s, h, _ = get(f"/logos/{t}.jpg")
    if s != 200 or "image/jpeg" not in ctype(h):
        break
check("all 12 logos served as images", s == 200 and "image/jpeg" in ctype(h), f"{t}: {s} {ctype(h)}")
s, h, _ = get("/logos/BB.jpg")
cc = {k.lower(): v for k, v in h.items()}.get("cache-control", "")
check("logos cached for a day", "max-age=86400" in cc, cc)
s, h, _ = get("/")
hl = {k.lower(): v for k, v in h.items()}
check("page can't be framed by other sites", hl.get("x-frame-options") == "SAMEORIGIN"
      and "frame-ancestors 'self'" in hl.get("content-security-policy", ""), hl.get("content-security-policy"))
check("brand images served as images",
      all("image/jpeg" in ctype(get(f"/brand/{n}.jpg")[1]) for n in ["icb-full", "icb-mark"]))
s, h, body = get("/rules/")
check("rules page served (not the app)", s == 200 and b'data-v="fixtures"' not in body)
check("rules images served", all("image/webp" in ctype(get(f"/rules/{n}.webp")[1]) for n in ["hero", "badge"]))
check("tests folder NOT served", b"playwright" not in get("/tests/test_deploy.py")[2])
check("wrangler.toml NOT served", b"pages_build_output_dir" not in get("/wrangler.toml")[2])

# --- 3. Backend slot ------------------------------------------------------
s, h, body = get("/api/health")
try:
    data = json.loads(body)
except ValueError:
    data = {}
check("GET /api/health -> ok JSON", s == 200 and data.get("ok") is True, f"{s} {body[:80]!r}")
check("health says BlastBhai", data.get("app") == "BlastBhai")

# --- 4. Real browser: loads clean, desktop + phone ------------------------
with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)
    for label, vp in [("desktop", {"width": 1366, "height": 860}), ("phone", {"width": 390, "height": 844})]:
        ctx = br.new_context(viewport=vp, reduced_motion="reduce")
        pg = ctx.new_page()
        errors, bad = [], []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("response", lambda r: bad.append(f"{r.status} {r.url}")
              if r.url.startswith(BASE) and r.status >= 400 else None)
        pg.goto(BASE + "/", wait_until="networkidle")
        pg.wait_for_timeout(800)
        check(f"[{label}] no JS errors", not errors, "; ".join(errors[:2]))
        check(f"[{label}] no broken own files (404s)", not bad, "; ".join(bad[:3]))
        tabs = pg.eval_on_selector_all("nav a[data-v]", "els => els.map(e => e.dataset.v)")
        check(f"[{label}] all 7 tabs present",
              tabs == ["home", "live", "draw", "fixtures", "table", "rules", "admin"], tabs)
        # images in the page actually rendered
        broken = pg.evaluate("""[...document.images].filter(i => i.complete && i.src.startsWith(location.origin)
                               && i.naturalWidth === 0).map(i => i.src)""")
        check(f"[{label}] no broken images", not broken, broken[:3])
        # each tab opens (skip the tour first)
        for btn in ["Skip", "এড়িয়ে যান", "বাদ দিন"]:
            loc = pg.get_by_role("button", name=btn)
            if loc.count():
                loc.first.click()
                break
        pg.keyboard.press("Escape")
        opened = []
        for v in ["live", "draw", "fixtures", "table", "rules", "home"]:
            pg.goto(f"{BASE}/#{v}")
            pg.wait_for_timeout(250)
            opened.append(pg.evaluate("location.hash") == f"#{v}")
        check(f"[{label}] every tab opens by link", all(opened))
        check(f"[{label}] no JS errors after visiting tabs", not errors, "; ".join(errors[:2]))
        if label == "phone":
            wide = pg.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
            check("[phone] no sideways scrolling", not wide)
        ctx.close()
    br.close()

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
