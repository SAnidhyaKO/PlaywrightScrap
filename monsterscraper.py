# from playwright.sync_api import sync_playwright
# import time, json, random

# def random_mouse_activity(page):
#     # simulate random mouse movement and click
#     for _ in range(random.randint(2, 4)):
#         x = random.randint(100, 1000)
#         y = random.randint(100, 600)
#         page.mouse.move(x, y)
#         if random.random() > 0.5:
#             page.mouse.click(x, y)
#         time.sleep(random.uniform(1, 2))

# def human_scroll(page, times=6):
#     for _ in range(times):
#         page.mouse.wheel(0, random.randint(300, 600))
#         time.sleep(random.uniform(1.2, 2.5))

# def looks_blocked(content):
#     keywords = ["access denied", "unusual activity", "captcha", "puzzle", "blocked"]
#     return any(word in content.lower() for word in keywords)

# def scrape_monster_us(query="backend developer", location="united states", max_jobs=20):
#     with sync_playwright() as p:
#         browser = p.chromium.launch(
#             headless=False,
#             args=["--disable-blink-features=AutomationControlled", "--incognito"]
#         )
#         context = browser.new_context(
#             user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/115.0.0.0 Safari/537.36",
#             locale="en-US"
#         )
#         page = context.new_page()

#         search_url = f"https://www.monster.com/jobs/search?q={query.replace(' ', '-')}&where={location.replace(' ', '-')}"
#         print(f"🌍 Visiting: {search_url}")
#         page.goto(search_url)
#         time.sleep(random.uniform(3, 5))

#         # Run anti-bot behavior
#         random_mouse_activity(page)
#         human_scroll(page)

#         if looks_blocked(page.content()):
#             print("🚨 Blocked by bot detection. Solve CAPTCHA manually...")
#             input("⏳ Press Enter after solving it manually...")

#         # Scrape job cards
#         jobs = []
#         cards = page.query_selector_all("section.card-content")
#         print(f"📦 Found {len(cards)} job cards.")

#         for card in cards[:max_jobs]:
#             try:
#                 title = card.query_selector("h2.title")
#                 company = card.query_selector("div.company")
#                 loc = card.query_selector("div.location")
#                 date = card.query_selector("time")
#                 link = card.query_selector("a")

#                 if not all([title, company, loc, link]):
#                     continue

#                 job = {
#                     "title": title.inner_text().strip(),
#                     "company": company.inner_text().strip(),
#                     "location": loc.inner_text().strip(),
#                     "posted": date.inner_text().strip() if date else None,
#                     "link": link.get_attribute("href")
#                 }
#                 jobs.append(job)
#                 print(f"✅ {job['title']} @ {job['company']}")
#                 time.sleep(random.uniform(1, 2.5))  # human-like delay

#             except Exception as e:
#                 print(f"❌ Error scraping job: {e}")
#                 continue

#         # Save to JSON
#         with open("monster_jobs.json", "w", encoding="utf-8") as f:
#             json.dump(jobs, f, indent=2, ensure_ascii=False)

#         print(f"\n🎉 DONE. {len(jobs)} jobs saved to 'monster_jobs.json'")
#         input("🧪 Press Enter to close the browser after review...")
#         browser.close()

# if __name__ == "__main__":
#     scrape_monster_us("backend engineer", "united states", max_jobs=15)

from playwright.sync_api import sync_playwright
import time, json, random

def scrape_loaded_jobs(page, max_jobs=50):
    print("🔽 Scrolling a bit just in case...")
    for _ in range(3):
        page.keyboard.press("End")
        time.sleep(random.uniform(1.5, 2.5))

    print("🔍 Scraping jobs...")
    jobs = []
    cards = page.query_selector_all("section.card-content")
    print(f"📦 Found {len(cards)} job cards on current screen.")

    for card in cards[:max_jobs]:
        try:
            title = card.query_selector("h2.title")
            company = card.query_selector("div.company")
            loc = card.query_selector("div.location")
            date = card.query_selector("time")
            link = card.query_selector("a")

            if not all([title, company, loc, link]):
                continue

            job = {
                "title": title.inner_text().strip(),
                "company": company.inner_text().strip(),
                "location": loc.inner_text().strip(),
                "posted": date.inner_text().strip() if date else None,
                "link": link.get_attribute("href")
            }

            jobs.append(job)
            print(f"✅ {job['title']} @ {job['company']}")
            time.sleep(random.uniform(0.6, 1.5))

        except Exception as e:
            print(f"❌ Error scraping job: {e}")
            continue

    with open("monster_jobs.json", "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)

    print(f"\n🎉 DONE. {len(jobs)} jobs saved to 'monster_jobs.json'")


def wait_for_you_and_scrape():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        print("🌐 Opening: https://www.monster.com")
        page.goto("https://www.monster.com")
        time.sleep(5)

        print("\n🧍 You now have full control. Navigate wherever you want inside the browser.")
        print("📌 Go to the jobs page, solve CAPTCHA, scroll/load all jobs.")
        input("⚠️ Then press ENTER here to start scraping current page...\n")

        scrape_loaded_jobs(page, max_jobs=50)

        input("🧪 Press ENTER to close the browser...")
        browser.close()

if __name__ == "__main__":
    wait_for_you_and_scrape()
