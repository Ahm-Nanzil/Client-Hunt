from playwright.sync_api import sync_playwright
import time
import os
import re
from pathlib import Path


def get_chrome_user_data_dir():
    home = Path.home()
    if os.name == "nt":
        return os.path.join(home, "AppData", "Local", "Google", "Chrome", "User Data")
    elif os.name == "posix":
        if os.path.exists(os.path.join(home, "Library", "Application Support", "Google", "Chrome")):
            return os.path.join(home, "Library", "Application Support", "Google", "Chrome")
        else:
            return os.path.join(home, ".config", "google-chrome")
    return None


def google_search_extract_emails(search_query="site:instagram.com \"fitness Coach\" \"@gmail.com\""):
    chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
    user_data_dir = get_chrome_user_data_dir()
    profile_path = os.path.join(user_data_dir, "Default")

    print(f"Starting Google search for: {search_query}")
    print(f"Using Chrome at: {chrome_path}")
    print(f"Using profile at: {profile_path}")

    timestamp = int(time.time())
    filename = f"google_gmail_emails_{timestamp}.txt"

    with sync_playwright() as p:
        try:
            browser_type = p.chromium
            browser = browser_type.launch_persistent_context(
                user_data_dir=profile_path,
                executable_path=chrome_path,
                headless=False,
                args=["--disable-blink-features=AutomationControlled"]
            )

            page = browser.new_page()

            stealth_js = """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => false,
                });
            """
            page.add_init_script(stealth_js)

            all_emails = set()
            url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
            current_page = 1

            while True:
                page.goto(url, wait_until="networkidle", timeout=60000)
                print(f"Loaded page {current_page} of search results")
                time.sleep(3)

                # CAPTCHA check
                if page.locator("iframe[src*='recaptcha']").count() > 0 or \
                   page.locator("text=Select all images").count() > 0 or \
                   page.locator("text=I'm not a robot").count() > 0:

                    print("\nCAPTCHA detected! Please solve it manually in the browser window.")
                    print("The script will wait up to 5 minutes for you to complete it.")
                    try:
                        page.wait_for_selector("div#search", timeout=300000)
                        print("CAPTCHA solved. Continuing...")
                    except Exception:
                        print("Timeout waiting for CAPTCHA to be solved.")
                        break

                # Extract emails
                text_content = page.evaluate("() => document.body.innerText")
                emails = re.findall(r'[a-zA-Z0-9_.+-]+@gmail\.com', text_content)
                found_count = len(emails)
                unique_emails = set(emails)
                print(f"Found {found_count} Gmail addresses ({len(unique_emails)} unique)")

                all_emails.update(unique_emails)

                # Check for next page
                next_button = page.locator("a#pnnext")
                if next_button.count() > 0:
                    url = next_button.get_attribute("href")
                    if not url.startswith("http"):
                        url = "https://www.google.com" + url
                    current_page += 1
                    print(f"Moving to next page: {url}")
                else:
                    print("No more pages found.")
                    break

            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"Search Query: {search_query}\n")
                f.write(f"Extraction Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 50 + "\n\n")
                for email in sorted(all_emails):
                    f.write(email + "\n")

            print(f"\nExtraction complete. Found {len(all_emails)} unique Gmail addresses.")
            print(f"Saved to file: {os.path.abspath(filename)}")

            browser.close()
            return filename

        except Exception as e:
            print(f"Error occurred: {str(e)}")
            return None


if __name__ == "__main__":
    query = 'site:instagram.com "fitness Coach" "@gmail.com"'
    google_search_extract_emails(query)
