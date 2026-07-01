import os
import time
import random
import traceback
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
# COURSE_CODE = "ot608"
# COURSE_URL = "https://www.biblicaltraining.org/learn/institute/ot608-deuteronomy"
# OUTPUT_DIR = "transcripts_deuteronomy"

COURSE_CODE = "1-and-2-kings-john-oswalt-ot630"
COURSE_URL = "https://www.biblicaltraining.org/learn/institute/1-and-2-kings-john-oswalt-ot630"
OUTPUT_DIR = "transcripts_kings"




if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)


def harvest_transcripts():
    try:
        with sync_playwright() as p:
            print("--- Launching Stealth Surgical Harvester ---")

            # Using a persistent context to bypass bot-detection and save logins
            context = p.chromium.launch_persistent_context(
                'automation_session',
                headless=False,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                args=["--disable-blink-features=AutomationControlled"],
                ignore_default_args=["--enable-automation"]
            )

            page = context.new_page()
            print(f"Navigating to {COURSE_URL}...")
            # page.goto(COURSE_URL)
            page.goto(COURSE_URL, timeout=60000, wait_until="domcontentloaded")

            print("\n[ACTION REQUIRED]")
            print("1. Log in and bypass any Cloudflare 'Verify you are human' boxes.")
            print("2. Ensure you are on the page showing the lesson links.")
            input("3. Once the lesson list is visible, press ENTER here in PyCharm...")

            # --- STEP 1: LINK DISCOVERY RETRY LOOP ---
            # --- STEP 1: LINK DISCOVERY RETRY LOOP ---
            links = []
            for attempt in range(3):
                print(f"Searching for links (Attempt {attempt + 1}/3)...")
                # Wait for the basic structure to be there, not for every background request to finish
                page.wait_for_load_state("domcontentloaded")
                time.sleep(2)  # Give it a tiny bit of extra breathing room

                # Broaden search to find any link containing the course code
                elements = page.locator(f"a[href*='{COURSE_CODE}']").all()
                found_urls = [el.get_attribute("href") for el in elements if el.get_attribute("href")]

                for l in found_urls:
                    full_url = l if l.startswith("http") else f"https://www.biblicaltraining.org{l}"
                    # Only grab actual lesson sub-pages, skip the main course landing page
                    if f"{COURSE_CODE}" in full_url and full_url != COURSE_URL and full_url not in links:
                        links.append(full_url)

                if len(links) > 0:
                    break
                print("No links found yet. Please ensure the lesson list is on screen.")
                time.sleep(3)

            if not links:
                print("CRITICAL: Found 0 links. Check if the URL changed or if you are logged out.")
                context.close()
                return

            print(f"Success! Found {len(links)} lessons to harvest.")

            # --- STEP 2: THE HARVEST LOOP ---
            for i, link in enumerate(links):
                try:
                    # Random "Human" delay between pages to avoid Cloudflare triggers
                    delay = random.uniform(5.0, 8.5)
                    print(f"\n[{i + 1}/{len(links)}] Pausing {delay:.1f}s then visiting: {link}")
                    time.sleep(delay)

                    page.goto(link, wait_until="domcontentloaded")
                    time.sleep(random.uniform(2.5, 4.5))

                    # Attempt to click Transcription
                    try:
                        tab = page.locator('[data-tab-hash="class--transcription"]').first
                        if tab.is_visible():
                            tab.click()
                            time.sleep(random.uniform(2.0, 3.5))
                    except:
                        # If clicking fails, we continue anyway to try the wide net grab
                        pass

                    # --- STEP 3: CONTENT EXTRACTION ---
                    content = ""
                    # Priority selectors for the transcript
                    selectors = [".prose", "[data-tab-content='class--transcription']", ".lecture-content"]
                    for selector in selectors:
                        target = page.locator(selector).first
                        if target.is_visible():
                            text = target.inner_text().strip()
                            if len(text) > 300:
                                content = text
                                break

                    # Fallback to the largest text block on the page
                    if not content:
                        divs = page.locator("div").all()
                        content_list = []
                        for d in divs:
                            try:
                                content_list.append(d.inner_text())
                            except:
                                continue

                        valid_blocks = [txt for txt in content_list if len(txt) > 500]
                        content = max(valid_blocks, key=len) if valid_blocks else ""

                    # --- STEP 4: SURGICAL NOISE CANCELING ---
                    if content:
                        # 1. Chop off footer boilerplate
                        junk_markers = ["Class Resources", "About BiblicalTraining.org", "Recommended Books"]
                        for marker in junk_markers:
                            if marker in content:
                                content = content.split(marker)[0].strip()

                        # 2. Strip specific UI words
                        content = content.replace("Scroll Down", "").strip()

                        # 3. Deduplicate double titles at the top
                        lines = content.split('\n')
                        if len(lines) > 1 and lines[0].strip() == lines[1].strip():
                            content = '\n'.join(lines[1:]).strip()

                        # --- STEP 5: SAVE ---
                        if len(content) > 150:
                            # Naming logic: 00 for landing, 01+ for lectures
                            filename = "Lesson_00_Overview.txt" if i == 0 else f"Lesson_{i:02d}.txt"
                            file_path = os.path.join(OUTPUT_DIR, filename)

                            with open(file_path, "w", encoding="utf-8") as f:
                                f.write(content)
                            print(f"   Saved: {filename} ({len(content)} characters)")
                        else:
                            print(f"   Warning: Content too short for {link}")
                    else:
                        print(f"   Warning: No text block found for {link}")

                except Exception as e:
                    print(f"   Error on {link}: {e}")

            print("\n--- Mission Accomplished! ---")
            context.close()

    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    harvest_transcripts()