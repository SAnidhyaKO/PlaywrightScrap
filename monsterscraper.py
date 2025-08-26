from playwright.sync_api import sync_playwright
import time, random, json

# ---------------- CONFIG ---------------- #
KEYWORDS = [
    "python developer", "software engineer", "backend engineer",
    "full stack developer", "react developer", "node.js developer",
    "java developer", "golang developer", "django developer",
    "data engineer", "machine learning engineer", "devops engineer",
    "cloud engineer", "android developer", "ios developer",
    "qa automation engineer", "sdet", "frontend developer"
]

LOCATION   = "Remote"
MAX_SCROLLS = 20          # how many times to scroll job list
OUT_FILE   = "monster_jobs.json"
HEADLESS   = False

# 👇 Add your proxies here. If empty → will use your own IP
PROXIES = [
    # Example: "http://user:pass@123.45.67.89:8000"
]

# ---------------- HELPERS ---------------- #
def human_delay(min_t=1, max_t=2.5):
    time.sleep(random.uniform(min_t, max_t))

def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def scroll_job_list(page, max_scrolls=20):
    last_count = 0
    for s in range(max_scrolls):
        page.evaluate("""
            () => {
                const sc = document.querySelector("div#JobCardGrid");
                if (sc) sc.scrollBy(0, sc.scrollHeight);
                window.scrollBy(0, 400);  // backup full-page scroll
            }
        """)
        page.wait_for_timeout(2500)  # let jobs lazy-load

        count = page.locator("div#JobCardGrid article[data-testid='JobCard']").count()

        if count == last_count:
            print("   ✅ No new jobs, stopping scroll")
            break
        last_count = count

# ---------------- MAIN ---------------- #
def run_scraper():
    results = []
    job_id = 1

    with sync_playwright() as p:
        proxy = None
        if PROXIES:
            proxy = PROXIES[0]   # rotate later if needed
            print(f"\n🌍 Using proxy: {proxy}")
        else:
            print("\n🌍 Using your own IP (no proxy)")

        # ✅ Reuse the same browser & page
        browser = p.firefox.launch(
            headless=HEADLESS,
            proxy={"server": proxy} if proxy else None
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3) "
                       "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
            locale="en-US",
            timezone_id="America/New_York",
        )
        context.add_init_script("""
            Object.defineProperty(navigator, 'platform', {get: () => 'MacIntel'});
            Object.defineProperty(navigator, 'vendor', {get: () => 'Apple Computer, Inc.'});
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        page = context.new_page()

        for kw in KEYWORDS:
            try:
                print(f"\n🔎 Searching for: {kw}")
                page.goto("https://www.monster.com/jobs/", timeout=60000)
                page.wait_for_load_state("networkidle")
                human_delay(2, 4)

                # Fill keyword
                try:
                    kw_box = page.locator("input[name='q']").first
                    kw_box.fill("")
                    for char in kw:
                        page.keyboard.type(char, delay=random.randint(80, 150))
                    print("✅ Keyword entered")
                except Exception as e:
                    print("⚠️ Keyword input fail:", e)

                # Fill location
                try:
                    loc_box = page.locator("input[name='where']").first
                    loc_box.fill("")
                    for char in LOCATION:
                        page.keyboard.type(char, delay=random.randint(80, 150))
                    print("✅ Location entered")
                except Exception as e:
                    print("⚠️ Location input fail:", e)

                # Click search
                try:
                    search_btn = page.locator("button[data-testid='searchbar-submit-button-desktop']").first
                    search_btn.click()
                    print("🔎 Submitted search")
                except Exception as e:
                    print("⚠️ Search button fail:", e)

                # Wait for captcha manual solve
                print("⚠️ If CAPTCHA shows, solve it now...")
                input("👉 Press Enter once you see job cards...")

                # -------- SCRAPE JOBS --------
                print(f"📄 Collecting jobs for {kw}")
                scroll_job_list(page, MAX_SCROLLS)

                job_cards = page.locator("div#JobCardGrid article[data-testid='JobCard']")
                count = job_cards.count()
                print(f"   Found {count} jobs after scrolling")

                for i in range(count):
                    try:
                        card = job_cards.nth(i)

                        title_el = card.locator("a[data-testid='jobTitle']")
                        company_el = card.locator("span[data-testid='company']")
                        location_el = card.locator("span[data-testid='jobDetailLocation']")

                        title = title_el.inner_text(timeout=2000)
                        company = company_el.inner_text(timeout=2000)
                        location = location_el.inner_text(timeout=2000)
                        link = title_el.get_attribute("href")

                        results.append({
                            "id": job_id,
                            "keyword": kw,
                            "title": title.strip(),
                            "company": company.strip(),
                            "location": location.strip(),
                            "link": "https://www.monster.com" + link if link and link.startswith("//") else link
                        })
                        job_id += 1
                        print(f"   ✅ Saved job {job_id-1}: {title[:50]}")

                    except Exception as e:
                        print(f"   ⚠️ Job parse failed at index {i}: {e}")
                        print("   --- Outer HTML snippet ---")
                        print(card.inner_html()[:400])

                save_json(results, OUT_FILE)

            except Exception as e:
                print(f"❌ Error for {kw}: {e}")

        browser.close()
        print(f"\n✅ Done. Saved {len(results)} jobs into {OUT_FILE}")

if __name__ == "__main__":
    run_scraper()
