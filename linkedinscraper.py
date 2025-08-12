# from playwright.sync_api import sync_playwright
# import time, os, json

# def linkedin_login_and_scrape(email, password, search_query):
#     with sync_playwright() as p:
#         # ✅ Start persistent browser so login session saves
#         profile_dir = os.path.join(os.getcwd(), "linkedin_profile")
#         browser = p.chromium.launch_persistent_context(profile_dir, headless=False)
#         page = browser.new_page()

#         # 🔐 STEP 1: LOGIN (skip if already logged in)
#         page.goto("https://www.linkedin.com/")
#         time.sleep(2)

#         if email != ".":
#             try:
#                 if page.is_visible("a.nav__button-secondary"):
#                     page.click("a.nav__button-secondary")
#                     time.sleep(2)
#             except: pass

#             try:
#                 if page.is_visible("button:has-text('Sign in with email')"):
#                     page.click("button:has-text('Sign in with email')")
#                     page.wait_for_url("https://www.linkedin.com/login", timeout=10000)
#                     time.sleep(2)
#             except: pass

#             if "login" in page.url:
#                 page.fill('input#username', email)
#                 page.fill('input#password', password)
#                 page.click('button[type=submit]')
#                 time.sleep(5)
#                 if "checkpoint" in page.url:
#                     input("⚠️ Verify manually and hit Enter...")

#             if "feed" not in page.url:
#                 input("⚠️ Still not logged in — finish manually and press Enter...")

#         # 🔎 STEP 2: Search jobs
#         print("🔍 Searching jobs...")
#         search_url = f"https://www.linkedin.com/jobs/search/?keywords={search_query.replace(' ', '%20')}"
#         page.goto(search_url)
#         time.sleep(5)

#         # ⬇️ STEP 3: Scroll to load jobs
#         print("⬇️ Scrolling to load job listings...")
#         scroll_container = page.locator("div.scaffold-layout__list").first
#         scroll_container.hover()
#         scroll_container.click()  # Activate focus

#         for _ in range(30):
#             scroll_container.evaluate("el => el.scrollBy(0, 300)")  # Actually scrolls that area
#             time.sleep(1.5)


#         # 🧱 STEP 4: Grab job cards
#         print("🔍 Grabbing job cards...")
#         job_cards = page.query_selector_all("li.scaffold-layout__list-item div.job-card-container")

#         if not job_cards:
#             print("❌ No job cards found.")
#             with open("linkedin_dump.html", "w", encoding="utf-8") as f:
#                 f.write(page.content())
#             input("🔧 Investigate and press Enter to exit...")
#             return

#         print(f"📦 Found {len(job_cards)} job cards")

#         # 🧠 STEP 5: Scrape details from job pane
#         scraped_jobs = []
#         for i, card in enumerate(job_cards):
#             try:
#                 print(f"➡️ Scraping job {i+1}...")
#                 card.scroll_into_view_if_needed()
#                 card.click()
#                 time.sleep(3)

#                 title = page.locator("div.t-24.job-details-jobs-unified-top-card__job-title").inner_text(timeout=10000)
#                 company = page.locator("div.job-details-jobs-unified-top-card__company-name").inner_text(timeout=10000)
#                 job_description = page.locator("div#job-details").inner_text(timeout=10000)
#                 location_block = page.locator(
#                     "div.job-details-jobs-unified-top-card__primary-description-container > div"
#                 ).inner_text(timeout=10000)


#                 scraped_jobs.append({
#                     "id": i + 1,
#                     "title": title.strip(),
#                     "company": company.strip(),
#                     "location_and_other_details": location_block.strip(),
#                     "job_link": page.url,
#                     "job_description": job_description.strip()
#                 })
#             except Exception as e:
#                 print(f"⚠️ Job {i+1} error: {e}")

#         # 💾 STEP 6: Save to file
#         with open("linkedin_job_details.json", "w", encoding="utf-8") as f:
#             json.dump(scraped_jobs, f, indent=2, ensure_ascii=False)

#         print("✅ Saved jobs to linkedin_job_details.json")
#         input("🧹 Press Enter to close browser...")
#         browser.close()

# # ==== 🔁 RUN IT ====
# if __name__ == "__main__":
#     email = input("📧 Enter your LinkedIn email (or '.' to skip login): ")
#     password = input("🔒 Enter your LinkedIn password (or '.' to skip): ")
#     query = input("🧠 Job search query (e.g. 'python developer'): ")
#     linkedin_login_and_scrape(email, password, query)


# linkedinscraper.py
# from playwright.sync_api import sync_playwright
# import time, os, json

# def linkedin_login_and_scrape(email, password, search_query):
#     with sync_playwright() as p:
#         # ✅ Start persistent browser so login session saves
#         profile_dir = os.path.join(os.getcwd(), "linkedin_profile")
#         browser = p.chromium.launch_persistent_context(profile_dir, headless=False)
#         page = browser.new_page()

#         # 🔐 STEP 1: LOGIN
#         page.goto("https://www.linkedin.com/")
#         time.sleep(2)

#         if email != ".":
#             try:
#                 if page.is_visible("a.nav__button-secondary"):
#                     page.click("a.nav__button-secondary")
#                     time.sleep(2)
#             except: pass

#             try:
#                 if page.is_visible("button:has-text('Sign in with email')"):
#                     page.click("button:has-text('Sign in with email')")
#                     page.wait_for_url("https://www.linkedin.com/login", timeout=10000)
#                     time.sleep(2)
#             except: pass

#             if "login" in page.url:
#                 page.fill('input#username', email)
#                 page.fill('input#password', password)
#                 page.click('button[type=submit]')
#                 time.sleep(5)
#                 if "checkpoint" in page.url:
#                     input("⚠️ Verify manually and hit Enter...")

#             if "feed" not in page.url:
#                 input("⚠️ Still not logged in — finish manually and press Enter...")

#         # 🔎 STEP 2: Search jobs
#         print("🔍 Searching jobs...")
#         search_url = f"https://www.linkedin.com/jobs/search/?keywords={search_query.replace(' ', '%20')}"
#         page.goto(search_url)
#         time.sleep(5)

#         all_jobs = []
#         page_num = 1

#         while True:
#             print(f"\n📄 Processing page {page_num}...")

#             # ✅ Wait for job list to appear
#             scroll_container = page.locator("div.scaffold-layout__list").first
#             scroll_container.hover()
#             scroll_container.click()  # Activate focus

#             for _ in range(30):
#                 scroll_container.evaluate("el => el.scrollBy(0, 300)")  # Actually scrolls that area
#                 time.sleep(1.5)



#             # ✅ Grab job cards
#             job_cards = page.query_selector_all("li.scaffold-layout__list-item div.job-card-container")

#             if not job_cards:
#                 print("❌ No job cards found on page.")
#                 break

#             print(f"📦 Found {len(job_cards)} job cards")

#             # ✅ Scrape each job
#             for i, card in enumerate(job_cards):
#                 try:
#                     print(f"➡️ Scraping job {len(all_jobs)+1}...")
#                     card.scroll_into_view_if_needed()
#                     card.click()
#                     time.sleep(2)

#                     title = page.locator("div.t-24.job-details-jobs-unified-top-card__job-title").inner_text(timeout=10000)
#                     company = page.locator("div.job-details-jobs-unified-top-card__company-name").inner_text(timeout=10000)
#                     location_block = page.locator("div.job-details-jobs-unified-top-card__primary-description-container > div").inner_text(timeout=10000)
#                     job_description = page.locator("div#job-details").inner_text(timeout=10000)

#                     all_jobs.append({
#                         "id": len(all_jobs) + 1,
#                         "title": title.strip(),
#                         "company": company.strip(),
#                         "location_and_other_details": location_block.strip(),
#                         "job_link": page.url,
#                         "job_description": job_description.strip()
#                     })
#                 except Exception as e:
#                     print(f"⚠️ Error scraping job {len(all_jobs)+1}: {e}")

#             # ✅ Check for "Next" button and click
#             try:
#                 next_btn = page.locator("button[aria-label='Page " + str(page_num + 1) + "']")
#                 if next_btn.is_visible():
#                     print("➡️ Moving to next page...")
#                     next_btn.click()
#                     time.sleep(5)
#                     page_num += 1
#                 else:
#                     print("⛔ No next page.")
#                     break
#             except:
#                 print("⛔ Couldn't find next button. Done scraping.")
#                 break

#         # 💾 Save to file
#         with open("linkedin_job_details.json", "w", encoding="utf-8") as f:
#             json.dump(all_jobs, f, indent=2, ensure_ascii=False)

#         print(f"\n✅ Scraped total {len(all_jobs)} jobs. Saved to linkedin_job_details.json")
#         input("🧹 Press Enter to close browser...")
#         browser.close()

# # ==== 🔁 RUN IT ====
# if __name__ == "__main__":
#     email = input("📧 Enter your LinkedIn email (or '.' to skip login): ")
#     password = input("🔒 Enter your LinkedIn password (or '.' to skip): ")
#     query = input("🧠 Job search query (e.g. 'python developer'): ")
#     linkedin_login_and_scrape(email, password, query)

# linkedinscraper_auto.py
from playwright.sync_api import sync_playwright
import time, os, json, re, datetime
from pathlib import Path

# ✅ Built-in tech keywords (edit as you like)
DEFAULT_KEYWORDS = [
    "python developer",
    "software engineer",
    "backend engineer",
    "full stack developer",
    "react developer",
    "node.js developer",
    "java developer",
    "golang developer",
    "django developer",
    "data engineer",
    "machine learning engineer",
    "devops engineer",
    "cloud engineer",
    "android developer",
    "ios developer",
    "qa automation engineer",
    "sdet",
]

# === Helpers ===
def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-") or "keyword"

def human_sleep(a=1.0, b=2.0):
    # simple mid sleep to avoid looking too botty
    t = (a + b) / 2.0
    time.sleep(t)

# === Core per-keyword scraper (keeps your selectors) ===
def scrape_keyword(page, search_query):
    search_url = f"https://www.linkedin.com/jobs/search/?keywords={search_query.replace(' ', '%20')}"
    print(f"\n🔎 Searching: {search_query} -> {search_url}")
    page.goto(search_url)
    time.sleep(5)  # your requirement: wait 5s after goto

    all_jobs = []
    page_num = 1

    while True:
        print(f"\n📄 Processing page {page_num} for '{search_query}'...")
        try:
            # Left list container focus (unchanged target)
            scroll_container = page.locator("div.scaffold-layout__list").first
            scroll_container.wait_for(state="visible", timeout=15000)
            scroll_container.hover()
            scroll_container.click()
        except Exception as e:
            print(f"❌ Couldn't focus job list container: {e}")
            break

        # Scroll to load more cards
        for _ in range(30):
            try:
                scroll_container.evaluate("el => el.scrollBy(0, 350)")
            except:
                pass
            time.sleep(1.3)

        # ✅ Same job card selector you confirmed works
        job_cards = page.query_selector_all("li.scaffold-layout__list-item div.job-card-container")
        if not job_cards:
            print("❌ No job cards found on page.")
            break

        print(f"📦 Found {len(job_cards)} job cards")

        # Open each card to read the right-side detail panel (same selectors)
        for _i, card in enumerate(job_cards):
            try:
                idx = len(all_jobs) + 1
                print(f"➡️ Scraping job {idx}...")
                card.scroll_into_view_if_needed()
                card.click()
                time.sleep(2)

                # ⬇️ Same detail selectors as your previous logic
                title = page.locator("div.t-24.job-details-jobs-unified-top-card__job-title").inner_text(timeout=10000)
                company = page.locator("div.job-details-jobs-unified-top-card__company-name").inner_text(timeout=10000)
                location_block = page.locator("div.job-details-jobs-unified-top-card__primary-description-container > div").inner_text(timeout=10000)
                job_description = page.locator("div#job-details").inner_text(timeout=10000)

                all_jobs.append({
                    "id": idx,
                    "keyword": search_query,
                    "title": title.strip(),
                    "company": company.strip(),
                    "location_and_other_details": location_block.strip(),
                    "job_link": page.url,
                    "job_description": job_description.strip()
                })
            except Exception as e:
                print(f"⚠️ Error scraping job {len(all_jobs)+1}: {e}")

        # Pagination: identical behavior
        try:
            next_btn = page.locator(f"button[aria-label='Page {page_num + 1}']")
            if next_btn.is_visible():
                print("➡️ Moving to next page...")
                next_btn.click()
                time.sleep(5)
                page_num += 1
            else:
                print("⛔ No next page.")
                break
        except Exception as e:
            print(f"⛔ Couldn't find next button. Done scraping. ({e})")
            break

    return all_jobs

def linkedin_login_and_scrape_batch(email, password):
    out_root = Path("linkedin_out") / datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_root.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        # ✅ Persistent profile so login sticks
        profile_dir = os.path.join(os.getcwd(), "linkedin_profile")
        browser = p.chromium.launch_persistent_context(profile_dir, headless=False)
        page = browser.new_page()

        # 🔐 Login (same flow)
        page.goto("https://www.linkedin.com/")
        time.sleep(2)

        if email != ".":
            try:
                if page.is_visible("a.nav__button-secondary"):
                    page.click("a.nav__button-secondary")
                    time.sleep(2)
            except: pass

            try:
                if page.is_visible("button:has-text('Sign in with email')"):
                    page.click("button:has-text('Sign in with email')")
                    page.wait_for_url("https://www.linkedin.com/login", timeout=10000)
                    time.sleep(2)
            except: pass

            if "login" in page.url:
                page.fill('input#username', email)
                page.fill('input#password', password)
                page.click('button[type=submit]')
                time.sleep(5)
                if "checkpoint" in page.url:
                    input("⚠️ Verify manually (OTP/captcha) and hit Enter...")

            if "feed" not in page.url and "jobs" not in page.url:
                input("⚠️ Still not logged in — finish manually and press Enter...")

        # 🧠 Always use DEFAULT_KEYWORDS (no prompt)
        keywords = DEFAULT_KEYWORDS
        print(f"\n🚀 Running for {len(keywords)} keyword(s): {keywords}")

        master = []
        for kw in keywords:
            print("\n" + "="*80)
            print(f"🧠 KEYWORD: {kw}")
            print("="*80)
            try:
                records = scrape_keyword(page, kw)
                master.extend(records)

                slug = slugify(kw)
                out_file = out_root / f"linkedin_jobs_{slug}.json"
                with out_file.open("w", encoding="utf-8") as f:
                    json.dump(records, f, indent=2, ensure_ascii=False)
                print(f"✅ Saved {len(records)} jobs for '{kw}' -> {out_file}")
            except KeyboardInterrupt:
                print("⛔ Interrupted by user.")
                break
            except Exception as e:
                print(f"💥 Failed keyword '{kw}': {e}")

            human_sleep(1.5, 3.0)

        # Save the master file
        master_file = out_root / "linkedin_jobs_MASTER.json"
        with master_file.open("w", encoding="utf-8") as f:
            json.dump(master, f, indent=2, ensure_ascii=False)
        print(f"\n🏁 TOTAL: {len(master)} jobs across {len(keywords)} keyword(s).")
        print(f"🗂  Output folder: {out_root.resolve()}")
        input("🧹 Press Enter to close browser...")
        browser.close()

# ==== RUN ====
if __name__ == "__main__":
    print("LinkedIn Batch Scraper 🔧 (Autopilot)")
    email = input("📧 Enter your LinkedIn email (or '.' to skip login): ").strip()
    password = input("🔒 Enter your LinkedIn password (or '.' to skip): ").strip()
    linkedin_login_and_scrape_batch(email, password)
