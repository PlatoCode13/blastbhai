"""BlastBhai tests: home, blank-before-draw skeleton, live filling, session-only draws, official draw. Run: python3 test_app.py"""
import asyncio,sys,json
from playwright.async_api import async_playwright
import os
U=os.environ.get('BASE','http://127.0.0.1:8788').rstrip('/')+'/index.html'
CSS=open(os.environ.get('FONTS_CSS','/home/claude/fonts/fonts.css')).read()  # local @font-face rules (Google Fonts may be blocked)
SH=os.environ.get('SHOTS','/tmp/blastbhai-shots/');os.makedirs(SH,exist_ok=True)
ok=[];bad=[]
REAL=['Blasters','Fusion','Phantoms','Legends','Brotherhood','Heatwaves','Fire Boys','SV Tigers','Sportings','Bagh','Knights','Kingslayers']
def check(name,cond,info=''):
    (ok if cond else bad).append(name);print(('PASS ' if cond else 'FAIL ')+name+(' '+str(info) if info and not cond else ''))
def noreal(t):return not any(r in t for r in REAL)
ERR=[]
async def page(ctx):
    pg=await ctx.new_page();pg.on('pageerror',lambda e:ERR.append(str(e)));return pg
async def fonts(pg):
    await pg.add_style_tag(content=CSS);await pg.evaluate('document.fonts.ready')
async def go(pg,h,wait=600):
    await pg.evaluate(f"location.hash='{h}'");await pg.wait_for_timeout(wait)
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
        # --- guided tour (first visit only)
        ctxt=await b.new_context(viewport={'width':1440,'height':900});pt=await page(ctxt);await pt.goto(U);await fonts(pt);await pt.wait_for_timeout(1500)
        check('tour shows on first visit',await pt.locator('#tour:not([hidden])').count()==1)
        steps=0
        while await pt.locator('#tour:not([hidden])').count() and steps<8:
            steps+=1
            if steps==5:
                last=await pt.inner_text('#tbody');check('tour gives the login (test login, or the slide deck once changed)',('ICB' in last and 'Laha Torin' in last) or 'স্লাইড ডেকে' in last,last)
                await pt.screenshot(path=SH+'s-tour-login.png')
            await pt.click('#tnext');await pt.wait_for_timeout(450)
        check('tour has 5 steps and closes',steps==5,steps)
        await pt.reload();await pt.wait_for_timeout(1500)
        check('tour does not show again',await pt.locator('#tour:not([hidden])').count()==0)
        pt2=await page(await b.new_context());await pt2.goto(U);await pt2.wait_for_timeout(1300);await pt2.click('#tskip');await pt2.wait_for_timeout(200)
        check('skip closes tour',await pt2.locator('#tour:not([hidden])').count()==0)
        NT="localStorage.setItem('bbTour','1')"
        ctx=await b.new_context(viewport={'width':1440,'height':900},reduced_motion='reduce');await ctx.add_init_script(NT);pg=await page(ctx)
        # --- home
        await pg.goto(U);await fonts(pg);await pg.wait_for_timeout(1800)
        check('lands on Home',await pg.locator('#v-home:not([hidden])').count()==1)
        check('countdown has 4 boxes',await pg.locator('#homecd > div').count()==4)
        facts=await pg.eval_on_selector_all('#facts b','e=>e.map(x=>x.textContent)')
        check('facts count up',facts==['১২','৬','১০৮','৩১','২','২'],facts)
        h=await pg.inner_text('#v-home .hh');check('headline wording',h=='প্রথম বল মাঠে গড়াতে আর বাকি',h)
                # --- blank before the draw
        await go(pg,'fixtures',800)
        check('Fixtures opens on the map',await pg.locator('#fxmap:not([hidden])').count()==1)
        check('12 empty slots',await pg.locator('#fxmap .mrow .ph').count()==12)
        st=await pg.inner_text('#fxmap .mst');check('status: draw on 4 Dec','৪ ডিসেম্বর' in st,st)
        check('trophy drawn',await pg.locator('#fxmap svg.trophy').count()==1)
        pos=await pg.eval_on_selector_all('#fxmap .bs .pos','e=>e.map(x=>x.textContent)')
        check('QFs use 1A v 4B labels',pos[:2]==['1A','4B'] and len(pos)>=8,pos)
        tot=await pg.inner_text('#fxmap .mcount .tot');check('total 31 matches','৩১' in tot,tot)
        ac=await pg.inner_text('#picker .allic');check('All-matches chip shows 31',ac=='31',ac)
        check('glowing trophy wrapper',await pg.locator('#fxmap .tro svg.trophy .shine').count()==1)
        check('team chips locked before draw',await pg.locator('#picker .pk[disabled]').count()==12)
        mt=await pg.inner_text('#fxmap');check('map has no team names',noreal(mt))
        await pg.screenshot(path=SH+'s-map-empty.png',full_page=True)
        check('button says Full schedule',(await pg.text_content('#fxmap .mfoot .spin')).strip()=='Full schedule')
        await pg.click('#fxmap .mfoot .spin');await pg.wait_for_timeout(500)
        n=await pg.locator('#allfx .ritem').count();t=await pg.inner_text('#allfx')
        check('full list: 31 slot matches, no names',n==31 and 'A1' in t and noreal(t),n)
        await go(pg,'live');t=await pg.inner_text('#lvfields');pv=await pg.inner_text('#preview')
        check('live shows slots, no names',noreal(t) and ('A' in t),t[:80])
        check('banner explains slots','ড্র এখনো হয়নি' in pv,pv)
        await go(pg,'table');check('table shows slots, no names',noreal(await pg.inner_text('#tables')))
        # --- a real spin fills the map live
        await go(pg,'draw');await pg.click('#go');await pg.wait_for_timeout(300);await pg.click('#spin')
        await pg.wait_for_function("document.querySelectorAll('#gA .slot[data-id],#gB .slot[data-id]').length===1",timeout=20000)
        landed=await pg.get_attribute('#gA .slot[data-id],#gB .slot[data-id]','data-id')
        await pg.wait_for_timeout(2600);await go(pg,'fixtures',700)
        if await pg.locator('#fxmap[hidden]').count():await pg.click('#picker [data-t=MAP]');await pg.wait_for_timeout(300)
        check('map: 1 slot filled after 1 spin',await pg.locator('#fxmap .mrow .ph').count()==11)
        check('filled slot is the landed team',await pg.locator(f'#fxmap .mrow img[src="logos/{landed}.jpg"]').count()==1,landed)
        st=await pg.inner_text('#fxmap .mst');check('status: draw running','১২টির মধ্যে ১টি' in st,st)
        # --- partial draw via session, check names flow into schedule
        await pg.evaluate("""sessionStorage.setItem('icb26-draw',JSON.stringify({order:[{id:'CB',g:'A'},{id:'FB',g:'B'},{id:'EF',g:'A'}],drawDone:false}))""")
        await pg.reload();await pg.wait_for_timeout(900);await go(pg,'fixtures',600)
        check('partial: 3 filled, 9 empty',await pg.locator('#fxmap .mrow .ph').count()==9)
        await pg.click('#picker [data-t=ALL]');await pg.wait_for_timeout(400);t=await pg.inner_text('#allfx')
        check('partial: drawn names appear in list','Blasters' in t and 'Fusion' in t and 'Fire Boys' in t and 'A3' in t)
        await pg.screenshot(path=SH+'s-map-partial-list.png')
        # --- complete draw
        await go(pg,'draw');await pg.click('#reset');await pg.wait_for_timeout(200)
        if await pg.locator('#intro:not([hidden])').count():await pg.click('#go')
        await pg.click('#instant');await pg.wait_for_timeout(500)
        await go(pg,'fixtures',800)
        if await pg.locator('#fxmap[hidden]').count():await pg.click('#picker [data-t=MAP]');await pg.wait_for_timeout(300)
        check('complete: no empty slots',await pg.locator('#fxmap .mrow .ph').count()==0 and await pg.locator('#fxmap .mrow img').count()==12)
        check('complete: team chips open',await pg.locator('#picker .pk[disabled]').count()==0)
        await pg.screenshot(path=SH+'s-map-full.png',full_page=True)
        await pg.click('#fxmap .mfoot .spin');await pg.wait_for_timeout(500);t=await pg.inner_text('#allfx')
        check('full schedule with real teams',await pg.locator('#allfx .ritem').count()==31 and not noreal(t))
        await pg.click('#picker .pk:nth-child(3)');await pg.wait_for_timeout(1200)
        check('team view opens after draw',await pg.locator('#tview:not([hidden])').count()==1)
        # --- reload keeps it, new visit is blank
        await pg.reload();await pg.wait_for_timeout(900)
        check('reload in same tab keeps draw',await pg.evaluate("JSON.parse(sessionStorage.getItem('icb26-draw')).order.length")==12)
        check('draw not stored on device',await pg.evaluate("'order' in JSON.parse(localStorage.getItem('icb26-v3'))")==False)
        pg2=await page(ctx);await pg2.goto(U+'#fixtures');await pg2.wait_for_timeout(900)
        check('new visit starts blank',await pg2.locator('#fxmap .mrow .ph').count()==12)
        # --- old saved draw (before this update) is ignored
        ctxm=await b.new_context(viewport={'width':1440,'height':900});await ctxm.add_init_script(NT);pm=await page(ctxm);await pm.goto(U)
        await pm.evaluate("""localStorage.setItem('icb26-v3',JSON.stringify({order:[{id:'CB',g:'A'}],drawDone:true,drawKind:'test',final:{A:['CB','EF','PH','NL','TU','HH'],B:['FB','ST','BD','BB','BK','CK']},dp:{d1:9,start:[480,480],close:[1140,1200],br:[[],[]]},mpt:4}))""")
        await pm.reload();await pm.wait_for_timeout(900);await go(pm,'fixtures')
        check('old test draw on device is ignored',await pm.locator('#fxmap .mrow .ph').count()==12)
        # --- admin: schedule / officials / results before the draw
        ctxa=await b.new_context(viewport={'width':1440,'height':900});await ctxa.add_init_script(NT);pa=await page(ctxa);await pa.goto(U)
        await pa.evaluate("sessionStorage.setItem('bbAuth',JSON.stringify({token:'',role:'admin',name:'Admin'}))");await pa.reload();await pa.wait_for_timeout(700)
        await go(pa,'schedule',900);t=await pa.inner_text('#days')
        check('admin schedule: A1 v A3 style, no names','A1' in t and noreal(t))
        await pa.screenshot(path=SH+'s-admin-schedule.png')
        await go(pa,'officials');check('officials wait for the draw',await pa.locator('#offlist .predraw').count()==1)
        await go(pa,'results');check('results wait for the draw',await pa.locator('#reslist .predraw').count()==1)
        # official draw stays; public can't redo it
        await go(pa,'draw');await pa.wait_for_timeout(300)
        if await pa.locator('#intro:not([hidden])').count():await pa.click('#go')
        if await pa.get_attribute('#official','aria-pressed')!='true':await pa.click('#official')
        await pa.click('#instant');await pa.wait_for_timeout(600)
        check('official draw saved on device',await pa.evaluate("!!localStorage.getItem('icb26-official')"))
        pb=await page(ctxa);await pb.goto(U+'#fixtures');await pb.wait_for_timeout(900)
        check('official draw shows on next visit',await pb.locator('#fxmap .mrow .ph').count()==0)
        st=await pb.inner_text('#fxmap .mst');check('status: official','অফিশিয়াল' in st,st)
        await go(pb,'draw');await pb.wait_for_timeout(300)
        check('public cannot redo the official draw',not await pb.locator('#reset').is_visible() and not await pb.locator('#instant').is_visible())
        await go(pa,'draw');await pa.click('#reset');await pa.wait_for_timeout(300)
        check('admin reset removes official draw',await pa.evaluate("localStorage.getItem('icb26-official')") is None)
        # format A (top 2) map
        await go(pa,'setup',700);await pa.click('#fmts [data-f=A]');await pa.wait_for_timeout(500);await go(pa,'fixtures',700)
        if await pa.locator('#fxmap[hidden]').count():await pa.click('#picker [data-t=MAP]');await pa.wait_for_timeout(300)
        check('top-2 format: no QFs, 2 semis',await pa.locator('#fxmap .qcol').count()==0 and await pa.locator('#fxmap .scol').count()==2)
        await pa.click('#fmts [data-f=B]') if await pa.locator('#fmts').is_visible() else None
        # --- phone
        ctxp=await b.new_context(viewport={'width':390,'height':844});await ctxp.add_init_script(NT);pp=await page(ctxp);await pp.goto(U+'#fixtures');await fonts(pp);await pp.wait_for_timeout(900)
        for h in ['home','live','draw','fixtures','table']:
            await go(pp,h,500);sw=await pp.evaluate('document.documentElement.scrollWidth');check(f'phone {h}: no sideways scroll',sw<=390,sw)
        await go(pp,'fixtures',600);await pp.screenshot(path=SH+'s-phone-map.png',full_page=True)
        w=await pp.evaluate("document.querySelector('#fbk').getBoundingClientRect().width");check('phone: feedback is a small round button',w<=52,w)
        check('feedback keeps its accessible name',(await pp.get_attribute('#fbk','aria-label') or '').startswith('Give feedback'))
        await pp.evaluate("scrollTo(0,0)");await pp.wait_for_timeout(200);await pp.mouse.wheel(0,600);await pp.wait_for_timeout(400)
        check('feedback hides while scrolling down',await pp.evaluate("document.querySelector('#fbk').classList.contains('away')"))
        await pp.mouse.wheel(0,-300);await pp.wait_for_timeout(400)
        check('feedback returns on scroll up',not await pp.evaluate("document.querySelector('#fbk').classList.contains('away')"))
        await pp.screenshot(path=SH+'s-phone-fbk.png')
        check('no script errors',not ERR,ERR)
        await b.close()
    print(f'\n{len(ok)} passed, {len(bad)} failed');sys.exit(1 if bad else 0)
asyncio.run(main())
