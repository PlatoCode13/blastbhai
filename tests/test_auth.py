"""Login checks: general admin, owner, owner-only password change.

Needs the server running with test secrets in .dev.vars and a KV store:
    wrangler pages dev --port 8788 --kv ICB_KV       (repo root)
    python3 -m http.server 8790 --directory site      (no-server copy)
    python3 tests/test_auth.py

Passwords are never written in this file. Give them as environment values:
    ADMIN_PASS="..." OWNER_PASS="..." python3 tests/test_auth.py
The test changes the admin password and sets it back at the end.
"""
import json
import os
import sys
import urllib.request

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://127.0.0.1:8788").rstrip("/")
STATIC = os.environ.get("STATIC", "http://127.0.0.1:8790").rstrip("/")
LOCKOUT = os.environ.get("LOCKOUT", "1") == "1"   # turn off for the live site
AP = os.environ["ADMIN_PASS"]   # general admin (username ICB)
OP = os.environ["OWNER_PASS"]   # owner (username ZHIMON)
results = []


def check(name, ok, info=""):
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
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}


def login(u, p):
    return call("/login", {"username": u, "password": p})


# ---------- API ----------
s, d = login("ICB", AP)
check("admin: ICB + admin password signs in", s == 200 and d.get("role") == "admin", (s, d))
admin_tok = d.get("token")
check("admin: not allowed to change password", not d.get("canChangePassword"))
s, d = login("icb", AP.title())
check("admin: small username + capital password still work", s == 200 and d.get("role") == "admin", (s, d))
s, d = login("  ICB ", AP.upper() + " ")
check("admin: extra spaces at the ends ignored", s == 200, (s, d))
s, d = login("ICB", AP[:3] + "x")
check("admin: wrong password refused (401)", s == 401 and not d.get("token"), (s, d))
s, d = login("ICB2026", AP)
check("old username ICB2026 no longer works", s == 401, (s, d))

s, d = login("Zhimon", OP)
check("owner: Zhimon + owner password signs in as owner", s == 200 and d.get("role") == "owner", (s, d))
check("owner: name is Zhimon", d.get("name") == "Zhimon", d)
check("owner: may change password", d.get("canChangePassword") is True)
owner_tok = d.get("token")
s, d = login("ZHIMON", OP.upper())
check("owner: any letter case works", s == 200 and d.get("role") == "owner", (s, d))
s, d = login("ICB", OP)
check("owner password does not open the ICB account", s == 401, (s, d))
s, d = login("ZHIMON", AP)
check("admin password does not open the owner account", s == 401, (s, d))

check("/me knows the admin", call("/me", token=admin_tok)[1].get("role") == "admin")
check("/me knows the owner", call("/me", token=owner_tok)[1].get("role") == "owner")
check("/me refuses no token", call("/me")[0] == 401)
forged = admin_tok[:-3] + ("AAA" if not admin_tok.endswith("AAA") else "BBB")
check("/me refuses a changed (forged) token", call("/me", token=forged)[0] == 401)

s, d = call("/admin-password", {"newPassword": "new pass 1"}, token=admin_tok)
check("admin cannot change the password (403)", s == 403, (s, d))
s, d = call("/admin-password", {"newPassword": "new pass 1"})
check("signed-out cannot change the password (401)", s == 401, (s, d))
s, d = call("/admin-password", {"newPassword": "abc"}, token=owner_tok)
check("owner: too-short password refused", s == 400, (s, d))
s, d = call("/admin-password", {"newPassword": "Match Day 26"}, token=owner_tok)
check("owner: changes admin password", s == 200 and d.get("ok"), (s, d))
check("old admin password stops working", login("ICB", AP)[0] == 401)
check("new admin password works (stored in small letters)", login("ICB", "match day 26")[0] == 200)
check("old admin sign-ins are logged out", call("/me", token=admin_tok)[0] == 401)
check("owner stays signed in", call("/me", token=owner_tok)[0] == 200)
s, d = call("/admin-password", {"newPassword": AP}, token=owner_tok)
check("owner: sets the admin password back", s == 200 and login("ICB", AP)[0] == 200, (s, d))


# ---------- browser ----------
def sign_in(pg, user, pw):
    pg.goto(BASE + "/#results")
    pg.wait_for_selector("#login:not([hidden])")
    pg.type("#lu", user)
    pg.type("#lp", pw)
    shown = (pg.input_value("#lu"), pg.input_value("#lp"))
    pg.click("#lf .spin")
    return shown


with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)

    def fresh():
        ctx = br.new_context(viewport={"width": 1366, "height": 860}, reduced_motion="reduce")
        ctx.add_init_script("try{localStorage.setItem('bbTour','1')}catch(e){}")
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        return ctx, pg, errs

    # owner
    ctx, pg, errs = fresh()
    shown = sign_in(pg, "zhimon", OP.upper())
    check("[ui] username turns to CAPITALS while typing", shown[0] == "ZHIMON", shown)
    check("[ui] password turns to small letters while typing", shown[1] == OP, shown)
    pg.wait_for_selector("#welcome:not([hidden])", timeout=8000)
    check("[ui] owner gets the Welcome pop-up", "Welcome, Zhimon" in pg.text_content("#welcome h2"),
          pg.text_content("#welcome h2"))
    pg.click("#wpw")
    pg.wait_for_timeout(300)
    check("[ui] pop-up button opens the password card", pg.evaluate("location.hash") == "#setup"
          and pg.is_visible("#ownpw"))
    check("[ui] top bar says Owner · Zhimon", pg.inner_text("#subnav .who").strip().lower() == "owner · zhimon",
          pg.inner_text("#subnav .who"))
    pg.fill("#np1", "abcdef")
    pg.fill("#np2", "abcdeg")
    pg.click("#npsave")
    check("[ui] mismatch is caught", "not the same" in pg.inner_text("#npmsg"))
    pg.fill("#np1", "")
    pg.type("#np1", "Final Pass")
    pg.fill("#np2", "final pass")
    pg.click("#npsave")
    pg.wait_for_function("document.querySelector('#npmsg').textContent.startsWith('Saved')", timeout=8000)
    check("[ui] owner saves a new admin password", True)
    check("[api] UI change really works", login("ICB", "final pass")[0] == 200)
    pg.reload()
    pg.wait_for_timeout(600)
    check("[ui] owner stays signed in after reload", pg.is_visible("#subnav") and pg.is_visible("#ownpw"))
    check("[ui] no JS errors (owner)", not errs, errs[:2])
    ctx.close()
    tok = login("ZHIMON", OP)[1]["token"]
    call("/admin-password", {"newPassword": AP}, token=tok)

    # general admin
    ctx, pg, errs = fresh()
    sign_in(pg, "icb", AP.title())
    pg.wait_for_selector("#subnav:not([hidden])", timeout=8000)
    pg.wait_for_timeout(300)
    check("[ui] admin signs in (typed small/Capital)", pg.is_visible("#subnav"))
    check("[ui] admin gets no owner pop-up", pg.is_hidden("#welcome"))
    pg.goto(BASE + "/#setup")
    pg.wait_for_timeout(300)
    check("[ui] admin does not see the password card", pg.is_hidden("#ownpw"))
    check("[ui] top bar says Admin", pg.inner_text("#subnav .who").strip().lower() == "admin")
    # owner changes the password -> this admin is signed out on next load
    tok = login("ZHIMON", OP)[1]["token"]
    call("/admin-password", {"newPassword": "other pass"}, token=tok)
    pg.reload()
    pg.wait_for_timeout(1200)
    check("[ui] admin is logged out after the owner changes the password",
          pg.is_hidden("#subnav") or pg.is_visible("#login"))
    call("/admin-password", {"newPassword": AP}, token=tok)
    check("[ui] no JS errors (admin)", not errs, errs[:2])
    ctx.close()

    # wrong password
    ctx, pg, errs = fresh()
    sign_in(pg, "ICB", "nope nope")
    pg.wait_for_function("document.querySelector('#lerr').textContent.length>0", timeout=8000)
    check("[ui] wrong password shows a message", "Wrong" in pg.inner_text("#lerr"))
    check("[ui] wrong password stays out", pg.is_hidden("#subnav"))
    ctx.close()

    # no server (plain file host): sign-in is refused politely
    if STATIC:
        ctx, pg, errs = fresh()
        pg.goto(STATIC + "/#results")
        pg.wait_for_selector("#login:not([hidden])")
        pg.type("#lu", "icb")
        pg.type("#lp", AP)
        pg.click("#lf .spin")
        pg.wait_for_function("document.querySelector('#lerr').textContent.length>0", timeout=8000)
        check("[no server] told to use the live site", "live site" in pg.inner_text("#lerr"))
        check("[no server] nobody gets in", pg.is_hidden("#subnav"))
        check("[ui] no JS errors (no server)", not errs, errs[:2])
        ctx.close()
    br.close()

# ---------- guessing is slowed down (last: it blocks this computer for 15 min) ----------
if LOCKOUT:
    codes = [login("ICB", f"guess {i}")[0] for i in range(11)]
    check("10 wrong tries -> blocked (429)", codes[-1] == 429, codes)
    check("blocked even with the right password", login("ICB", AP)[0] == 429)

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
