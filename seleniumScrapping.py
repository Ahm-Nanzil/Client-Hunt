from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import os
import re
import csv


def google_search_extract_emails(search_query="site:instagram.com \"Football Coach\" \"@gmail.com\""):
    # Chrome options with your profile
    options = Options()
    options.binary_location = r"C:\Users\ASUS\Downloads\chrome-win64\chrome-win64\chrome.exe"
    options.add_argument(r"--user-data-dir=C:\Users\ASUS\AppData\Local\Google\Chrome for Testing\User Data")
    options.add_argument("--profile-directory=Profile 3")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    # ChromeDriver service
    service = Service(r"C:\Users\ASUS\Downloads\chromedriver-win64\chromedriver-win64\chromedriver.exe")

    print(f"Starting Google search for: {search_query}")
    print(f"Using Chrome at: {options.binary_location}")
    print(f"Using profile: Profile 3")

    timestamp = int(time.time())
    filename = f"google_gmail_emails_{timestamp}.txt"

    try:
        # Create driver
        driver = webdriver.Chrome(service=service, options=options)

        # Execute script to hide webdriver property
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        all_emails = set()
        url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
        current_page = 1

        while True:
            driver.get(url)
            print(f"Loaded page {current_page} of search results")
            time.sleep(3)

            # CAPTCHA check
            captcha_detected = False
            try:
                # Check for various CAPTCHA indicators
                captcha_selectors = [
                    "iframe[src*='recaptcha']",
                    "[data-callback='recaptchaCallback']",
                    "text*='Select all images'",
                    "text*='I\\'m not a robot'"
                ]

                for selector in captcha_selectors:
                    try:
                        if "text*=" in selector:
                            # For text-based checks, use page source
                            if selector.split("'")[1] in driver.page_source:
                                captcha_detected = True
                                break
                        else:
                            # For CSS selectors
                            driver.find_element(By.CSS_SELECTOR, selector)
                            captcha_detected = True
                            break
                    except NoSuchElementException:
                        continue

                if captcha_detected:
                    print("\nCAPTCHA detected! Please solve it manually in the browser window.")
                    print("The script will wait up to 5 minutes for you to complete it.")
                    try:
                        # Wait for search results to appear
                        WebDriverWait(driver, 300).until(
                            EC.presence_of_element_located((By.ID, "search"))
                        )
                        print("CAPTCHA solved. Continuing...")
                    except TimeoutException:
                        print("Timeout waiting for CAPTCHA to be solved.")
                        break

            except Exception as e:
                print(f"Error checking for CAPTCHA: {e}")

            # Extract emails from page source
            page_text = driver.page_source
            emails = re.findall(r'[a-zA-Z0-9_.+-]+@gmail\.com', page_text)
            found_count = len(emails)
            unique_emails = set(emails)
            print(f"Found {found_count} Gmail addresses ({len(unique_emails)} unique)")

            all_emails.update(unique_emails)

            # Check for next page
            try:
                next_button = driver.find_element(By.ID, "pnnext")
                url = next_button.get_attribute("href")
                if not url.startswith("http"):
                    url = "https://www.google.com" + url
                current_page += 1
                print(f"Moving to next page: {url}")
            except NoSuchElementException:
                print("No more pages found.")
                break

        # Save results to file
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"Search Query: {search_query}\n")
            f.write(f"Extraction Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 50 + "\n\n")
            for email in sorted(all_emails):
                f.write(email + "\n")

        print(f"\nExtraction complete. Found {len(all_emails)} unique Gmail addresses.")
        print(f"Saved to file: {os.path.abspath(filename)}")

        driver.quit()
        return filename

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        try:
            driver.quit()
        except:
            pass
        return None


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


if __name__ == "__main__":
    result = main()
    print(result)