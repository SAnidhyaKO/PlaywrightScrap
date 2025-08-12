import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # Show browser
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://www.naukri.com/")
        print("🌐 Navigated to Naukri.com")

        # Type in the job title
        await page.fill("input.suggestor-input[placeholder='Enter skills / designations / companies']", "Software Engineer")
        print("🔍 Entered job title: Software Engineer")

        # Press ENTER or click the search button
        await page.keyboard.press("Enter")
        print("🔎 Searching for jobs...")

        # Wait for job cards to load
        await page.wait_for_selector(".jobTuple.bgWhite.br4.mb-8")

        # Grab all job cards
        job_cards = await page.query_selector_all(".jobTuple.bgWhite.br4.mb-8")

        print(f"🧾 Found {len(job_cards)} job listings:\n")

        for card in job_cards:
            title = await card.query_selector_eval("a.title.fw500.ellipsis", "el => el.textContent") or "N/A"
            company = await card.query_selector_eval("a.subTitle.ellipsis.fleft", "el => el.textContent") or "N/A"
            location = await card.query_selector_eval(".location span", "el => el.textContent") or "N/A"
            experience = await card.query_selector_eval(".exp span", "el => el.textContent") or "N/A"
            salary = await card.query_selector_eval(".salary span", "el => el.textContent") or "N/A"

            print(f"🔹 Title: {title.strip()}")
            print(f"🏢 Company: {company.strip()}")
            print(f"📍 Location: {location.strip()}")
            print(f"⏳ Experience: {experience.strip()}")
            print(f"💰 Salary: {salary.strip()}")
            print("-" * 50)

        # Keep browser open until manually closed
        print("⏳ Browser is now running. Press CTRL+C in terminal to exit.")
        await asyncio.sleep(999999)

asyncio.run(run())
