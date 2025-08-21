from playwright.sync_api import sync_playwright
import time, json, os, re, random, signal, sys
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from copy import deepcopy
from typing import List, Dict, Any, Tuple

# =================== Config ===================
OUTPUT_FILE = "dice_jobs.json"
HEADLESS = bool(int(os.getenv("HEADLESS", "0")))
CHECKPOINT_EVERY = 50                # save every N jobs
PAGELOAD_TIMEOUT = 35000
DETAIL_TIMEOUT = 25000
MAX_SCROLLS_PER_PAGE = 40
SCROLL_PAUSE_RANGE = (0.7, 1.5)
NAV_PAUSE_RANGE = (0.9, 2.0)
DETAIL_RESET_EVERY = 120             # recreate detail tab every X jobs to avoid bloat
DEFAULT_LOCATION = "Remote"

DEFAULT_KEYWORDS: List[str] = [
    "python developer", "software engineer", "backend engineer", "full stack developer",
    "react developer", "node.js developer", "java developer", "golang developer",
    "django developer", "data engineer", "machine learning engineer", "devops engineer",
    "cloud engineer", "android developer", "ios developer", "qa automation engineer",
    "sdet", "data scientist", "site reliability engineer", "platform engineer"
]

# =================== Stop flag ===================
STOP_REQUESTED = False
def _sig_handler(signum, frame):
    global STOP_REQUESTED
    STOP_REQUESTED = True
    print("\n🛑 Received stop — finishing current cycle and saving…")
signal.signal(signal.SIGINT, _sig_handler)
signal.signal(signal.SIGTERM, _sig_handler)

# =================== Utils ===================
def rand_pause(a=0.8, b=1.8):
    time.sleep(random.uniform(a, b))

def write_json_atomic(path: str, data: List[Dict[str, Any]]):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)

def load_existing(path: str) -> Tuple[List[Dict[str, Any]], int, set, set]:
    if not os.path.exists(path):
        return [], 1, set(), set()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    next_id = (max([r.get("id", 0) for r in data]) + 1) if data else 1
    seen_urls = {r.get("url") for r in data if r.get("url")}
    seen_jobids = {str(r.get("job_id")) for r in data if r.get("job_id")}
    return data, next_id, seen_urls, seen_jobids

def ensure_checkpoint(results: List[Dict[str, Any]]):
    write_json_atomic(OUTPUT_FILE, results)
    print(f"💾 Checkpoint saved: {len(results)} jobs")

def accept_cookies(page):
    try:
        if page.is_visible("button#onetrust-accept-btn-handler", timeout=3000):
            page.click("button#onetrust-accept-btn-handler")
            print("🍪 Accepted cookies (OneTrust)")
            return
    except: pass
    try:
        shadow_host = page.query_selector("div#cmpwrapper")
        if shadow_host:
            root = shadow_host.evaluate_handle("el => el.shadowRoot")
            if root:
                btn = root.query_selector("button#cmpboxbtnyes") or root.query_selector("button[aria-label='Allow all']")
                if btn:
                    btn.click()
                    print("🍪 Accepted cookies (Shadow DOM CMP)")
                    return
    except: pass
    print("🍪 No cookie popup (or already accepted)")

def debug_precise(page):
    try:
        article_count = page.evaluate("() => document.querySelectorAll('article').length")
        print(f"🧠 DOM <article> count: {article_count}")
    except: pass
    try:
        container_html = page.evaluate("""
            () => {
              const el = document.querySelector("div.m-px.mx-auto.max-w-screen-2xl");
              return el ? el.innerText.slice(0, 300) : "❌ Container not found";
            }
        """)
        print(f"🔍 Container preview:\n{container_html}\n")
    except: pass

def progressive_scroll_until_stable(page, get_cards, max_scrolls=40, px=1600):
    last_count, stagnation = -1, 0
    for _ in range(max_scrolls):
        if STOP_REQUESTED: break
        page.mouse.wheel(0, px)
        rand_pause(*SCROLL_PAUSE_RANGE)
        try:
            count = get_cards().count()
        except:
            count = 0
        if count == last_count:
            stagnation += 1
        else:
            stagnation, last_count = 0, count
        if stagnation >= 3:
            break

def add_or_inc_page_param(url: str, target_page_index: int) -> str:
    """Ensure ?page=N is set to given target_page_index (1-based)."""
    u = urlparse(url)
    qs = parse_qs(u.query)
    qs["page"] = [str(target_page_index)]
    new_query = urlencode(qs, doseq=True)
    return urlunparse((u.scheme, u.netloc, u.path, u.params, new_query, u.fragment))

def parse_job_id_from_url(url: str) -> str:
    if not url: return ""
    m = re.search(r"/job-detail/[^/]+/(\d+)", url)
    if m: return m.group(1)
    m = re.search(r"[?&]jid=(\d+)", url)
    if m: return m.group(1)
    m = re.search(r"(\d{6,})$", url.rstrip("/"))
    return m.group(1) if m else ""

# =================== Field extractors ===================
SALARY_RX = re.compile(
    r"(\$|USD|US\$)\s?[\d,]+(?:\s?-\s?|\s?to\s?)[\d,]+(?:\s?(?:/year|/yr|/hour|/hr|yr|hr|annum|annual))?|"
    r"(\$|USD|US\$)\s?[\d,]+(?:\s?(?:/year|/yr|/hour|/hr|yr|hr|annum|annual))|"
    r"[\d,]+\s?(?:-\s?|to\s?)[\d,]+\s?(?:k|K)\s?(?:/year|/yr|yr|annual)?",
    re.IGNORECASE
)

EMPLOYMENT_HINTS = [
    "Employment Type", "Employment", "Job Type", "Type", "Work Type",
    "Work Arrangement", "Contract Type"
]
LOCATION_HINTS = ["Location", "Job Location", "Onsite Location"]

def text_or_empty(el):
    try:
        return el.inner_text().strip()
    except:
        return ""

def first_text(page, selectors: List[str]) -> str:
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el:
                t = el.inner_text().strip()
                if t:
                    return t
        except: pass
    return ""

def sanitize_salary(txt: str) -> str:
    """Only accept strings that contain a valid salary-like pattern."""
    if not txt: return ""
    # discard long paragraphs
    if len(txt) > 180:
        return ""
    # try to extract the first valid match
    m = SALARY_RX.search(txt)
    return m.group(0).strip() if m else ""

def parse_quick_facts_map(page) -> Dict[str, str]:
    """
    Build a dict from the 'quick facts' section when present.
    We scope to ul[data-testid='job-quick-facts'] to avoid grabbing JD content.
    """
    result = {}
    try:
        ul = page.query_selector("ul[data-testid='job-quick-facts']")
        if not ul:
            return result
        items = ul.query_selector_all("li")
        for li in items:
            raw = text_or_empty(li)
            # Try split by colon
            if ":" in raw:
                k, v = raw.split(":", 1)
                result[k.strip()] = v.strip()
            else:
                # Try split by newline (label on first line, value on next)
                parts = [p.strip() for p in raw.splitlines() if p.strip()]
                if len(parts) >= 2 and len(parts[0]) <= 40:
                    result[parts[0]] = parts[1]
    except: pass
    return result

def extract_from_quick_facts(page) -> Dict[str, str]:
    facts = parse_quick_facts_map(page)
    out = {"salary": "", "employment_type": "", "location": ""}

    # employment
    for key in EMPLOYMENT_HINTS:
        if key in facts and facts[key]:
            out["employment_type"] = facts[key]
            break

    # location
    for key in LOCATION_HINTS:
        if key in facts and facts[key]:
            out["location"] = facts[key]
            break

    # salary
    for k in list(facts.keys()):
        if any(h.lower() in k.lower() for h in ["salary", "compensation", "pay", "rate"]):
            s = sanitize_salary(facts[k])
            if s:
                out["salary"] = s
                break

    # Fallback: if salary still empty, scan text within quick facts for salary-like substrings
    if not out["salary"]:
        try:
            quick_text = page.query_selector("ul[data-testid='job-quick-facts']").inner_text()
            s = sanitize_salary(quick_text)
            if s:
                out["salary"] = s
        except: pass

    return out

def extract_on_dice_detail(jp):
    # Primary fields
    title = first_text(jp, ["h1[data-cy='jobTitle']", "h1", "header h1"])
    company = first_text(jp, ["a[data-cy='companyNameLink']", "[data-cy='companyNameLink']", "a[href*='company']"])
    location = first_text(jp, ["li[data-cy='jobLocation']", "[data-cy='jobLocation']"])

    posted = first_text(jp, ["li[data-cy='postedDate']", "[data-cy='postedDate']"])
    employment = first_text(jp, ["li[data-cy='employmentType']", "[data-cy='employmentType']"])
    # description (broader)
    description = first_text(jp, [
        "div.job-description",
        "div[data-cy='jobDescription']",
        "section[data-cy='jobDescription']",
        "article",
        "main"
    ])

    # Quick facts map for robust extraction/sanitization
    facts = extract_from_quick_facts(jp)
    if not employment:
        employment = facts["employment_type"]
    if not location:
        location = facts["location"]
    salary = facts["salary"]

    return title, company, location, posted, employment, salary, description

def extract_on_generic(jp):
    # Fallback for external ATS pages
    title = first_text(jp, ["h1", "header h1", "h1[class*='title']", "h1[itemprop='title']"])
    company = first_text(jp, ["[itemprop='hiringOrganization']", "a[href*='company']", "span[class*='company']"])
    location = first_text(jp, ["[itemprop='jobLocation']", "span[class*='location']"])
    posted = first_text(jp, ["time[datetime]", "time"])
    employment = ""
    description = first_text(jp, ["[itemprop='description']", "section[role='main']", "article", "main"])

    # Try to read labeled facts-like blocks
    facts = extract_from_quick_facts(jp)
    if not employment:
        employment = facts["employment_type"]
    if not location:
        location = facts["location"]
    salary = facts["salary"]

    # If still no salary, crawl visible text and pick first salary-like token (bounded)
    if not salary:
        try:
            snippet = jp.evaluate("() => document.body.innerText.slice(0, 20000)")
            salary = sanitize_salary(snippet)
        except: pass

    return title, company, location, posted, employment, salary, description

# =================== Pagination helpers ===================
NEXT_SELECTORS = [
    "button[aria-label='Next Page']",
    "[data-testid='pagination-next-button']",
    "nav[aria-label='Pagination'] >> text=Next",
    "a[rel='next']",
    "button:has-text('Next')"
]

def click_next_or_url_fallback(page, page_index: int) -> Tuple[bool, int]:
    """
    Try UI click to go next. If can't, use URL fallback (?page=N+1).
    Returns (went_next, new_page_index)
    """
    # make sure pagination bar is visible
    try:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        rand_pause(0.4, 0.9)
    except: pass

    for sel in NEXT_SELECTORS:
        try:
            el = page.query_selector(sel)
            if not el: continue
            if not el.is_visible():
                page.evaluate("(e) => e.scrollIntoView({block:'center'})", el)
                rand_pause(0.2, 0.5)
            aria_dis = el.get_attribute("aria-disabled")
            disabled = (aria_dis == "true")
            if disabled:
                continue
            # Try normal click
            try:
                el.click()
            except:
                # JS click fallback
                try:
                    page.evaluate("(e) => e.click()", el)
                except:
                    continue
            # wait new content
            page.wait_for_load_state("domcontentloaded")
            rand_pause(*NAV_PAUSE_RANGE)
            page.wait_for_load_state("networkidle")
            return True, page_index + 1
        except:
            continue

    # URL fallback
    try:
        next_url = add_or_inc_page_param(page.url, page_index + 1)
        if next_url != page.url:
            page.goto(next_url, wait_until="domcontentloaded")
            rand_pause(*NAV_PAUSE_RANGE)
            page.wait_for_load_state("networkidle")
            return True, page_index + 1
    except:
        pass

    return False, page_index

# =================== Core scraping ===================
def open_context(p):
    browser = p.chromium.launch(headless=HEADLESS, args=[
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
    ])
    ctx = browser.new_context(
        viewport={"width": 1400, "height": 900},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36",
    )
    return browser, ctx

def safe_new_page(ctx):
    # sometimes ctx is dead; this will raise
    return ctx.new_page()

def scrape_keyword(env, keyword: str, location: str, state):
    """
    Scrape all pages for keyword+location.
    env: {'p': playwright, 'browser': browser, 'ctx': ctx}
    state: [results, next_id, seen_urls, seen_jobids]
    """
    results, next_id, seen_urls, seen_jobids = state
    p, browser, ctx = env["p"], env["browser"], env["ctx"]

    def reopen_env():
        print("♻️ Recreating browser/context…")
        try:
            try: env["ctx"].close()
            except: pass
            try: env["browser"].close()
            except: pass
        except: pass
        b, c = open_context(p)
        env["browser"], env["ctx"] = b, c
        return b, c

    # --- open search page (with retry if context is closed) ---
    page_index = 1
    search_url = f"https://www.dice.com/jobs?q={keyword}&location={location}"
    try:
        page = safe_new_page(ctx)
    except Exception as e:
        if "closed" in repr(e).lower():
            browser, ctx = reopen_env()
            page = safe_new_page(ctx)
        else:
            raise
    page.set_default_timeout(PAGELOAD_TIMEOUT)

    print(f"\n🔎 Keyword: {keyword} | Location: {location}")
    print(f"🔗 {search_url}")
    page.goto(search_url, wait_until="domcontentloaded")
    rand_pause(*NAV_PAUSE_RANGE)
    accept_cookies(page)
    page.wait_for_load_state("networkidle")

    total_added_for_keyword = 0
    jobs_since_reset = 0

    # Create one detail tab (recycled)
    def new_detail_page():
        nonlocal ctx
        try:
            jp = ctx.new_page()
        except Exception as e:
            if "closed" in repr(e).lower():
                _, ctx = reopen_env()
                jp = ctx.new_page()
            else:
                raise
        jp.set_default_timeout(DETAIL_TIMEOUT)
        return jp

    jp = new_detail_page()

    while True:
        if STOP_REQUESTED: break

        cards = page.get_by_test_id("job-search-serp-card")
        try:
            cards.first.wait_for(timeout=7000)
        except: pass

        print(f"🖱️ Page {page_index}: scrolling to load cards…")
        progressive_scroll_until_stable(page, lambda: page.get_by_test_id("job-search-serp-card"), max_scrolls=MAX_SCROLLS_PER_PAGE)
        rand_pause(*SCROLL_PAUSE_RANGE)

        try:
            count = cards.count()
        except:
            count = 0
        print(f"📦 Found {count} job cards on page {page_index}")
        if count == 0:
            debug_precise(page)
            # try a hard reload once
            try:
                page.reload(wait_until="domcontentloaded")
                page.wait_for_load_state("networkidle")
                count = page.get_by_test_id("job-search-serp-card").count()
            except: pass
            if count == 0:
                print("⚠️ No cards — stopping this keyword.")
                break

        for i in range(count):
            if STOP_REQUESTED: break
            try:
                card = cards.nth(i)
                href = None
                try:
                    href = card.get_by_test_id("job-search-job-card-link").get_attribute("href")
                except:
                    try:
                        href = card.locator("a").first.get_attribute("href")
                    except:
                        href = None
                if not href:
                    print(f"⚠️ Card {i+1}: no href; skipping.")
                    continue

                url = href if href.startswith("http") else ("https://www.dice.com" + href)
                if url in seen_urls:
                    continue

                # Rotate detail tab occasionally
                if jobs_since_reset and jobs_since_reset % DETAIL_RESET_EVERY == 0:
                    try: jp.close()
                    except: pass
                    jp = new_detail_page()
                    jobs_since_reset = 0

                # Open detail with redirect capture
                original_url = url
                try:
                    resp = jp.goto(url, wait_until="domcontentloaded")
                except Exception as e:
                    if "closed" in repr(e).lower():
                        # detail page died; recreate and retry once
                        try: jp.close()
                        except: pass
                        jp = new_detail_page()
                        resp = jp.goto(url, wait_until="domcontentloaded")
                    else:
                        raise
                rand_pause(*NAV_PAUSE_RANGE)
                try:
                    jp.wait_for_load_state("networkidle", timeout=DETAIL_TIMEOUT)
                except: pass

                final_url = jp.url
                redirected = (final_url != original_url)
                redirect_chain = []
                try:
                    req = resp.request if resp else None
                    while req and req.redirected_from:
                        redirect_chain.append(req.redirected_from.url)
                        req = req.redirected_from
                    redirect_chain = list(reversed(redirect_chain))
                except:
                    redirect_chain = []

                is_dice = ("dice.com" in final_url)

                if is_dice:
                    title, company, location_text, posted, employment, salary, description = extract_on_dice_detail(jp)
                else:
                    title, company, location_text, posted, employment, salary, description = extract_on_generic(jp)

                job_id = parse_job_id_from_url(final_url) or parse_job_id_from_url(original_url)
                if job_id and job_id in seen_jobids:
                    seen_urls.add(url)
                    continue

                # Final salary sanitize (avoid wrong JD capture)
                salary = sanitize_salary(salary)

                rec = {
                    "id": next_id,
                    "keyword": keyword,
                    "url": original_url,
                    "final_url": final_url,
                    "redirected": bool(redirected),
                    "redirect_chain": redirect_chain,
                    "job_id": job_id or None,
                    "title": title or "",
                    "company": company or "",
                    "location": location_text or "",
                    "posted": posted or "",
                    "employment_type": employment or "",
                    "salary": salary or "",
                    "description": description or "",
                    "source": "dice" if is_dice else "external"
                }

                results.append(rec)
                seen_urls.add(url)
                if job_id: seen_jobids.add(job_id)
                print(f"✅ [{rec['id']}] {rec['title'][:60]} | {rec['company'][:40]}")
                next_id += 1
                total_added_for_keyword += 1
                jobs_since_reset += 1

                if (next_id - 1) % CHECKPOINT_EVERY == 0:
                    ensure_checkpoint(results)

            except Exception as e:
                print(f"⚠️ Error scraping card {i+1}: {e}")
                continue

        # page-end checkpoint
        ensure_checkpoint(results)
        if STOP_REQUESTED: break

        # Next page
        try:
            went_next, page_index = click_next_or_url_fallback(page, page_index)
            if not went_next:
                print("✅ No more pages for this keyword.")
                break
        except Exception as e:
            print(f"❌ Pagination failed/ended: {e}")
            break

    # Cleanup detail page
    try: jp.close()
    except: pass

    print(f"📈 Added {total_added_for_keyword} jobs for '{keyword}'")
    # update state
    state[1] = next_id

def main():
    print("🚀 Dice multi-keyword scraper starting…")
    results, next_id, seen_urls, seen_jobids = load_existing(OUTPUT_FILE)
    state = [results, next_id, seen_urls, seen_jobids]

    with sync_playwright() as p:
        browser, ctx = open_context(p)
        env = {"p": p, "browser": browser, "ctx": ctx}

        try:
            for kw in DEFAULT_KEYWORDS:
                if STOP_REQUESTED: break
                scrape_keyword(env, kw, DEFAULT_LOCATION, state)
        finally:
            ensure_checkpoint(state[0])
            try: env["ctx"].close()
            except: pass
            try: env["browser"].close()
            except: pass

    print("🏁 Done.")

if __name__ == "__main__":
    main()
