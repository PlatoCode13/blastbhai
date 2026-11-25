"""Test-login hint: shown on the sign-in screen and in the tour only while the
admin password is still the first one.

    wrangler pages dev --port 8788      (fresh KV, i.e. a new --persist-to folder)
    ADMIN_PASS=... OWNER_PASS=... python3 tests/test_hint.py
"""
import json
import os
import sys
import urllib.request

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://127.0.0.1:8788").rstrip("/")
AP, OP = os.environ["ADMIN_PASS"], os.environ["OWNER_PASS"]
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


s, d = call("/hint")
check("/api/hint says show while the password is the first one", s == 200 and d.get("show") is True, (s, d))
check("/api/hint never sends a password", "password" not in json.dumps(d).lower() and AP not in json.dumps(d).lower())

with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)

    def fresh(tour_seen=True):
        c = br.new_context(viewport={"width": 1366, "height": 860}, reduced_motion="reduce")
        if tour_seen:
            c.add_init_script("try{localStorage.setItem('bbTour','1')}catch(e){}")
        pg = c.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        return c, pg, errs

    c, pg, errs = fresh()
    pg.goto(BASE + "/#results", wait_until="networkidle")
    pg.wait_for_selector("#login:not([hidden])")
    pg.wait_for_timeout(400)
    t = pg.inner_text("#lhint") if pg.is_visible("#lhint") else ""
    check("[login] shows Username: ICB", "Username: ICB" in t, t)
    check("[login] shows Password: Laha Torin", "Password: Laha Torin" in t, t)
    pg.type("#lu", "ICB")
    pg.type("#lp", "Laha Torin")
    pg.click("#lf .spin")
    pg.wait_for_selector("#subnav:not([hidden])", timeout=8000)
    check("[login] typing exactly 'Laha Torin' signs in", pg.is_visible("#subnav"))
    check("[login] no JS errors", not errs, errs[:2])
    c.close()

    c, pg, errs = fresh(tour_seen=False)
    pg.goto(BASE + "/", wait_until="networkidle")
    pg.wait_for_selector("#tour:not([hidden])", timeout=8000)
    for _ in range(6):
        if "ICB" in pg.inner_text("#tbody") or pg.is_hidden("#tour"):
            break
        pg.click("#tnext")
        pg.wait_for_timeout(250)
    t = pg.inner_text("#tbody")
    check("[tour] last step shows ICB / Laha Torin", "ICB" in t and "Laha Torin" in t, t)
    c.close()

    # owner changes the admin password -> hint disappears everywhere
    tok = call("/login", {"username": "ZHIMON", "password": OP})[1]["token"]
    call("/admin-password", {"newPassword": "changed pass"}, token=tok)
    check("/api/hint hides after the owner changes the password", call("/hint")[1].get("show") is False)
    c, pg, errs = fresh()
    pg.goto(BASE + "/#results", wait_until="networkidle")
    pg.wait_for_selector("#login:not([hidden])")
    pg.wait_for_timeout(400)
    check("[login] hint gone after the change", pg.is_hidden("#lhint"))
    c.close()
    c, pg, errs = fresh(tour_seen=False)
    pg.goto(BASE + "/", wait_until="networkidle")
    pg.wait_for_selector("#tour:not([hidden])", timeout=8000)
    for _ in range(4):
        pg.click("#tnext")
        pg.wait_for_timeout(250)
    t = pg.inner_text("#tbody")
    check("[tour] back to 'details in the slide deck'", "Laha Torin" not in t and "স্লাইড" in t, t)
    c.close()
    br.close()

call("/admin-password", {"newPassword": AP}, token=tok)
print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
