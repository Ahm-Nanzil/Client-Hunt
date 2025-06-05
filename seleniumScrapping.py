from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import re
import os
import csv
import pandas as pd
from pathlib import Path
import threading
import pygame
import sys

# Initialize pygame mixer for audio
pygame.mixer.init()


def play_notification_sound(sound_file="notification.wav", repeat=3):
    """Play notification sound when CAPTCHA is detected"""
    try:
        if os.path.exists(sound_file):
            sound = pygame.mixer.Sound(sound_file)
            for _ in range(repeat):
                sound.play()
                time.sleep(1)
        else:
            # If no custom sound file, use system beep
            for _ in range(repeat):
                print('\a')  # System beep
                time.sleep(0.5)
    except Exception as e:
        print(f"Error playing notification sound: {e}")
        # Fallback to system beep
        for _ in range(repeat):
            print('\a')
            time.sleep(0.5)


def send_notification_to_frontend(message="CAPTCHA Detected!"):
    """Send notification to frontend (you can expand this for WebSocket)"""
    print(f"🔔 NOTIFICATION: {message}")
    # Here you could implement WebSocket or Server-Sent Events
    # to notify the frontend in real-time


def detect_captcha_advanced(driver):
    """Enhanced CAPTCHA detection with multiple patterns"""
    captcha_indicators = [
        # reCAPTCHA patterns
        "iframe[src*='recaptcha']",
        "div[class*='recaptcha']",
        ".g-recaptcha",

        # Common CAPTCHA text patterns
        "//*[contains(text(),'Select all images')]",
        "//*[contains(text(),\"I'm not a robot\")]",
        "//*[contains(text(),'Verify you are human')]",
        "//*[contains(text(),'Complete the security check')]",
        "//*[contains(text(),'Please confirm you are human')]",

        # hCaptcha patterns
        "iframe[src*='hcaptcha']",
        "div[class*='hcaptcha']",

        # Cloudflare patterns
        "//*[contains(text(),'Checking your browser')]",
        "//*[contains(text(),'Please wait while we verify')]",
        "div[class*='cf-browser-verification']",

        # General CAPTCHA patterns
        "input[name*='captcha']",
        "img[src*='captcha']",
        "//*[contains(text(),'security code')]",
        "//*[contains(text(),'verification code')]"
    ]

    for indicator in captcha_indicators:
        try:
            if indicator.startswith("//"):
                # XPath selector
                elements = driver.find_elements(By.XPATH, indicator)
            else:
                # CSS selector
                elements = driver.find_elements(By.CSS_SELECTOR, indicator)

            if elements:
                return True, indicator
        except Exception:
            continue

    return False, None


def wait_for_captcha_resolution(driver, max_wait_time=600):  # 10 minutes max
    """Wait for CAPTCHA to be solved with enhanced monitoring"""
    print(f"\n{'=' * 50}")
    print("🚨 CAPTCHA DETECTED! 🚨")
    print("Please solve the CAPTCHA manually in the browser window.")
    print(f"The script will wait up to {max_wait_time // 60} minutes for you to complete it.")
    print("💡 Tip: Look for checkboxes, image selections, or verification prompts.")
    print(f"{'=' * 50}\n")

    # Play notification sound in a separate thread
    sound_thread = threading.Thread(target=play_notification_sound)
    sound_thread.daemon = True
    sound_thread.start()

    # Send notification to frontend
    send_notification_to_frontend("CAPTCHA detected! Please solve it manually.")

    start_wait = time.time()
    check_interval = 3  # Check every 3 seconds

    while time.time() - start_wait < max_wait_time:
        try:
            # Check multiple indicators that CAPTCHA is solved
            solved_indicators = [
                # Google search results are back
                (By.ID, "search"),
                (By.ID, "searchform"),
                (By.CSS_SELECTOR, "#search .g"),  # Individual search results

                # General page content indicators
                (By.TAG_NAME, "body"),  # Basic page load
            ]

            for by_method, selector in solved_indicators:
                try:
                    element = driver.find_element(by_method, selector)
                    if element and element.is_displayed():
                        # Double-check that CAPTCHA is really gone
                        captcha_present, _ = detect_captcha_advanced(driver)
                        if not captcha_present:
                            print("✅ CAPTCHA solved! Continuing scraping...")
                            send_notification_to_frontend("CAPTCHA solved! Scraping resumed.")
                            return True
                except NoSuchElementException:
                    continue

            # Show progress
            elapsed = int(time.time() - start_wait)
            remaining = max_wait_time - elapsed
            print(f"⏳ Waiting for CAPTCHA solution... ({elapsed}s elapsed, {remaining}s remaining)")

        except Exception as e:
            print(f"Error checking CAPTCHA status: {e}")

        time.sleep(check_interval)

    print("⏰ Timeout waiting for CAPTCHA to be solved.")
    send_notification_to_frontend("CAPTCHA timeout! Scraping stopped.")
    return False


def load_existing_emails(csv_file="clients.csv"):
    """Load existing emails from clients.csv"""
    existing_emails = set()
    if os.path.exists(csv_file):
        try:
            df = pd.read_csv(csv_file)
            if 'email' in df.columns:
                existing_emails = set(df['email'].dropna().str.lower())
            print(f"Loaded {len(existing_emails)} existing emails from {csv_file}")
        except Exception as e:
            print(f"Error reading {csv_file}: {e}")
    else:
        print(f"{csv_file} not found. Will create new file.")
    return existing_emails


def save_new_emails_to_csv(new_emails, csv_file="clients.csv"):
    """Save new emails to clients.csv"""
    if not new_emails:
        print("No new emails to save.")
        return

    # Check if file exists
    file_exists = os.path.exists(csv_file)

    # Prepare data
    new_data = [{'email': email} for email in new_emails]

    if file_exists:
        # Append to existing file
        existing_df = pd.read_csv(csv_file)
        new_df = pd.DataFrame(new_data)
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        combined_df.to_csv(csv_file, index=False)
    else:
        # Create new file
        new_df = pd.DataFrame(new_data)
        new_df.to_csv(csv_file, index=False)

    print(f"Added {len(new_emails)} new emails to {csv_file}")


def search_and_save(search_query, existing_emails=None):
    """Main scraping function with enhanced CAPTCHA handling"""
    if existing_emails is None:
        existing_emails = set()

    # Chrome options with your profile
    options = Options()
    options.binary_location = r"C:\Users\ASUS\Downloads\chrome-win64\chrome-win64\chrome.exe"
    options.add_argument(r"--user-data-dir=C:\Users\ASUS\AppData\Local\Google\Chrome for Testing\User Data")
    options.add_argument(r"--profile-directory=Profile 3")
    # Optional: Disable automation flags if needed
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    # ChromeDriver service
    service = Service(r"C:\Users\ASUS\Downloads\chromedriver-win64\chromedriver-win64\chromedriver.exe")

    # Create driver
    driver = webdriver.Chrome(service=service, options=options)

    try:
        all_emails = set()
        base_url = "https://www.google.com/search?q="
        query_url = base_url + search_query.replace(' ', '+')
        driver.get(query_url)
        print(f"Starting Google search for: {search_query}")
        current_page = 1

        while True:
            print(f"Loaded page {current_page} of search results")
            time.sleep(3)  # Wait for page to load

            # Enhanced CAPTCHA detection
            captcha_present, captcha_type = detect_captcha_advanced(driver)

            if captcha_present:
                print(f"\n🔴 CAPTCHA detected (Type: {captcha_type})")

                # Wait for CAPTCHA to be solved
                if not wait_for_captcha_resolution(driver):
                    print("Exiting due to CAPTCHA timeout.")
                    break

                # Continue with scraping after CAPTCHA is solved
                time.sleep(2)  # Brief pause after resolution

            # Extract page text
            try:
                page_text = driver.find_element(By.TAG_NAME, "body").text
                emails = re.findall(r'[a-zA-Z0-9_.+-]+@gmail\.com', page_text)
                found_count = len(emails)
                unique_emails = set(email.lower() for email in emails)

                # Filter out existing emails
                new_emails = unique_emails - existing_emails

                print(f"Found {found_count} Gmail addresses ({len(unique_emails)} unique) on this page")
                print(f"New emails (not in clients.csv): {len(new_emails)}")

                all_emails.update(new_emails)
            except Exception as e:
                print(f"Error extracting emails: {e}")
                continue

            # Find next page button
            try:
                next_button = driver.find_element(By.ID, "pnnext")
                if next_button:
                    next_button_url = next_button.get_attribute("href")
                    if not next_button_url.startswith("http"):
                        next_button_url = "https://www.google.com" + next_button_url
                    current_page += 1
                    print(f"Moving to next page: {next_button_url}")
                    driver.get(next_button_url)
                    time.sleep(3)
                else:
                    print("No more pages found.")
                    break
            except NoSuchElementException:
                print("No next page button found. Ending search.")
                break

        # Save to temporary file first
        timestamp = int(time.time())
        temp_filename = f"temp_gmail_emails_{timestamp}.txt"
        with open(temp_filename, "w", encoding="utf-8") as f:
            f.write(f"Search Query: {search_query}\n")
            f.write(f"Extraction Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 50 + "\n\n")
            for email in sorted(all_emails):
                f.write(email + "\n")

        print(f"\nExtraction complete. Found {len(all_emails)} new Gmail addresses.")
        print(f"Temporary file created: {os.path.abspath(temp_filename)}")

        return all_emails, temp_filename

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return set(), None

    finally:
        driver.quit()


# Rest of your existing functions remain the same...
def process_single_query(query):
    """Process a single search query"""
    print(f"Processing single query: {query}")

    # Load existing emails
    existing_emails = load_existing_emails()

    # Scrape new emails
    new_emails, temp_file = search_and_save(query, existing_emails)

    if new_emails:
        # Save new emails to clients.csv
        save_new_emails_to_csv(new_emails)

        # Delete temporary file
        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)
            print(f"Deleted temporary file: {temp_file}")

    return len(new_emails)


def process_multiple_queries(queries):
    """Process multiple search queries"""
    print(f"Processing {len(queries)} queries...")

    total_new_emails = 0
    all_new_emails = set()

    # Load existing emails once
    existing_emails = load_existing_emails()

    for i, query in enumerate(queries, 1):
        print(f"\n--- Processing Query {i}/{len(queries)} ---")
        print(f"Query: {query}")

        # Scrape new emails
        new_emails, temp_file = search_and_save(query, existing_emails | all_new_emails)

        if new_emails:
            all_new_emails.update(new_emails)
            total_new_emails += len(new_emails)

            # Delete temporary file
            if temp_file and os.path.exists(temp_file):
                os.remove(temp_file)
                print(f"Deleted temporary file: {temp_file}")

        # Add delay between queries to avoid being blocked
        if i < len(queries):
            print("Waiting 10 seconds before next query...")
            time.sleep(10)

    # Save all new emails to clients.csv at once
    if all_new_emails:
        save_new_emails_to_csv(all_new_emails)

    print(f"\n=== SUMMARY ===")
    print(f"Total queries processed: {len(queries)}")
    print(f"Total new emails found: {total_new_emails}")

    return total_new_emails


def scrape_emails(query_type, queries):
    """Main function to be called from Flask"""
    try:
        if query_type == "single":
            if isinstance(queries, list) and len(queries) > 0:
                return process_single_query(queries[0])
            else:
                return process_single_query(queries)
        elif query_type == "multiple":
            if isinstance(queries, str):
                queries = [queries]
            return process_multiple_queries(queries)
        else:
            raise ValueError("Invalid query_type. Use 'single' or 'multiple'")
    except Exception as e:
        print(f"Error in scrape_emails: {e}")
        return 0


if __name__ == "__main__":
    # Test with single query
    query = 'site:instagram.com "fitness Coach" "@gmail.com"'
    result = scrape_emails("single", query)
    print(f"Found {result} new emails")