"""Breaks in every match list + the shared match-day plan (/api/plan).

    wrangler pages dev --port 8788      (fresh KV)
    ADMIN_PASS=... python3 tests/test_breaks.py

Leaves the shared plan on the defaults when it finishes.
"""
import json
import os
import sys
import urllib.request

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://127.0.0.1:8788").rstrip("/")
AP = os.environ["ADMIN_PASS"]
results = []


def check(name, ok, info=""):
    ok = bool(ok)
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (f"  ({info})" if info and not ok else ""))


def call(path, body=None, token=None):
    req = urllib.request.Request(BASE + "/api" + path, method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": "Bearer " + token} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


DEFAULT = {"dp": {"d1": 9, "start": [480, 480], "close": [1140, 1200], "br": [
    [{"l": "Lunch + Dhuhr prayer", "a": 4, "m": 60}, {"l": "Asr prayer", "a": 5, "m": 20},
     {"l": "Maghrib prayer", "a": 7, "m": 20}, {"l": "Buffer", "a": 9, "m": 20}],
    [{"l": "Table check + rest before QFs", "a": 3, "m": 20}, {"l": "Lunch + Dhuhr prayer", "a": 4, "m": 60},
     {"l": "Asr prayer", "a": 5, "m": 20}, {"l": "Maghrib + final prep", "a": 6, "m": 40},
     {"l": "Prize giving + closing", "a": 7, "m": 60}, {"l": "Buffer", "a": 7, "m": 60}]]},
    "len": 55, "ch": 5, "alone": True, "fmt": "B", "mpt": 4}

# ---------- API ----------
s, d = call("/plan")
check("GET /api/plan works for everyone", s == 200 and d.get("ok"), (s, d))
tok = call("/login", {"username": "ICB", "password": AP})[1]["token"]
check("POST without sign-in refused (401)", call("/plan", {"plan": DEFAULT})[0] == 401)
check("POST with a forged token refused (401)", call("/plan", {"plan": DEFAULT}, token=tok[:-4] + "AAAA")[0] == 401)
bad = json.loads(json.dumps(DEFAULT)); bad["dp"]["br"][0][0]["m"] = 9999
check("POST with impossible minutes refused (400)", call("/plan", {"plan": bad}, token=tok)[0] == 400)
bad = json.loads(json.dumps(DEFAULT)); bad["fmt"] = "Z"
check("POST with unknown format refused (400)", call("/plan", {"plan": bad}, token=tok)[0] == 400)
bad = json.loads(json.dumps(DEFAULT)); bad["dp"]["br"][0][0]["l"] = "x" * 500
s, d = call("/plan", {"plan": bad}, token=tok)
check("long break names are cut to 40 letters", s == 200 and len(call("/plan")[1]["plan"]["dp"]["br"][0][0]["l"]) == 40, (s, d))
s, d = call("/plan", {"plan": DEFAULT}, token=tok)
check("admin saves the plan", s == 200 and d.get("v"), (s, d))
check("everyone reads the same plan back", call("/plan")[1]["plan"] == DEFAULT)

# ---------- browser ----------
DAY1_1230 = "2026-12-26T12:30:00+01:00"
DAY1_1130 = "2026-12-26T11:30:00+01:00"
BEFORE = "2026-11-26T20:00:00+01:00"

with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)

    def ctx_at(when, vp=None):
        c = br.new_context(viewport=vp or {"width": 1366, "height": 860}, reduced_motion="reduce",
                           timezone_id="Europe/Berlin")
        c.add_init_script("try{localStorage.setItem('bbTour','1')}catch(e){}")
        pg = c.new_page()
        pg.clock.install(time=when)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        return c, pg, errs

    def sign_in(pg):
        pg.goto(BASE + "/#results")
        pg.wait_for_selector("#login:not([hidden])")
        pg.type("#lu", "ICB")
        pg.type("#lp", AP)
        pg.click("#lf .spin")
        pg.wait_for_selector("#subnav:not([hidden])")

    # public: full schedule shows breaks (even before the draw)
    c, pg, errs = ctx_at(BEFORE)
    pg.goto(BASE + "/#fixtures", wait_until="networkidle")
    pg.click("button.fsb")
    pg.wait_for_selector("#allfx .ritem")
    rows = pg.locator("#allfx .brow")
    texts = rows.all_inner_texts()
    check("[public] full schedule lists the breaks", rows.count() >= 8, rows.count())
    check("[public] prayer breaks are named", any("Dhuhr" in t for t in texts) and any("Asr" in t for t in texts)
          and any("Maghrib" in t for t in texts), texts[:3])
    order = pg.evaluate("""[...document.querySelectorAll('#allfx > *')].slice(0,20).map(e=>e.className.split(' ')[0]+':'+(e.querySelector('time')||{}).textContent)""")
    lunch = next((i for i, x in enumerate(order) if x.startswith("brow:12:00")), -1)
    check("[public] Day 1 lunch sits at 12:00, between the 11:00 and 13:00 matches",
          lunch > 0 and order[lunch - 1].startswith("ritem:11:00") and order[lunch + 1].startswith("ritem:13:00"), order)
    pg.goto(BASE + "/#live")
    pg.wait_for_timeout(300)
    check("[public] no break banner before the tournament", pg.is_hidden("#lvbrk"))
    check("[public] no JS errors", not errs, errs[:2])
    c.close()

    # live: during lunch and before lunch
    c, pg, errs = ctx_at(DAY1_1230)
    pg.goto(BASE + "/#live", wait_until="networkidle")
    pg.wait_for_timeout(300)
    t = pg.text_content("#lvbrk") if pg.is_visible("#lvbrk") else ""
    check("[live 12:30] shows Break now", "Break now" in t and "Lunch + Dhuhr prayer" in t, t)
    check("[live 12:30] says when play resumes", "13:00" in t, t)
    c.close()
    c, pg, errs = ctx_at(DAY1_1130)
    pg.goto(BASE + "/#live", wait_until="networkidle")
    pg.wait_for_timeout(300)
    t = pg.text_content("#lvbrk") if pg.is_visible("#lvbrk") else ""
    check("[live 11:30] shows the next break", "Next break 12:00" in t and "60 min" in t, t)
    viewer = (c, pg)  # keep this one open: it must pick up the admin's change by itself

    # admin: draw, breaks in Results and Officials, then change a break
    ca, pa, errs_a = ctx_at(DAY1_1130)
    sign_in(pa)
    pa.goto(BASE + "/#draw")
    pa.wait_for_timeout(300)
    if pa.is_visible("#go"):
        pa.click("#go")
    pa.click("#instant")
    pa.wait_for_timeout(400)
    pa.goto(BASE + "/#results")
    pa.wait_for_selector("#reslist .ritem")
    check("[admin] Results list shows the breaks", pa.locator("#reslist .brow").count() >= 8)
    pa.goto(BASE + "/#officials")
    pa.wait_for_timeout(300)
    check("[admin] Officials list shows the breaks between matches", pa.locator("#offlist .brow").count() >= 3)
    pa.goto(BASE + "/#setup")
    pa.wait_for_selector("#br0 .bkr")
    pa.locator("#br0 .bkr").first.locator("select.bm").select_option("45")
    pa.wait_for_function("document.querySelector('#syncst').textContent.includes('Saved for everyone')", timeout=8000)
    check("[admin] change is saved for everyone", True)
    srv = call("/plan")[1]["plan"]["dp"]["br"][0][0]
    check("[api] server has the new 45 min lunch", srv["m"] == 45, srv)

    # the open public screen updates within a minute, no reload
    vc, vp = viewer
    vp.clock.run_for(61000)
    vp.wait_for_timeout(800)
    t = vp.inner_text("#lvbrk") if vp.is_visible("#lvbrk") else ""
    check("[live] open screen picks up the change by itself", "45 min" in t and "12:45" in t, t)
    vp.goto(BASE + "/#fixtures")
    vp.click("button.fsb")
    vp.wait_for_selector("#allfx .ritem")
    order = vp.evaluate("""[...document.querySelectorAll('#allfx > *')].slice(0,20).map(e=>(e.querySelector('time')||{}).textContent)""")
    times = [(x or "")[:5] for x in order[:16]]
    check("[public] matches after lunch move to 12:45", "12:45" in times and "13:00" not in times, times)
    vc.close()

    # a brand-new visitor gets the shared plan
    c, pg, errs = ctx_at(DAY1_1130, {"width": 390, "height": 844})
    pg.goto(BASE + "/#live", wait_until="networkidle")
    pg.wait_for_timeout(600)
    t = pg.inner_text("#lvbrk") if pg.is_visible("#lvbrk") else ""
    check("[phone] new visitor sees the shared 45 min lunch", "45 min" in t, t)
    check("[phone] no sideways scrolling", not pg.evaluate("document.documentElement.scrollWidth > innerWidth + 1"))
    check("[phone] no JS errors", not errs, errs[:2])
    c.close()

    # 'View as public' does not push anything
    v_before = call("/plan")[1]["v"]
    pa.click("#asPublic")
    pa.wait_for_timeout(1200)
    check("[admin] View as public sends nothing", call("/plan")[1]["v"] == v_before)
    pa.click("#backAdmin")
    pa.goto(BASE + "/#setup")
    pa.wait_for_selector("#dpreset")
    pa.click("#dpreset")
    ok = False
    for _ in range(20):
        pa.wait_for_timeout(300)
        if call("/plan")[1]["plan"]["dp"] == DEFAULT["dp"]:
            ok = True
            break
    check("[admin] Back to defaults is shared too", ok, call("/plan")[1]["plan"]["dp"]["br"][0][0])
    check("[admin] no JS errors", not errs_a, errs_a[:2])
    ca.close()
    br.close()

call("/plan", {"plan": DEFAULT}, token=tok)
print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
