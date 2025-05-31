from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import re
import os

def search_and_save(search_query='site:instagram.com "fitness Coach" "@gmail.com"'):
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
                print("\nCAPTCHA detected! Please solve it manually in the browser window.")
                print("The script will wait up to 5 minutes for you to complete it.")
                # Wait max 5 minutes for the search results container to appear
                start_wait = time.time()
                solved = False
                while time.time() - start_wait < 300:
                    try:
                        # Check if search results container is back
                        if driver.find_element(By.ID, "search"):
                            solved = True
                            print("CAPTCHA solved. Continuing...")
                            break
                    except NoSuchElementException:
                        pass
                    time.sleep(3)
                if not solved:
                    print("Timeout waiting for CAPTCHA to be solved. Exiting.")
                    break

            # Extract page text
            page_text = driver.find_element(By.TAG_NAME, "body").text
            emails = re.findall(r'[a-zA-Z0-9_.+-]+@gmail\.com', page_text)
            found_count = len(emails)
            unique_emails = set(emails)
            print(f"Found {found_count} Gmail addresses ({len(unique_emails)} unique) on this page")
            all_emails.update(unique_emails)

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

        # Save to file
        timestamp = int(time.time())
        filename = f"google_gmail_emails_{timestamp}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"Search Query: {search_query}\n")
            f.write(f"Extraction Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*50 + "\n\n")
            for email in sorted(all_emails):
                f.write(email + "\n")

        print(f"\nExtraction complete. Found {len(all_emails)} unique Gmail addresses.")
        print(f"Saved to file: {os.path.abspath(filename)}")

        return filename

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return None

    finally:
        driver.quit()

if __name__ == "__main__":
    query = 'site:instagram.com "fitness Coach" "@gmail.com"'
    search_and_save(query)
