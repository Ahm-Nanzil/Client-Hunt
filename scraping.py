from playwright.sync_api import sync_playwright
import time
import os
import re
from pathlib import Path


def google_search_extract_emails(search_query="site:instagram.com \"Football Coach\" \"@gmail.com\""):
    # Use your specific Chrome paths and profile
    chrome_path = r"C:\Users\ASUS\Downloads\chrome-win64\chrome-win64\chrome.exe"
    user_data_dir = r"C:\Users\ASUS\AppData\Local\Google\Chrome for Testing\User Data"
    profile_path = "Profile 3"

    print(f"Starting Google search for: {search_query}")
    print(f"Using Chrome at: {chrome_path}")
    print(f"Using profile: {profile_path} in {user_data_dir}")

    timestamp = int(time.time())
    filename = f"google_gmail_emails_{timestamp}.txt"

    with sync_playwright() as p:
        try:
            browser_type = p.chromium
            browser = browser_type.launch_persistent_context(
                user_data_dir=os.path.join(user_data_dir, profile_path),
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


import csv


def main():
    """Main scraping function to be called from the web interface"""
    try:
        query = 'site:instagram.com "fitness Coach" "@gmail.com"'
        filename = google_search_extract_emails(query)

        if filename:
            # Read scraped emails from file
            scraped_emails = []
            with open(filename, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                # Skip the header lines (first 4 lines)
                for line in lines[4:]:
                    email = line.strip()
                    if email:
                        scraped_emails.append(email)

            # Read existing emails from CSV
            existing_emails = set()
            csv_file = 'clients.csv'

            try:
                with open(csv_file, 'r', newline='', encoding='utf-8') as csvfile:
                    reader = csv.reader(csvfile)
                    next(reader, None)  # Skip header
                    for row in reader:
                        if len(row) > 0:
                            existing_emails.add(row[0].strip().lower())
            except FileNotFoundError:
                # If CSV doesn't exist, create it with header
                with open(csv_file, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Email', 'Customer Name', 'Address', 'Customer Number', 'Sent'])

            # Filter out existing emails and add new ones
            new_emails = []
            for email in scraped_emails:
                if email.lower() not in existing_emails:
                    new_emails.append(email)

            # Add new emails to CSV
            if new_emails:
                with open(csv_file, 'a', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    customer_number = 27077  # Start from next number

                    # Get the last customer number from existing data
                    try:
                        with open(csv_file, 'r', newline='', encoding='utf-8') as read_file:
                            reader = csv.reader(read_file)
                            next(reader, None)  # Skip header
                            last_number = 27076
                            for row in reader:
                                if len(row) > 3 and row[3].isdigit():
                                    last_number = max(last_number, int(row[3]))
                            customer_number = last_number + 1
                    except:
                        pass

                    # Add new emails to CSV
                    for email in new_emails:
                        writer.writerow([
                            email,
                            "No data fulfill your filter criteria",  # Default name
                            "Scraped Lead",  # Default address
                            str(customer_number),
                            "No"  # Not sent yet
                        ])
                        customer_number += 1

            # Delete the temporary scraping file
            try:
                os.remove(filename)
                print(f"Temporary file {filename} deleted successfully")
            except Exception as e:
                print(f"Warning: Could not delete temporary file {filename}: {e}")

            return {
                "status": "success",
                "leads_scraped": len(scraped_emails),
                "new_leads_added": len(new_emails),
                "existing_leads_skipped": len(scraped_emails) - len(new_emails),
                "message": f"Scraping completed! Found {len(scraped_emails)} emails, added {len(new_emails)} new leads to CSV, skipped {len(scraped_emails) - len(new_emails)} existing emails."
            }
        else:
            return {
                "status": "error",
                "leads_scraped": 0,
                "new_leads_added": 0,
                "message": "Scraping failed - no file generated"
            }

    except Exception as e:
        return {
            "status": "error",
            "leads_scraped": 0,
            "new_leads_added": 0,
            "message": f"Scraping error: {str(e)}"
        }