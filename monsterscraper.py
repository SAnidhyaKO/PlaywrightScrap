# # monster_playwright_pro.py
# # Playwright (sync) with proxy rotation, stealth, humanized scrolling, retries, continuous IDs.
# from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
# import json, os, time, random, re, sys
# from pathlib import Path
# from urllib.parse import quote_plus

# # ================== CONFIG ==================
# OUT_FILE = Path("monster_jobs.json")
# KEYWORDS = ["python developer", "backend engineer", "react developer"]
# LOCATION = "Remote"            # e.g., "New York, NY" or "Remote"
# COUNTRY  = "US"                # affects geolocation/locale; set "IN" for India, etc.
# FETCH_DETAILS = True           # visit each job page for description
# SCROLL_MAX_SEC = 45            # per keyword
# HEADLESS = False               # headed mode reduces detection
# MANUAL_PAUSE = False           # set True to solve challenges by hand

# # ---- Proxy pool (rotate per context). Use user:pass@host:port or host:port
# PROXIES = [
#     # "user:pass@res-proxy.example.com:8001",
#     # "user:pass@res-proxy.example.com:8002",
# ]

# # ---- User-Agent pool
# UA_POOL = [
#     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
#     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
#     "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
# ]

# # ================== HELPERS ==================
# UUID_RE = re.compile(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", re.I)

# def monster_search_url(keyword, location):
#     return f"https://www.monster.com/jobs/search/?q={quote_plus(keyword)}&where={quote_plus(location)}"

# def load_existing():
#     if OUT_FILE.exists():
#         try:
#             return json.loads(OUT_FILE.read_text("utf-8"))
#         except Exception:
#             pass
#     return []

# def save_all(rows):
#     OUT_FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf-8")

# def next_id(rows):
#     return (max((r.get("id", 0) for r in rows), default=0) + 1) if rows else 1

# def extract_uuid(url):
#     m = UUID_RE.search(url or "")
#     return m.group(1) if m else None

# def accept_cookies(page):
#     for sel in [
#         "button#onetrust-accept-btn-handler",
#         "button[aria-label='Accept all']",
#         "button:has-text('Accept All')",
#         "button:has-text('I Agree')",
#     ]:
#         try:
#             if page.locator(sel).first.is_visible():
#                 page.locator(sel).first.click()
#                 break
#         except: pass

# def stealthify(page):
#     page.add_init_script("""
#       Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
#       window.chrome = window.chrome || { runtime: {} };
#       const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
#       if (originalQuery) {
#         window.navigator.permissions.query = (parameters) => (
#           parameters.name === 'notifications'
#             ? Promise.resolve({ state: Notification.permission })
#             : originalQuery(parameters)
#         );
#       }
#       // Fake plugins & languages
#       Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3] });
#       Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
#     """)

# def human_wiggle(page):
#     w = page.viewport_size["width"]
#     h = page.viewport_size["height"]
#     for _ in range(random.randint(2,4)):
#         x = random.randint(60, w-60); y = random.randint(90, h-90)
#         page.mouse.move(x, y, steps=random.randint(8,18))
#         time.sleep(random.uniform(0.06, 0.15))

# def robust_scroll(page, max_seconds=40):
#     start = time.time()
#     last_h = 0
#     while time.time() - start < max_seconds:
#         # Try a “Load more” button if present
#         try:
#             btn = page.locator("button:has-text('Load more')")
#             if btn and btn.first.is_visible():
#                 btn.first.click()
#                 page.wait_for_load_state("networkidle", timeout=10000)
#         except: pass

#         page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
#         time.sleep(random.uniform(0.6, 1.2))
#         human_wiggle(page)

#         new_h = page.evaluate("document.body.scrollHeight")
#         if new_h == last_h:
#             page.evaluate("window.scrollTo(0, document.body.scrollHeight - 500)")
#             time.sleep(random.uniform(0.4, 0.9))
#             page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
#             time.sleep(0.6)
#             if page.evaluate("document.body.scrollHeight") == new_h:
#                 break
#         last_h = new_h

# def parse_list_cards(page):
#     cards = page.locator("div#JobCardGrid article[data-testid='svx_jobCard']")
#     n = cards.count()
#     rows = []
#     for i in range(n):
#         c = cards.nth(i)
#         a = c.locator("a[data-testid='jobTitle']")
#         if a.count() == 0: 
#             continue
#         title = a.first.inner_text().strip()
#         href  = a.first.get_attribute("href") or ""
#         # Company
#         company = ""
#         try: company = c.locator("span[data-testid='company']").first.inner_text().strip()
#         except: pass
#         # Location
#         location = ""
#         try: location = c.locator("span[data-testid='jobDetailLocation']").first.inner_text().strip()
#         except: pass
#         rows.append({"title": title, "url": href, "company": company, "location": location})
#     return rows

# def parse_detail(page):
#     title = ""
#     for sel in ["[data-testid='jobTitle']", "h1", "h2"]:
#         try:
#             if page.locator(sel).first.is_visible():
#                 title = page.locator(sel).first.inner_text().strip(); break
#         except: pass

#     desc = ""
#     for sel in ["[data-testid='jobDescription']", "section#JobDescription", "div#JobDescription", "article"]:
#         try:
#             if page.locator(sel).first.is_visible():
#                 raw = page.locator(sel).first.inner_text().strip()
#                 desc = " ".join(raw.split()); break
#         except: pass

#     return {"job_title_detail": title, "description": desc}

# def with_retries(fn, retries=3, base_sleep=1.0):
#     last = None
#     for i in range(retries):
#         try:
#             return fn()
#         except Exception as e:
#             last = e
#             time.sleep(base_sleep * (2 ** i) + random.uniform(0, 0.5))
#     raise last

# def new_context(p, proxy=None):
#     args = [
#         "--disable-blink-features=AutomationControlled",
#         "--disable-dev-shm-usage",
#         "--no-sandbox",
#     ]
#     browser = p.chromium.launch(headless=HEADLESS, args=args, slow_mo=random.randint(20,60))
#     ua = random.choice(UA_POOL)
#     viewport = {"width": random.randint(1280, 1560), "height": random.randint(820, 1020)}
#     ctx_kwargs = dict(
#         user_agent=ua,
#         viewport=viewport,
#         locale="en-US",
#         timezone_id="America/New_York" if COUNTRY=="US" else "Asia/Kolkata",
#         geolocation={"latitude": 40.73, "longitude": -73.93} if COUNTRY=="US" else {"latitude": 28.61, "longitude": 77.20},
#         permissions=["geolocation"],
#     )
#     if proxy:
#         # proxy format: user:pass@host:port OR host:port
#         if "@" in proxy:
#             auth, hostport = proxy.split("@", 1)
#             user, pwd = auth.split(":", 1)
#             host, port = hostport.split(":")
#             ctx_kwargs["proxy"] = {"server": f"http://{host}:{port}", "username": user, "password": pwd}
#         else:
#             host, port = proxy.split(":")
#             ctx_kwargs["proxy"] = {"server": f"http://{host}:{port}"}
#     context = browser.new_context(**ctx_kwargs)
#     page = context.new_page()
#     stealthify(page)
#     return browser, context, page

# # ================== MAIN ==================
# def main():
#     data = load_existing()
#     nid = next_id(data)
#     seen = {(r.get("source","monster"), r.get("job_id")) for r in data if r.get("job_id")}

#     with sync_playwright() as p:
#         proxy_idx = -1

#         for kw in KEYWORDS:
#             # rotate context (and proxy) per keyword
#             proxy = None
#             if PROXIES:
#                 proxy_idx = (proxy_idx + 1) % len(PROXIES)
#                 proxy = PROXIES[proxy_idx]

#             browser, context, page = new_context(p, proxy)

#             url = monster_search_url(kw, LOCATION)

#             def goto_list():
#                 page.goto(url, wait_until="domcontentloaded", timeout=45000)
#                 accept_cookies(page)
#                 try: page.wait_for_load_state("networkidle", timeout=10000)
#                 except PWTimeout: pass
#                 human_wiggle(page)

#             # open list with retries (proxy hiccups happen)
#             with_retries(goto_list, retries=3, base_sleep=1.5)

#             if MANUAL_PAUSE:
#                 print("🔒 Manual pause: clear any challenge, then press Enter…")
#                 input()

#             robust_scroll(page, max_seconds=SCROLL_MAX_SEC)

#             listings = parse_list_cards(page)
#             for row in listings:
#                 job_id = extract_uuid(row["url"]) or f"{kw}:{row['url']}"
#                 key = ("monster", job_id)
#                 if key in seen:
#                     continue

#                 record = {
#                     "id": nid,
#                     "source": "monster",
#                     "keyword": kw,
#                     "job_id": job_id,
#                     "title": row["title"],
#                     "company": row["company"],
#                     "location": row["location"],
#                     "url": row["url"],
#                 }

#                 if FETCH_DETAILS and row["url"]:
#                     def fetch_detail():
#                         page.goto(row["url"], wait_until="domcontentloaded", timeout=45000)
#                         try: page.wait_for_load_state("networkidle", timeout=9000)
#                         except PWTimeout: pass
#                         human_wiggle(page)
#                         dd = parse_detail(page)
#                         # hop back to list for continuity (short scroll to regenerate DOM if needed)
#                         page.goto(url, wait_until="domcontentloaded", timeout=45000)
#                         try: page.wait_for_load_state("networkidle", timeout=8000)
#                         except PWTimeout: pass
#                         robust_scroll(page, max_seconds=8)
#                         return dd

#                     try:
#                         dd = with_retries(fetch_detail, retries=2, base_sleep=1.2)
#                         record.update(dd)
#                         time.sleep(random.uniform(0.25, 0.6))
#                     except Exception as e:
#                         record["detail_error"] = str(e)[:200]
#                         # if detail fails repeatedly, continue—don't kill the run

#                 data.append(record)
#                 nid += 1
#                 seen.add(key)

#             save_all(data)
#             context.close(); browser.close()

# if __name__ == "__main__":
#     try:
#         main()
#     except KeyboardInterrupt:
#         print("\nStopped by user. Current progress saved.")



# from playwright.sync_api import sync_playwright

# def main():
#     with sync_playwright() as p:
#         browser = p.chromium.launch(headless=False)
#         page = browser.new_page()
#         page.goto("https://www.monster.com/jobs/")
#         print("Hey, we are on Monster jobs page!")
#         page.fill('input[name="q"]', "Python developer")
#         page.fill('input[name="where"]', "Remote")
#         page.wait_for_selector('button[type="submit" i], button[data-testid="search-button"]')
#         page.click('button[type="submit" i], button[data-testid="search-button"]')
#         input("Press Enter to close the browser...")
#         browser.close()

# if __name__ == "__main__":
#     main()

# monster_basic.py
# Playwright (sync) — simple, robust, human-ish Monster scraper
# pip install playwright && playwright install

import json, time, random, re
from pathlib import Path
from urllib.parse import quote_plus
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ========= CONFIG =========
OUT_FILE = Path("monster_jobs_basic.json")
KEYWORDS = ["python developer", "backend engineer"]
LOCATIONS = ["Remote", "New York, NY"]
HEADLESS = False          # headed reduces detection; set True for CI
HUMAN_FORM_RATIO = 0.25   # 0..1 — how often to simulate homepage form (stealth)
SCROLL_SECONDS = 20       # how long to scroll on results
FETCH_DETAILS = False     # visit each job page for description (slower)

UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

def search_url(q, where):
    return f"https://www.monster.com/jobs/search/?q={quote_plus(q)}&where={quote_plus(where)}"

def accept_cookies(page):
    for sel in [
        "#onetrust-accept-btn-handler",
        "button[aria-label='Accept all']",
        "button:has-text('Accept All')",
        "button:has-text('I Agree')",
    ]:
        try:
            el = page.locator(sel).first
            if el.is_visible():
                el.click()
                break
        except: pass

def stealthify(page):
    page.add_init_script("""
      Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
      window.chrome = window.chrome || { runtime: {} };
      const orig = Notification && Notification.permission;
      const oq = navigator.permissions && navigator.permissions.query;
      if (oq) {
        navigator.permissions.query = (p) => (
          p && p.name === 'notifications'
          ? Promise.resolve({ state: orig })
          : oq(p)
        );
      }
      Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3] });
      Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
    """)

def human_wiggle(page):
    vp = page.viewport_size
    if not vp: return
    w, h = vp["width"], vp["height"]
    for _ in range(random.randint(2,4)):
        x = random.randint(40, w-40); y = random.randint(90, h-90)
        page.mouse.move(x, y, steps=random.randint(8,18))
        time.sleep(random.uniform(0.05, 0.15))

def human_type(page, selector, text):
    # Type like a human (slower & less botty than .fill)
    page.click(selector, timeout=8000)
    page.locator(selector).clear()
    for ch in text:
        page.keyboard.type(ch)
        time.sleep(random.uniform(0.02, 0.08))

def robust_scroll(page, seconds=20):
    t0 = time.time()
    last_h = 0
    while time.time() - t0 < seconds:
        # Try "Load more" if present
        try:
            btn = page.locator("button:has-text('Load more')")
            if btn and btn.first.is_visible():
                btn.first.click()
                page.wait_for_load_state("networkidle", timeout=8000)
        except: pass

        page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        time.sleep(random.uniform(0.5, 1.0))
        human_wiggle(page)

        new_h = page.evaluate("document.body.scrollHeight")
        if new_h == last_h:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight - 600)")
            time.sleep(random.uniform(0.3, 0.7))
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(0.5)
            if page.evaluate("document.body.scrollHeight") == new_h:
                break
        last_h = new_h

def parse_list(page):
    # Monster's current (stable) data-testids
    cards = page.locator("div#JobCardGrid article[data-testid='svx_jobCard']")
    n = cards.count()
    out = []
    for i in range(n):
        c = cards.nth(i)
        a = c.locator("a[data-testid='jobTitle']")
        if a.count() == 0:
            continue
        title = a.first.inner_text().strip()
        href  = a.first.get_attribute("href") or ""
        try:
            company = c.locator("span[data-testid='company']").first.inner_text().strip()
        except: company = ""
        try:
            location = c.locator("span[data-testid='jobDetailLocation']").first.inner_text().strip()
        except: location = ""
        out.append({
            "title": title, "url": href, "company": company, "location": location
        })
    return out

def parse_detail(page):
    # Optional, slower
    title = ""
    for sel in ("[data-testid='jobTitle']", "h1", "h2"):
        try:
            if page.locator(sel).first.is_visible():
                title = page.locator(sel).first.inner_text().strip(); break
        except: pass
    desc = ""
    for sel in ("[data-testid='jobDescription']", "section#JobDescription", "div#JobDescription", "article"):
        try:
            if page.locator(sel).first.is_visible():
                raw = page.locator(sel).first.inner_text().strip()
                desc = " ".join(raw.split()); break
        except: pass
    return {"detail_title": title, "description": desc}

def save(rows):
    OUT_FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf-8")

def run():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
            slow_mo=random.randint(20, 60),
        )
        ctx = browser.new_context(
            user_agent=random.choice(UA_POOL),
            viewport={"width": random.randint(1280, 1600), "height": random.randint(820, 1040)},
            locale="en-US",
            timezone_id="America/New_York",
            geolocation={"latitude": 40.73, "longitude": -73.93},
            permissions=["geolocation"],
        )
        page = ctx.new_page()
        stealthify(page)

        for kw in KEYWORDS:
            for loc in LOCATIONS:
                try:
                    if random.random() < HUMAN_FORM_RATIO:
                        # --- Human path: homepage -> type -> search
                        page.goto("https://www.monster.com/jobs", wait_until="domcontentloaded", timeout=45000)
                        accept_cookies(page)
                        try: page.wait_for_load_state("networkidle", timeout=8000)
                        except PWTimeout: pass
                        human_wiggle(page)

                        # Inputs can vary; try the common ones first
                        # Name attributes often: q (keyword), where (location)
                        human_type(page, 'input[name="q"]', kw)
                        time.sleep(random.uniform(0.2, 0.6))
                        human_type(page, 'input[name="where"]', loc)
                        time.sleep(random.uniform(0.3, 0.8))

                        # Click search — try multiple robust selectors
                        for sel in [
                            'button[type="submit"]',
                            'button[data-testid="search-button"]',
                            'button:has-text("Search")',
                        ]:
                            try:
                                if page.locator(sel).first.is_visible():
                                    page.locator(sel).first.click()
                                    break
                            except: pass

                        try: page.wait_for_load_state("networkidle", timeout=10000)
                        except PWTimeout: pass
                    else:
                        # --- Direct results (fast & reliable)
                        page.goto(search_url(kw, loc), wait_until="domcontentloaded", timeout=45000)
                        accept_cookies(page)
                        try: page.wait_for_load_state("networkidle", timeout=8000)
                        except PWTimeout: pass

                    human_wiggle(page)
                    robust_scroll(page, seconds=SCROLL_SECONDS)

                    rows = parse_list(page)
                    if FETCH_DETAILS:
                        for r in rows:
                            if not r.get("url"):
                                continue
                            try:
                                page.goto(r["url"], wait_until="domcontentloaded", timeout=45000)
                                try: page.wait_for_load_state("networkidle", timeout=8000)
                                except PWTimeout: pass
                                human_wiggle(page)
                                r.update(parse_detail(page))
                            except Exception as e:
                                r["detail_error"] = str(e)[:200]
                                # keep going

                    for r in rows:
                        r.update({"keyword": kw, "query_location": loc, "source": "monster"})
                    results.extend(rows)
                    save(results)  # incremental save
                except Exception as e:
                    # soft-fail per combo
                    results.append({"keyword": kw, "query_location": loc, "error": str(e)[:200], "source": "monster"})
                    save(results)

        print(f"✓ Done. Collected {len(results)} rows → {OUT_FILE}")
        if not HEADLESS:
            input("Press Enter to close…")
        ctx.close(); browser.close()

if __name__ == "__main__":
    run()

