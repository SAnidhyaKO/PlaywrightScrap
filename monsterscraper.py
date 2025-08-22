# monsterscraper_proxies.py
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
MAX_PAGES  = 2
OUT_FILE   = "monster_jobs.json"
HEADLESS   = False

# 👇 Add your proxies here. If empty → will use your own IP
PROXIES = [
    # Example: "http://user:pass@123.45.67.89:8000"
]

# ---------------- HELPERS ---------------- #
def human_delay(min_t=1, max_t=2.5):
    time.sleep(random.uniform(min_t, max_t))

def human_scroll(page):
    try:
        height = page.evaluate("() => document.body.scrollHeight")
        for y in range(0, height, random.randint(400, 700)):
            page.mouse.wheel(0, y)
            human_delay(0.4, 1.2)
    except Exception as e:
        print("⚠️ Scroll failed:", e)

def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ---------------- MAIN ---------------- #
def run_scraper():
    results = []
    job_id = 1

    with sync_playwright() as p:
        for idx, kw in enumerate(KEYWORDS):
            # pick proxy if available
            proxy = None
            if PROXIES:
                proxy = PROXIES[idx % len(PROXIES)]
                print(f"\n🌍 Using proxy: {proxy}")
            else:
                print("\n🌍 Using your own IP (no proxy)")

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

            try:
                print(f"🔎 Searching for: {kw}")
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

                # CAPTCHA pause
                print("⚠️ If CAPTCHA shows, solve it manually now...")
                input("👉 Press Enter when jobs page is visible...")

                # Scrape pages
                for pg in range(1, MAX_PAGES + 1):
                    print(f"📄 Page {pg} for {kw}")
                    human_scroll(page)

                    job_cards = page.locator("section.card-content")
                    count = job_cards.count()
                    print(f"   Found {count} jobs")

                    for i in range(count):
                        try:
                            card = job_cards.nth(i)
                            title = card.locator("h2 a").inner_text(timeout=3000)
                            company = card.locator("div.company span").inner_text(timeout=3000)
                            location = card.locator("div.location span").inner_text(timeout=3000)
                            link = card.locator("h2 a").get_attribute("href")

                            results.append({
                                "id": job_id,
                                "keyword": kw,
                                "title": title.strip(),
                                "company": company.strip(),
                                "location": location.strip(),
                                "link": link
                            })
                            job_id += 1
                        except Exception as e:
                            print("   ⚠️ Job parse failed:", e)

                    save_json(results, OUT_FILE)

                    # Next page
                    try:
                        next_btn = page.locator("a[aria-label='Next']")
                        if next_btn.is_visible():
                            next_btn.click()
                            print("➡️ Next page")
                            human_delay(3, 6)
                        else:
                            break
                    except:
                        break

            except Exception as e:
                print(f"❌ Error for {kw}: {e}")

            browser.close()

        print(f"\n✅ Done. Saved {len(results)} jobs into {OUT_FILE}")

if __name__ == "__main__":
    run_scraper()
