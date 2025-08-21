import json, re, time, random, sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, TimeoutError

# --------- CONFIG ---------
KEYWORDS = [
    "software engineer", "python developer", "backend engineer",
    "full stack developer", "react developer", "node.js developer",
    "java developer", "golang developer", "django developer",
    "data engineer", "machine learning engineer", "devops engineer",
    "cloud engineer", "android developer", "ios developer",
    "qa automation engineer",
]
LOCATION = "Remote"
OUTPUT_FILE = "jobs_indeed.json"      # single JSON array
STATE_FILE  = "jobs_indeed_state.json" # resume state (keyword index, page_num, next_id)
BROWSER_ENGINE = "chromium"           # "chromium" | "firefox" | "webkit"
HEADFUL = True                        # headful so you can solve human verification
BASE_DELAY = 1.6
DETAIL_DELAY = 0.8
STOP_AFTER_EMPTY_PAGES = 2            # stop a keyword after X consecutive empty pages
MAX_PER_KEYWORD = None                # None = all pages; or cap for testing

BASE_URL = "https://www.indeed.com/jobs"
JOB_DETAIL_URL = "https://www.indeed.com/m/basecamp/viewjob?viewtype=embedded&jk={jk}"

# regex fallbacks
JOB_CARDS_RE = re.compile(
    r'window\.mosaic\.providerData\["mosaic-provider-jobcards"\]\s*=\s*(\{.+?\});',
    re.DOTALL,
)
DETAIL_RE = re.compile(r"_initialData=(\{.+?\});", re.DOTALL)

# ---------- STORAGE / RESUME ----------

def load_json_array(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "[]")
        return data if isinstance(data, list) else []
    except Exception:
        return []

def save_json_array(path: Path, arr: List[Dict[str, Any]]) -> None:
    path.write_text(json.dumps(arr, ensure_ascii=False, indent=2), encoding="utf-8")

def load_state() -> Dict[str, Any]:
    p = Path(STATE_FILE)
    if not p.exists():
        return {"kw_idx": 0, "page_num": 0, "next_id": 1}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"kw_idx": 0, "page_num": 0, "next_id": 1}

def save_state(state: Dict[str, Any]) -> None:
    Path(STATE_FILE).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

def next_id_from_output(out_path: Path) -> int:
    data = load_json_array(out_path)
    if not data:
        return 1
    return max((rec.get("id", 0) for rec in data), default=0) + 1

def ensure_state_consistency(out_path: Path, state: Dict[str, Any]) -> Dict[str, Any]:
    # If output already has IDs, keep state.next_id in sync
    current_next = next_id_from_output(out_path)
    if current_next > state.get("next_id", 1):
        state["next_id"] = current_next
    return state

def dedupe(existing: List[Dict[str, Any]], new_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = {(it.get("source"), it.get("jobkey")) for it in existing if it.get("jobkey")}
    out: List[Dict[str, Any]] = []
    for it in new_items:
        key = (it.get("source"), it.get("jobkey"))
        if it.get("jobkey") and key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out

# ---------- PARSERS ----------

@dataclass
class JobItem:
    id: int
    source: str
    keyword: str
    jobkey: str
    title: str
    company: str
    location: str
    date_posted: str
    summary: str
    salary_text: str
    rating: float
    listing_url: str
    apply_url: str
    description_html: str

def build_search_url(keyword: str, location: str, start: int = 0) -> str:
    return f"{BASE_URL}?q={quote(keyword)}&l={quote(location)}&start={start}"

def get_provider_json_from_page(page: Page) -> Optional[Dict[str, Any]]:
    try:
        data = page.evaluate("""() => {
            try { return window.mosaic?.providerData?.["mosaic-provider-jobcards"]; }
            catch (e) { return null; }
        }""")
        return data if isinstance(data, dict) else None
    except Exception:
        return None

def parse_search_results_html(html: str) -> List[Dict[str, Any]]:
    m = JOB_CARDS_RE.search(html)
    if not m:
        return []
    try:
        payload = json.loads(m.group(1))
        results = (
            payload.get("metaData", {})
            .get("mosaicProviderJobCardsModel", {})
            .get("results", [])
        )
        return results or []
    except Exception:
        return []

def extract_card_fields(card: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "jobkey": card.get("jobkey") or card.get("jobKey") or "",
        "title": card.get("displayTitle", "") or card.get("title", ""),
        "company": card.get("company", "") or card.get("companyName", ""),
        "location": card.get("formattedLocation", "") or card.get("location", ""),
        "date_posted": card.get("formattedRelativeTime", "") or card.get("listedDate", ""),
        "summary": (card.get("descriptionSnippet") or "").replace("\n", " ").strip(),
        "salary_text": (
            card.get("salarySnippet", {}).get("text", "")
            if isinstance(card.get("salarySnippet"), dict) else ""
        ),
        "rating": float(card.get("companyReviewRating", 0) or 0.0),
        "listing_url": card.get("jobURL") or (f"https://www.indeed.com/viewjob?jk={card.get('jobkey','')}"),
        "apply_url": card.get("jobURL") or "",
    }

def parse_detail_html(html: str) -> Dict[str, Any]:
    m = DETAIL_RE.search(html)
    if not m:
        return {}
    try:
        data = json.loads(m.group(1))
        return data.get("jobInfoWrapperModel", {}).get("jobInfoModel", {}) or {}
    except Exception:
        return {}

# ---------- HUMAN-GATE HANDLING (manual) ----------

GATE_HINTS = [
    "verify you're human", "verify you are human", "are you a human",
    "unusual traffic", "bot detection", "complete the challenge",
    "press and hold", "captcha"
]

def is_human_gate(page: Page) -> bool:
    try:
        html = page.content().lower()
    except Exception:
        return False
    return any(h in html for h in GATE_HINTS)

def pause_for_human(page: Page) -> None:
    # Bring the page to front, give you time to solve, then wait until gate disappears
    print("\n🔒 Human verification detected.")
    print("➡️  Please solve the verification in the browser window.")
    input("👉 Press ENTER here after you finish the verification...")
    # small wait loop to ensure page is past the gate
    for _ in range(30):
        time.sleep(1.0)
        if not is_human_gate(page):
            print("✅ Verification cleared. Resuming…")
            return
    print("⚠️ Still seeing verification page. You may need to try again.")

# ---------- SCRAPING ----------

def get_results_from_page(page: Page) -> List[Dict[str, Any]]:
    provider = get_provider_json_from_page(page)
    if provider:
        results = (
            provider.get("metaData", {})
            .get("mosaicProviderJobCardsModel", {})
            .get("results", [])
        )
        return results or []
    # DOM fallback (defensive)
    items: List[Dict[str, Any]] = []
    cards = page.query_selector_all("div.job_seen_beacon, div.slider_item, li div.jobCard_mainContent")
    for c in cards:
        try:
            title_el = (c.query_selector("h2 a") or c.query_selector("a[data-jk]"))
            jk = (title_el.get_attribute("data-jk") if title_el else None) or (c.get_attribute("data-jk") or "")
            t = (title_el.inner_text().strip() if title_el else "").strip()
            company_el = c.query_selector(".companyName, span[data-company-name]") or c.query_selector("span.companyName")
            company = company_el.inner_text().strip() if company_el else ""
            loc_el = c.query_selector(".companyLocation") or c.query_selector("div[data-testid='text-location']")
            loc = loc_el.inner_text().strip() if loc_el else ""
            date_el = c.query_selector("span.date, span[data-testid='myJobsStateDate']")
            date_posted = date_el.inner_text().strip() if date_el else ""
            sum_el = c.query_selector("div.job-snippet, li.job-snippet, .jobCardShelfContainer")
            summary = sum_el.inner_text().replace("\n", " ").strip() if sum_el else ""
            salary_el = c.query_selector("div.metadata.salary-snippet-container, div.salary-snippet-container")
            salary = salary_el.inner_text().strip() if salary_el else ""
            url = f"https://www.indeed.com/viewjob?jk={jk}" if jk else ""
            items.append({
                "jobkey": jk or "",
                "displayTitle": t,
                "company": company,
                "formattedLocation": loc,
                "formattedRelativeTime": date_posted,
                "descriptionSnippet": summary,
                "salarySnippet": {"text": salary} if salary else {},
                "jobURL": url
            })
        except Exception:
            continue
    return items

def scrape_keyword(
    browser: Browser,
    keyword: str,
    location: str,
    start_id: int,
    page_num_start: int = 0,
) -> Tuple[List[Dict[str, Any]], int, int]:
    context: BrowserContext = browser.new_context(
        user_agent=random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
        ]),
        viewport={"width": 1366, "height": 900}
    )
    page = context.new_page()
    collected: List[Dict[str, Any]] = []
    cur_id = start_id
    empty_pages = 0
    fetched_for_kw = 0
    page_num = page_num_start

    try:
        while True:
            start = page_num * 10
            url = build_search_url(keyword, location, start)
            print(f"🔎 {keyword} | Page {page_num+1} | {url}")
            try:
                page.goto(url, timeout=60000, wait_until="domcontentloaded")
            except TimeoutError:
                time.sleep(2.0)
                page_num += 1
                continue

            if is_human_gate(page):
                pause_for_human(page)

            try:
                page.wait_for_load_state("networkidle", timeout=45000)
            except TimeoutError:
                pass

            # small human-like scrolls
            for _ in range(3):
                page.mouse.wheel(0, random.randint(500, 1200))
                time.sleep(0.4 + random.random())

            results = get_results_from_page(page)
            if not results:
                empty_pages += 1
                if empty_pages >= STOP_AFTER_EMPTY_PAGES:
                    break
                time.sleep(BASE_DELAY + random.uniform(1.0, 2.0))
                page_num += 1
                continue

            empty_pages = 0
            for card in results:
                fields = extract_card_fields(card)
                jk = fields["jobkey"]
                description_html = ""
                salary_from_detail = ""
                rating_from_detail = None

                if jk:
                    durl = JOB_DETAIL_URL.format(jk=jk)
                    try:
                        page.goto(durl, timeout=60000, wait_until="domcontentloaded")
                        if is_human_gate(page):
                            pause_for_human(page)
                        try:
                            page.wait_for_load_state("networkidle", timeout=45000)
                        except TimeoutError:
                            pass

                        dhtml = page.content()
                        d = parse_detail_html(dhtml)

                        desc = d.get("jobDescriptionSectionModel", {}).get("descriptionHtml")
                        if isinstance(desc, str):
                            description_html = desc
                        comp = d.get("compensationInfoModel", {}).get("extractedCompensation", {})
                        if isinstance(comp, dict):
                            lo, hi, typ = comp.get("min"), comp.get("max"), comp.get("type")
                            if lo and hi:
                                salary_from_detail = f"{lo}-{hi} ({typ})"
                            elif lo:
                                salary_from_detail = f"{lo} ({typ})"
                            elif hi:
                                salary_from_detail = f"{hi} ({typ})"
                        try:
                            rating_from_detail = float(d.get("companyReviewModel", {}).get("rating", 0) or 0.0)
                        except Exception:
                            rating_from_detail = None
                        time.sleep(DETAIL_DELAY + random.uniform(0.2, 0.8))
                    except Exception:
                        # continue with listing-only fields
                        pass

                item = JobItem(
                    id=cur_id,
                    source="indeed",
                    keyword=keyword,
                    jobkey=jk,
                    title=fields["title"],
                    company=fields["company"],
                    location=fields["location"],
                    date_posted=fields["date_posted"],
                    summary=fields["summary"],
                    salary_text=salary_from_detail or fields["salary_text"],
                    rating=(rating_from_detail if rating_from_detail is not None else fields["rating"]),
                    listing_url=fields["listing_url"],
                    apply_url=fields["apply_url"] or fields["listing_url"],
                    description_html=description_html,
                )
                collected.append(asdict(item))
                cur_id += 1
                fetched_for_kw += 1

                if MAX_PER_KEYWORD and fetched_for_kw >= MAX_PER_KEYWORD:
                    break

                time.sleep(BASE_DELAY + random.uniform(0.2, 0.9))

            if MAX_PER_KEYWORD and fetched_for_kw >= MAX_PER_KEYWORD:
                break

            # next page
            page_num += 1
            time.sleep(BASE_DELAY + random.uniform(0.8, 1.8))

    finally:
        page.close()
        context.close()

    return collected, cur_id, page_num

# ---------- ORCHESTRATION ----------

def main():
    out_path = Path(OUTPUT_FILE)
    existing = load_json_array(out_path)
    state = ensure_state_consistency(out_path, load_state())

    print(f"Resuming at: kw_idx={state['kw_idx']} page_num={state['page_num']} next_id={state['next_id']}")
    print(f"Existing records: {len(existing)}")

    with sync_playwright() as p:
        if BROWSER_ENGINE == "chromium":
            browser = p.chromium.launch(headless=not HEADFUL)
        elif BROWSER_ENGINE == "webkit":
            browser = p.webkit.launch(headless=not HEADFUL)
        else:
            browser = p.firefox.launch(headless=not HEADFUL)

        try:
            for kw_idx in range(state["kw_idx"], len(KEYWORDS)):
                kw = KEYWORDS[kw_idx]
                page_num_start = state["page_num"] if kw_idx == state["kw_idx"] else 0

                print(f"\n==== [{kw_idx+1}/{len(KEYWORDS)}] Keyword: {kw} ====")
                new_items, next_id, last_page_num = scrape_keyword(
                    browser=browser,
                    keyword=kw,
                    location=LOCATION,
                    start_id=state["next_id"],
                    page_num_start=page_num_start,
                )

                # merge + dedupe + save
                merged = existing + dedupe(existing, new_items)
                save_json_array(out_path, merged)
                existing = merged

                # advance state to next keyword
                state["kw_idx"] = kw_idx + 1
                state["page_num"] = 0
                state["next_id"]  = next_id
                save_state(state)
                print(f"✅ {kw}: +{len(new_items)} (total: {len(existing)})  next_id={state['next_id']}")

                time.sleep(BASE_DELAY + random.uniform(1.0, 2.0))

        finally:
            browser.close()

    print(f"\n✅ Done (or checkpoint saved). JSON: {out_path.resolve()}")
    print(f"State stored in: {Path(STATE_FILE).resolve()} (safe to delete when fully complete)")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted. State saved. You can rerun to resume.")
