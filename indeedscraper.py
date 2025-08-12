from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import time, json, random, os
from datetime import datetime

def human_sleep(a=0.6, b=1.4):
    time.sleep(random.uniform(a, b))

def accept_cookies(page):
    # Handle various cookie banners Indeed likes to throw around
    selectors = [
        "button:has-text('Accept All')",
        "button:has-text('Accept all')",
        "button:has-text('I accept')",
        "button:has-text('OK')",
        "button[aria-label='Accept']",
        "button#onetrust-accept-btn-handler",
    ]
    for sel in selectors:
        try:
            if page.is_visible(sel, timeout=1000):
                page.click(sel, timeout=1000)
                human_sleep()
                break
        except Exception:
            pass

def slow_scroll(page, container_selector="body", steps=6):
    # Scrolls in chunks to trigger lazy loading
    for _ in range(steps):
        page.evaluate("""sel => {
            const el = document.querySelector(sel) || document.scrollingElement || document.body;
            el.scrollBy(0, Math.floor(window.innerHeight*0.8));
        }""", container_selector)
        human_sleep(0.8, 1.6)

def extract_text(el, selector, default=""):
    try:
        handle = el.query_selector(selector)
        if not handle:
            return default
        txt = handle.inner_text().strip()
        return " ".join(txt.split())
    except Exception:
        return default

def open_job_detail(page, card):
    """
    Clicks the job title link. Indeed often opens a side panel; sometimes a new page.
    We try to get description from side panel first; if not, open in new tab.
    """
    # Prefer the dedicated title link
    link = card.query_selector("a.jcs-JobTitle, a.tapItem")
    if not link:
        return None, None

    # Try side-panel first (click without ctrl/meta)
    with page.expect_event("websocket", timeout=2000) as maybe_ws:
        pass  # noop to keep Playwright happy in some environments

    before = page.url
    link.click()
    human_sleep(0.8, 1.4)

    # Side panel container commonly exists:
    # #vjs-container (legacy) or div#jobDescriptionText inside a detail pane
    # We’ll look for a description region anywhere on the page first.
    try:
        page.wait_for_selector("div#jobDescriptionText, #jobDescriptionText", timeout=3000)
        return "sidepanel", page
    except PlaywrightTimeoutError:
        pass

    # If side panel not found, try opening in a new tab via Ctrl/Cmd+Enter fallback.
    # (Sometimes the click already navigated; check if URL changed significantly)
    if page.url != before:
        # Navigated in same page; try to grab description here
        try:
            page.wait_for_selector("div#jobDescriptionText, #jobDescriptionText", timeout=3000)
            return "navigated", page
        except PlaywrightTimeoutError:
            return None, None

    # Force open in new tab as a last resort
    try:
        with page.context.expect_page() as new_page_info:
            page.keyboard.down("Meta")  # Cmd on mac
            link.click()
            page.keyboard.up("Meta")
        newp = new_page_info.value
        newp.wait_for_load_state("domcontentloaded", timeout=10000)
        human_sleep()
        try:
            newp.wait_for_selector("div#jobDescriptionText, #jobDescriptionText", timeout=5000)
            return "newpage", newp
        except PlaywrightTimeoutError:
            return "newpage", newp
    except Exception:
        return None, None

def get_description_from(scope_page):
    try:
        desc_el = scope_page.query_selector("div#jobDescriptionText, #jobDescriptionText")
        if not desc_el:
            return ""
        raw = desc_el.inner_text().strip()
        # compact a bit
        return "\n".join([line.strip() for line in raw.splitlines() if line.strip()])
    except Exception:
        return ""

def scrape_indeed(keyword="python developer", location="India", max_pages=2, headless=False, slowmo=0):
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=slowmo)
        context = browser.new_context(
            viewport={"width": 1366, "height": 900},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/123.0.0.0 Safari/537.36"),
        )
        page = context.new_page()

        base = "https://in.indeed.com/"
        page.goto(base, wait_until="domcontentloaded", timeout=30000)
        time.sleep(5)  # you asked for a hard wait after goto
        accept_cookies(page)

        # Fill search form (Indeed India homepage form)
        try:
            # Sometimes homepage shows a compact search box with these ids
            page.fill("input[name='q']", keyword, timeout=5000)
        except Exception:
            # fallback: more generic
            q_inputs = page.query_selector_all("input[type='text']")
            if q_inputs:
                q_inputs[0].fill(keyword)

        try:
            page.fill("input[name='l']", location, timeout=3000)
        except Exception:
            pass

        # Submit search
        try:
            if page.is_visible("button[type='submit']", timeout=3000):
                page.click("button[type='submit']")
            else:
                page.keyboard.press("Enter")
        except Exception:
            page.keyboard.press("Enter")

        # Wait for results container
        try:
            page.wait_for_selector("#mosaic-jobResults, div.jobsearch-ResultsList", timeout=15000)
        except PlaywrightTimeoutError:
            print("Search results container not found. UI changed?")
            return results

        current_page = 1
        while current_page <= max_pages:
            print(f"🔎 Page {current_page} …")
            human_sleep(1.0, 1.8)

            # Scroll to load
            slow_scroll(page, container_selector="body", steps=7)

            # Grab all job cards
            cards = page.query_selector_all("div.job_seen_beacon")
            if not cards:
                # fallback older selector
                cards = page.query_selector_all("div.cardOutline")
            print(f"Found {len(cards)} cards")

            for idx, card in enumerate(cards, start=1):
                try:
                    title = extract_text(card, "h2.jobTitle span")
                    if not title:
                        title = extract_text(card, "a.jcs-JobTitle")

                    company = extract_text(card, "span.companyName")
                    loc = extract_text(card, "div.companyLocation")
                    salary = extract_text(card, "div.salary-snippet-container, span.salary-snippet-container, div.metadata.salary-snippet-container")
                    snippet = extract_text(card, "div.job-snippet")
                    posted = extract_text(card, "span.date, span[aria-label*='Posted']") or extract_text(card, "span[aria-label*='posted']")

                    # Open detail and fetch full JD
                    origin, scope = open_job_detail(page, card)
                    full_jd = ""
                    job_url = ""
                    if origin and scope:
                        full_jd = get_description_from(scope)
                        try:
                            job_url = scope.url
                        except Exception:
                            job_url = ""
                        # Close new page if we opened one
                        if origin == "newpage":
                            try:
                                scope.close()
                            except Exception:
                                pass
                        else:
                            # Close side panel if a close button exists (optional)
                            for sel in [
                                "button[aria-label='Close']", 
                                "button:has-text('Close')",
                                "div[aria-label='Close']"
                            ]:
                                try:
                                    if page.is_visible(sel, timeout=500):
                                        page.click(sel)
                                        break
                                except Exception:
                                    pass
                            human_sleep(0.4, 0.9)

                    results.append({
                        "title": title,
                        "company": company,
                        "location": loc,
                        "salary": salary,
                        "snippet": snippet,
                        "posted": posted,
                        "full_description": full_jd,
                        "job_url": job_url,
                        "source_page": page.url,
                        "scraped_at": datetime.utcnow().isoformat() + "Z",
                    })
                    # tiny pause between cards
                    human_sleep(0.4, 0.9)

                except Exception as e:
                    print(f"[Card {idx}] Skipped due to error: {e}")
                    continue

            # Try next page
            current_page += 1
            try:
                # Newer selectors
                next_sel_candidates = [
                    "a[aria-label='Next']",
                    "a[data-testid='pagination-page-next']",
                    "a:has-text('Next')",
                ]
                clicked = False
                for sel in next_sel_candidates:
                    if page.is_enabled(sel, timeout=1500) and page.is_visible(sel, timeout=1500):
                        page.click(sel)
                        clicked = True
                        break
                if not clicked:
                    print("No Next button found; stopping.")
                    break
                page.wait_for_load_state("domcontentloaded", timeout=15000)
                accept_cookies(page)
                human_sleep(1.2, 2.0)
            except Exception:
                print("Pagination failed or no more pages.")
                break

        context.close()
        browser.close()

    # Save
    out = "indeed_results.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"✅ Saved {len(results)} jobs to {os.path.abspath(out)}")
    return results

if __name__ == "__main__":
    # Example run; tweak as you like
    scrape_indeed(
        keyword="python developer",
        location="Remote",
        max_pages=3,
        headless=False,  # set True for stealthy background runs (but debug with False first)
        slowmo=0
    )
