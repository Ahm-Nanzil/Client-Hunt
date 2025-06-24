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
from gtts import gTTS
import pygame
import tempfile
from datetime import datetime

# Constants
QUERY_LOG_FILE = "search_queries.log"  # File to store all search queries


def log_query(query, query_type="single"):
    """Log the search query to a file with timestamp"""
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"{timestamp} - {query_type.upper()} - {query}\n"

        with open(QUERY_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)

        print(f"Logged query: {query} (Type: {query_type})")
    except Exception as e:
        print(f"Error logging query: {e}")


def play_captcha_alert():
    """Play a voice notification when CAPTCHA is detected"""
    try:
        print("🔊 Playing voice notification...")

        # Generate speech
        tts = gTTS(text="Attention! CAPTCHA detected. Please solve the captcha to continue!", lang='en')

        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
            temp_file = f.name
            tts.save(temp_file)

        # Initialize pygame mixer
        pygame.mixer.init()
        pygame.mixer.music.load(temp_file)
        pygame.mixer.music.play()

        # Wait until playback finishes
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)

        # Clean up
        pygame.mixer.quit()
        os.unlink(temp_file)

        print("🔊 Voice notification completed.")

    except Exception as e:
        print(f"Could not play voice notification: {e}")
        # Fallback to system beep if voice fails
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except:
            print("Fallback beep also failed.")


def load_existing_emails(csv_file="clients.csv"):
    """Load existing emails from clients.csv"""
    existing_emails = set()
    if os.path.exists(csv_file):
        try:
            df = pd.read_csv(csv_file)
            if 'Email' in df.columns:
                existing_emails = set(df['Email'].dropna().str.lower())
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
    new_data = [{'Email': email} for email in new_emails]

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
    """Main scraping function"""
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

            # CAPTCHA detection
            captcha_present = False
            try:
                # Check for recaptcha iframe or texts indicating CAPTCHA
                if driver.find_elements(By.CSS_SELECTOR, "iframe[src*='recaptcha']") or \
                        driver.find_elements(By.XPATH, "//*[contains(text(),'Select all images')]") or \
                        driver.find_elements(By.XPATH, "//*[contains(text(),\"I'm not a robot\")]"):
                    captcha_present = True
            except Exception:
                captcha_present = False

            if captcha_present:
                print("\n🚨 CAPTCHA DETECTED! 🚨")
                play_captcha_alert()  # Play voice notification
                print("Please solve it manually in the browser window.")
                print("The script will wait up to 5 minutes for you to complete it.")

                # Wait max 5 minutes for the search results container to appear
                start_wait = time.time()
                solved = False
                while time.time() - start_wait < 300:
                    try:
                        # Check if search results container is back
                        if driver.find_element(By.ID, "search"):
                            solved = True
                            print("✅ CAPTCHA solved. Continuing...")
                            break
                    except NoSuchElementException:
                        pass
                    time.sleep(3)
                if not solved:
                    print("❌ Timeout waiting for CAPTCHA to be solved. Exiting.")
                    break

            # Extract page text
            page_text = driver.find_element(By.TAG_NAME, "body").text
            emails = re.findall(r'[a-zA-Z0-9_.+-]+@gmail\.com', page_text)
            found_count = len(emails)
            unique_emails = set(email.lower() for email in emails)

            # Filter out existing emails
            new_emails = unique_emails - existing_emails

            print(f"Found {found_count} Gmail addresses ({len(unique_emails)} unique) on this page")
            print(f"New emails (not in clients.csv): {len(new_emails)}")

            all_emails.update(new_emails)

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


def process_single_query(query):
    """Process a single search query"""
    print(f"Processing single query: {query}")

    # Log the query
    log_query(query, "single")

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

        # Log each query
        log_query(query, "multiple")

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