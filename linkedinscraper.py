
# linkedinscraper_auto_scrolling_singlejson.py
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
    "platform engineer",
    "data scientist",
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

def focus_job_list(page):
    """Focus the left result list. Try the known container; fall back to a generic list role."""
    try:
        cont = page.locator("div.scaffold-layout__list").first
        cont.wait_for(state="visible", timeout=15000)
        cont.hover(); cont.click()
        return cont
    except:
        pass
    try:
        lst = page.get_by_role("list").first
        lst.hover(); lst.click()
        return lst
    except Exception as e:
        raise RuntimeError(f"Cannot focus job list: {e}")

def load_job_cards(page, list_container, min_cards=25, max_tries=80):
    """
    Aggressively load virtualized job cards in the left pane.
    Mixes container scroll, window wheel, End key, and jiggles.
    Returns the final count.
    """
    primary_sel = "li.scaffold-layout__list-item div.job-card-container"
    fallback_sel = "li:has(div)"

    def count_cards():
        c = page.locator(primary_sel).count()
        if c == 0:
            c = list_container.locator(fallback_sel).count()
        return c

    # ensure focus
    try:
        list_container.hover()
        list_container.click()
    except:
        pass

    stall = 0
    for _ in range(max_tries):
        curr = count_cards()
        if curr >= min_cards:
            return curr

        # 1) Scroll container towards bottom
        try:
            list_container.evaluate("el => el.scrollBy(0, el.clientHeight - 64)")
        except:
            pass

        # 2) Nudge window—some loaders listen to window scroll
        try:
            page.mouse.wheel(0, 800)
        except:
            pass

        # 3) Big jump
        try:
            page.keyboard.press("End")
        except:
            pass

        time.sleep(0.33)

        new_count = count_cards()
        if new_count > curr:
            stall = 0
            continue

        # Jiggle if stalled: top then bottom
        stall += 1
        if stall % 4 == 0:
            try:
                list_container.evaluate("el => { el.scrollTo(0, 0); }")
                time.sleep(0.18)
                list_container.evaluate("el => { el.scrollTo(0, el.scrollHeight); }")
            except:
                pass

        time.sleep(0.22)

    return count_cards()

# === Core per-keyword scraper (keeps your selectors) ===
def scrape_keyword(page, search_query, start_id=1):
    """
    Scrape all pages for a given keyword using your original selectors.
    Returns (records, next_id_after_this_keyword).
    """
    search_url = f"https://www.linkedin.com/jobs/search/?keywords={search_query.replace(' ', '%20')}"
    print(f"\n🔎 Searching: {search_query} -> {search_url}")
    page.goto(search_url)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except:
        pass
    time.sleep(5)  # your requirement: wait 5s after goto

    all_jobs = []
    page_num = 1
    current_id = start_id  # continuous global id

    while True:
        print(f"\n📄 Processing page {page_num} for '{search_query}'...")

        # ✅ Focus list + force-load ~25 cards
        try:
            scroll_container = focus_job_list(page)
        except Exception as e:
            print(f"❌ Couldn't focus job list container: {e}")
            break

        loaded = load_job_cards(page, scroll_container, min_cards=25, max_tries=80)
        print(f"🧲 Loaded {loaded} cards in the list")

        # ✅ Use your known selector; fallback if needed
        job_cards = page.query_selector_all("li.scaffold-layout__list-item div.job-card-container")
        if not job_cards:
            job_cards = scroll_container.locator("li:has(div)").all()

        if not job_cards:
            print("❌ No job cards found on page.")
            break

        print(f"📦 Found {len(job_cards)} job cards")

        # Open each card to read the right-side detail panel (same selectors)
        for _i, card in enumerate(job_cards):
            try:
                print(f"➡️ Scraping job id {current_id}...")
                card.scroll_into_view_if_needed()
                card.click()
                time.sleep(2)

                # ⬇️ Same detail selectors as your previous logic
                title = page.locator("div.t-24.job-details-jobs-unified-top-card__job-title").inner_text(timeout=10000)
                company = page.locator("div.job-details-jobs-unified-top-card__company-name").inner_text(timeout=10000)
                location_block = page.locator("div.job-details-jobs-unified-top-card__primary-description-container > div").inner_text(timeout=10000)
                job_description = page.locator("div#job-details").inner_text(timeout=10000)

                all_jobs.append({
                    "id": current_id,  # 👈 continuous global id
                    "keyword": search_query,
                    "title": title.strip(),
                    "company": company.strip(),
                    "location_and_other_details": location_block.strip(),
                    "job_link": page.url,
                    "job_description": job_description.strip()
                })
                current_id += 1
            except Exception as e:
                print(f"⚠️ Error scraping id {current_id}: {e}")

        # Pagination: identical behavior with simple fallback timing
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

    return all_jobs, current_id  # return next starting id

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

        # 🧠 Use DEFAULT_KEYWORDS and produce ONE master JSON with continuous IDs
        keywords = DEFAULT_KEYWORDS
        print(f"\n🚀 Running for {len(keywords)} keyword(s): {keywords}")

        master = []
        current_id = 1  # 👈 global continuous id starts here

        for kw in keywords:
            print("\n" + "="*80)
            print(f"🧠 KEYWORD: {kw}")
            print("="*80)
            try:
                records, current_id = scrape_keyword(page, kw, start_id=current_id)
                master.extend(records)
                print(f"✅ Collected {len(records)} jobs for '{kw}'. Next id will be {current_id}.")
            except KeyboardInterrupt:
                print("⛔ Interrupted by user.")
                break
            except Exception as e:
                print(f"💥 Failed keyword '{kw}': {e}")

            human_sleep(1.5, 3.0)

        # Save the single master file
        master_file = out_root / "linkedin_jobs_MASTER.json"
        with master_file.open("w", encoding="utf-8") as f:
            json.dump(master, f, indent=2, ensure_ascii=False)

        print(f"\n🏁 TOTAL: {len(master)} jobs across {len(keywords)} keyword(s).")
        print(f"🗂  Output folder: {out_root.resolve()}")
        input("🧹 Press Enter to close browser...")
        browser.close()

# ==== RUN ====
if __name__ == "__main__":
    print("LinkedIn Batch Scraper 🔧 (Single JSON + Continuous IDs)")
    email = input("📧 Enter your LinkedIn email (or '.' to skip login): ").strip()
    password = input("🔒 Enter your LinkedIn password (or '.' to skip): ").strip()
    linkedin_login_and_scrape_batch(email, password)
