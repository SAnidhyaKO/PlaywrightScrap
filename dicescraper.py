# from playwright.sync_api import sync_playwright
# import time
# import json

# def scrape_dice_jobs(keyword="python", location="Remote"):
#     results = []

#     with sync_playwright() as p:
#         browser = p.chromium.launch(headless=False)
#         context = browser.new_context()
#         page = context.new_page()

#         search_url = f"https://www.dice.com/jobs?q={keyword}&location={location}"
#         print(f"🔗 Navigating to: {search_url}")
#         page.goto(search_url)

#         # Wait for full hydration
#         time.sleep(5)
#         print("⏳ Waited 5s for rendering...")

#         # Try accepting cookie popup from Shadow DOM
#         try:
#             print("🔍 Looking for cookie popup via Shadow DOM...")
#             shadow_host = page.query_selector("div#cmpwrapper")
#             if shadow_host:
#                 shadow_root = shadow_host.evaluate_handle("el => el.shadowRoot")
#                 accept_btn = shadow_root.query_selector("button#cmpboxbtnyes")
#                 if accept_btn:
#                     accept_btn.click()
#                     print("🍪 Cookie accepted.")
#                 else:
#                     print("❌ No accept button in shadow DOM.")
#             else:
#                 print("❌ Shadow host not found.")
#         except Exception as e:
#             print(f"⚠️ Cookie popup error: {e}")

#         page.wait_for_load_state("networkidle")
#         time.sleep(1)

#         try:
#             while True:
#                 print("🖱️ Scrolling to trigger lazy loading...")
#                 page.mouse.wheel(0, 1500)
#                 time.sleep(3)

#                 # Check how many <article> tags JS sees
#                 js_count = page.evaluate("() => document.querySelectorAll('article').length")
#                 print(f"🧠 JS sees {js_count} <article> tags")

#                 print("⏳ Waiting for job container...")
#                 page.wait_for_selector("div.m-px.mx-auto.max-w-screen-2xl.sm\\:px-6", timeout=15000)

#                 job_cards = page.query_selector_all("article[data-testid*='job-search-serp-card']")
#                 print(f"📦 Found {len(job_cards)} job cards")

#                 if not job_cards:
#                     print("🚫 No job cards found on this page.")
#                     break

#                 # Just log first few job cards to debug
#                 for i, card in enumerate(job_cards[:5]):
#                     print(f"\n🔎 Preview Job Card {i+1}:\n{card.inner_text()[:300]}")

#                 # Scrape job card details
#                 for idx, card in enumerate(job_cards):
#                     try:
#                         job_link = card.query_selector("a").get_attribute("href")
#                         if not job_link.startswith("http"):
#                             job_link = "https://www.dice.com" + job_link

#                         print(f"➡️ Opening job {idx + 1}: {job_link}")
#                         job_page = context.new_page()
#                         job_page.goto(job_link)
#                         job_page.wait_for_load_state("networkidle")
#                         time.sleep(2)

#                         def safe_text(selector):
#                             el = job_page.query_selector(selector)
#                             return el.inner_text().strip() if el else ""

#                         title = safe_text("h1")
#                         company = safe_text("a[data-cy='companyNameLink']")
#                         location = safe_text("li[data-cy='jobLocation']")
#                         posted = safe_text("li[data-cy='postedDate']")
#                         emp_type = safe_text("li[data-cy='employmentType']")
#                         salary = safe_text("li[data-cy='salary']")
#                         jd = safe_text("div.job-description")

#                         results.append({
#                             "title": title,
#                             "company": company,
#                             "location": location,
#                             "posted": posted,
#                             "employment_type": emp_type,
#                             "salary": salary,
#                             "description": jd,
#                             "url": job_link
#                         })

#                         job_page.close()
#                     except Exception as e:
#                         print(f"⚠️ Error scraping job {idx + 1}: {e}")
#                         continue

#                 # Pagination
#                 try:
#                     next_btn = page.query_selector("button[aria-label='Next Page']")
#                     if next_btn and not next_btn.is_disabled():
#                         print("⏭️ Going to next page...")
#                         next_btn.click()
#                         page.wait_for_load_state("networkidle")
#                         time.sleep(3)
#                     else:
#                         print("✅ No more pages.")
#                         break
#                 except Exception as e:
#                     print(f"❌ Pagination failed: {e}")
#                     break

#         except Exception as e:
#             print("💥 Major error:", e)

#         finally:
#             with open("dice_jobs.json", "w", encoding="utf-8") as f:
#                 json.dump(results, f, indent=2)
#             print(f"💾 Saved {len(results)} jobs to dice_jobs.json")

#             input("🧪 Press Enter to close browser after inspection...")
#             browser.close()

# if __name__ == "__main__":
#     scrape_dice_jobs("python", "Remote")
from playwright.sync_api import sync_playwright
import time, json, os

# ------------------ COOKIE HANDLER ------------------ #
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
            shadow_root = shadow_host.evaluate_handle("el => el.shadowRoot")
            accept_btn = shadow_root.query_selector("button#cmpboxbtnyes") or shadow_root.query_selector("button[aria-label='Allow all']")
            if accept_btn:
                accept_btn.click()
                print("🍪 Accepted cookies (Shadow DOM CMP)")
                return
    except: pass

    print("🍪 No cookie popup found (or already accepted)")

# ------------------ DEBUG PRECISION MODE ------------------ #
def debug_precise(page):
    article_count = page.evaluate("() => document.querySelectorAll('article').length")
    print(f"🧠 DOM <article> count: {article_count}")

    container_html = page.evaluate("""
        () => {
            const el = document.querySelector("div.m-px.mx-auto.max-w-screen-2xl");
            return el ? el.innerHTML.slice(0, 500) : "❌ Container not found";
        }
    """)
    print(f"🔍 Container preview:\n{container_html}\n")

    test_ids = page.evaluate("""
        () => Array.from(document.querySelectorAll("[data-testid]"))
                   .map(e => e.getAttribute("data-testid"))
                   .slice(0, 20)
    """)
    print(f"🏷️ First 20 data-testids found: {test_ids}")

# ------------------ SCROLL HELPERS ------------------ #
def progressive_scroll(page, steps=6, px=1600, wait=1.0):
    for _ in range(steps):
        page.mouse.wheel(0, px)
        time.sleep(wait)

# ------------------ MAIN SCRAPER ------------------ #
def scrape_dice_jobs(keyword="python", location="Remote"):
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context(
            viewport={"width": 1400, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36"
        )
        page = ctx.new_page()

        search_url = f"https://www.dice.com/jobs?q={keyword}&location={location}"
        print(f"🔗 Navigating to: {search_url}")
        page.goto(search_url)
        time.sleep(5)  # Wait for initial load + popups
        accept_cookies(page)
        page.wait_for_load_state("networkidle")

        try:
            while True:
                print("🖱️ Scrolling to load jobs…")
                progressive_scroll(page)

                cards = page.get_by_test_id("job-search-serp-card")
                try:
                    cards.first.wait_for(timeout=7000)
                except: pass

                count = cards.count()
                print(f"📦 Found {count} job cards")

                if count == 0:
                    print("⚠️ No cards detected — running precise debug…")
                    debug_precise(page)
                    break

                for i in range(count):
                    try:
                        card = cards.nth(i)
                        link_el = card.get_by_test_id("job-search-job-card-link")
                        href = link_el.get_attribute("href") if link_el else card.locator("a").first.get_attribute("href")
                        if not href:
                            continue
                        url = href if href.startswith("http") else "https://www.dice.com" + href
                        print(f"➡️ Opening job {i+1}/{count}: {url}")

                        jp = ctx.new_page()
                        jp.goto(url)
                        jp.wait_for_load_state("networkidle")
                        time.sleep(1.5)

                        def t(sel):
                            el = jp.query_selector(sel)
                            return el.inner_text().strip() if el else ""

                        data = {
                            "title": t("h1"),
                            "company": t("a[data-cy='companyNameLink']"),
                            "location": t("li[data-cy='jobLocation']"),
                            "posted": t("li[data-cy='postedDate']"),
                            "employment_type": t("li[data-cy='employmentType']"),
                            "salary": t("li[data-cy='salary']"),
                            "description": t("div.job-description"),
                            "url": url
                        }
                        results.append(data)
                        jp.close()
                    except Exception as e:
                        print(f"⚠️ Error scraping job {i+1}: {e}")

                try:
                    next_btn = page.locator("button[aria-label='Next Page'], [aria-label='Next'][role='link']").first
                    if next_btn and next_btn.is_enabled():
                        print("⏭️ Going to next page…")
                        next_btn.click()
                        page.wait_for_load_state("networkidle")
                        time.sleep(2)
                    else:
                        print("✅ No more pages.")
                        break
                except Exception as e:
                    print(f"❌ Pagination failed: {e}")
                    break

        except Exception as e:
            print("💥 Fatal error:", e)

        finally:
            with open("dice_jobs.json", "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2)
            print(f"💾 Saved {len(results)} jobs to dice_jobs.json")

            input("🧪 Press Enter to close browser…")
            browser.close()

# ------------------ RUN ------------------ #
if __name__ == "__main__":
    scrape_dice_jobs("python", "Remote")
