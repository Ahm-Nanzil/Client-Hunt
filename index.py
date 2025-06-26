#!/usr/bin/env python3
"""
Email Campaign Manager - Optimized Version
"""

import csv
import json
import os
import time
import smtplib
import logging
import subprocess
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
import re
from flask import Flask, request, jsonify, render_template_string, render_template
import threading
import gc
from seleniumScrapping import scrape_emails

# Configuration
BATCH_SIZE = 1
CSV_FILE = 'clients.csv'
TRACKING_FILE = 'email_tracking.json'
EMAIL_TEMPLATE = 'emailbody.html'
SCRAPING_SCRIPT = 'seleniumScrapping.py'
CONFIG_FILE = 'email_config.json'  # ADD THIS LINE

# Flask app setup
app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class EmailCampaignManager:
    def __init__(self):
        # Load configuration
        config = self.load_email_config()

        self.batch_size = config['batch_size']
        self.csv_file = CSV_FILE
        self.tracking_file = TRACKING_FILE
        self.email_template = EMAIL_TEMPLATE

        # Email settings from config
        self.smtp_server = config['smtp_server']
        self.smtp_port = config['smtp_port']
        self.email_user = config['email_user']
        self.email_password = config['email_password']
        self.sender_name = config['sender_name']
        self.sender_email = config['sender_email']

    def load_email_config(self):
        """Load email configuration from file or create default"""
        default_config = {
            'batch_size': 50,
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'email_user': 'ahmnanzil33@gmail.com',
            'email_password': 'hpitjdlzhhmnhurc',
            'sender_name': 'Web Development',
            'sender_email': 'ahmnanzil22334@gmail.com'
        }

        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults for any missing keys
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
            except (json.JSONDecodeError, IOError):
                pass

        # Save default config
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=2)
        return default_config

    def save_email_config(self, config):
        """Save email configuration to file"""
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    def initialize_tracking_data(self):
        if os.path.exists(self.tracking_file):
            try:
                with open(self.tracking_file, 'r') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
            except (json.JSONDecodeError, IOError):
                pass

        default_data = {
            'current_index': 0,
            'total_processed': 0,
            'last_batch_time': None,
            'all_sent': False,
            'current_batch_progress': 0
        }

        os.makedirs(os.path.dirname(self.tracking_file) if os.path.dirname(self.tracking_file) else '.', exist_ok=True)
        self.save_tracking_data(default_data)
        return default_data

    def save_tracking_data(self, data):
        with open(self.tracking_file, 'w') as f:
            json.dump(data, f, indent=2)

    def validate_email(self, email):
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    def get_clients_from_csv(self, start_index, batch_size):
        clients = []
        count = 0
        current_index = 0

        try:
            with open(self.csv_file, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                next(reader, None)

                for row in reader:
                    if current_index < start_index:
                        current_index += 1
                        continue

                    email = row[0].strip() if len(row) > 0 else ''
                    name = row[1].strip() if len(row) > 1 else ''
                    address = row[2].strip() if len(row) > 2 else ''
                    customer_number = row[3].strip() if len(row) > 3 else ''
                    sent_status = row[4].strip() if len(row) > 4 else 'No'

                    if not self.validate_email(email):
                        current_index += 1
                        continue

                    if sent_status.lower() != 'yes':
                        clients.append({
                            'email': email,
                            'name': name,
                            'address': address,
                            'customer_number': customer_number,
                            'row_index': current_index
                        })

                        count += 1
                        if count >= batch_size:
                            break

                    current_index += 1

        except FileNotFoundError:
            logger.error(f"CSV file {self.csv_file} not found")
            return {'clients': [], 'last_index': 0, 'total_rows': 0}

        return {
            'clients': clients,
            'last_index': current_index,
            'total_rows': self.count_total_rows() - 1
        }

    def count_total_rows(self):
        try:
            with open(self.csv_file, 'r', newline='', encoding='utf-8') as csvfile:
                return sum(1 for _ in csv.reader(csvfile))
        except FileNotFoundError:
            return 0

    def mark_clients_as_sent(self, clients):
        chunk_size = 50
        for i in range(0, len(clients), chunk_size):
            chunk = clients[i:i + chunk_size]
            self.mark_client_chunk_as_sent(chunk)

    def mark_client_chunk_as_sent(self, client_chunk):
        rows = []
        try:
            with open(self.csv_file, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                rows = list(reader)
        except FileNotFoundError:
            logger.error(f"CSV file {self.csv_file} not found")
            return

        for client in client_chunk:
            row_index = client['row_index'] + 1
            if row_index < len(rows):
                while len(rows[row_index]) < 5:
                    rows[row_index].append("")
                rows[row_index][4] = "Yes"

        with open(self.csv_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(rows)

    def reset_all_clients(self):
        rows = []
        try:
            with open(self.csv_file, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                rows = list(reader)
        except FileNotFoundError:
            logger.error(f"CSV file {self.csv_file} not found")
            return

        for i in range(1, len(rows)):
            while len(rows[i]) < 5:
                rows[i].append("")
            rows[i][4] = "No"

        with open(self.csv_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(rows)

    def send_emails(self, clients):
        try:
            with open(self.email_template, 'r', encoding='utf-8') as f:
                email_content = f.read()
        except FileNotFoundError:
            email_content = "<h1>Default Email Content</h1>"

        sent_count = 0
        failed_count = 0
        total_to_send = len(clients)
        tracking = self.initialize_tracking_data()
        chunk_size = 20

        for i in range(0, len(clients), chunk_size):
            client_chunk = clients[i:i + chunk_size]

            tracking['current_batch_progress'] = sent_count
            self.save_tracking_data(tracking)

            for client in client_chunk:
                try:
                    msg = MIMEMultipart('alternative')
                    msg['Subject'] = "Boost Your Online Presence with a Professional Website 🌐"
                    msg['From'] = formataddr((self.sender_name, self.sender_email))
                    msg['To'] = formataddr((client['name'], client['email']))

                    html_part = MIMEText(email_content, 'html', 'utf-8')
                    msg.attach(html_part)

                    with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                        server.starttls()
                        server.login(self.email_user, self.email_password)
                        server.send_message(msg)

                    sent_count += 1
                    logger.info(f"Email sent successfully to: {client['email']}")
                    time.sleep(0.1)

                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to send email to {client['email']}: {str(e)}")

                if sent_count % 10 == 0:
                    tracking['current_batch_progress'] = sent_count
                    self.save_tracking_data(tracking)

            self.mark_clients_as_sent(client_chunk)
            gc.collect()
            time.sleep(1)

        return {
            'sent': sent_count,
            'failed': failed_count,
            'total': total_to_send
        }

    def process_emails(self):
        tracking = self.initialize_tracking_data()
        tracking['current_batch_progress'] = 0
        self.save_tracking_data(tracking)

        result = self.get_clients_from_csv(tracking['current_index'], self.batch_size)
        clients = result['clients']
        total_rows = result['total_rows']

        if not clients:
            if tracking['total_processed'] >= total_rows or tracking['all_sent']:
                self.reset_all_clients()
                tracking.update({
                    'current_index': 0,
                    'total_processed': 0,
                    'all_sent': False,
                    'current_batch_progress': 0
                })
                self.save_tracking_data(tracking)
                return {
                    'status': 'reset',
                    'message': 'All clients have been processed. Starting over from the beginning.'
                }
            else:
                tracking['current_index'] = result['last_index']
                self.save_tracking_data(tracking)
                return {
                    'status': 'skip',
                    'message': 'No new clients to process at this position. Moving to next batch.'
                }

        email_result = self.send_emails(clients)
        sent_count = email_result['sent']
        failed_count = email_result['failed']

        tracking.update({
            'current_index': result['last_index'],
            'total_processed': tracking['total_processed'] + sent_count,
            'last_batch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'current_batch_progress': 0
        })

        if tracking['total_processed'] >= total_rows:
            tracking['all_sent'] = True

        self.save_tracking_data(tracking)

        return {
            'status': 'success',
            'sent_count': sent_count,
            'failed_count': failed_count,
            'total_processed': tracking['total_processed'],
            'total_clients': total_rows,
            'next_batch_starts_at': tracking['current_index']
        }

    def get_current_progress(self):
        tracking = self.initialize_tracking_data()
        total_rows = self.count_total_rows() - 1

        return {
            'current_batch_progress': tracking['current_batch_progress'],
            'batch_size': self.batch_size,
            'total_processed': tracking['total_processed'],
            'total_clients': total_rows,
            'progress_percentage': round((tracking['total_processed'] / max(1, total_rows)) * 100, 1)
        }

    def run_scraping(self):
        try:
            if not os.path.exists(SCRAPING_SCRIPT):
                return {
                    'status': 'error',
                    'message': f'Scraping script {SCRAPING_SCRIPT} not found in directory'
                }

            result = subprocess.run(['python', SCRAPING_SCRIPT],
                                    capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                # Parse output to get results
                output_lines = result.stdout.strip().split('\n')
                return {
                    'status': 'success',
                    'message': 'Scraping completed successfully',
                    'leads_scraped': len([line for line in output_lines if '@' in line]),
                    'new_leads_added': 0,
                    'existing_leads_skipped': 0,
                    'output': result.stdout
                }
            else:
                return {
                    'status': 'error',
                    'message': f'Scraping failed: {result.stderr}'
                }

        except subprocess.TimeoutExpired:
            return {
                'status': 'error',
                'message': 'Scraping timeout (5 minutes exceeded)'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Scraping error: {str(e)}'
            }


campaign_manager = EmailCampaignManager()

# Fixed HTML Template with proper escaping
HTML_TEMPLATE = "main.html"
CONFIG_TEMPLATE ="config.html"

@app.route('/')
@app.route('/')
def index():
    tracking = campaign_manager.initialize_tracking_data()
    total_rows = campaign_manager.count_total_rows() - 1
    config = campaign_manager.load_email_config()  # ADD THIS LINE

    overall_progress = round((tracking['total_processed'] / max(1, total_rows)) * 100, 1)
    batch_progress = round((tracking['current_batch_progress'] / max(1, config['batch_size'])) * 100, 1)  # USE config['batch_size']

    return render_template(HTML_TEMPLATE,
                                  total_clients=total_rows,
                                  batch_size=config['batch_size'],  # USE config['batch_size']
                                  emails_sent=tracking['total_processed'],
                                  next_batch_start=tracking['current_index'],
                                  last_batch_time=tracking['last_batch_time'] or 'Never',
                                  overall_progress=overall_progress,
                                  batch_progress=batch_progress)


@app.route('/progress')
def get_progress():
    return jsonify(campaign_manager.get_current_progress())



@app.route('/send', methods=['POST'])
def send_emails():
    result = campaign_manager.process_emails()
    return jsonify(result)


@app.route('/reset')
def reset_campaign():
    campaign_manager.reset_all_clients()
    tracking = campaign_manager.initialize_tracking_data()
    tracking.update({
        'current_index': 0,
        'total_processed': 0,
        'all_sent': False,
        'current_batch_progress': 0
    })
    campaign_manager.save_tracking_data(tracking)

    return jsonify({
        'status': 'success',
        'message': 'Campaign has been reset successfully'
    })

@app.route('/scraping')
def scraping():
    result = campaign_manager.run_scraping()
    return jsonify(result)
@app.route('/scrape_options')
def scrape_options():
    """Route to show scraping options"""
    return render_template('scrape_options.html')


@app.route('/scrape_single')
def scrape_single():
    """Route for single query scraping"""
    return render_template('scrape_single.html')


@app.route('/scrape_multiple')
def scrape_multiple():
    """Route for multiple query scraping"""
    return render_template('scrape_multiple.html')


@app.route('/process_scrape', methods=['POST'])
def process_scrape():
    """Process the scraping request"""
    try:
        data = request.get_json()
        query_type = data.get('type')
        queries = data.get('queries')

        if not query_type or not queries:
            return jsonify({'success': False, 'message': 'Missing required data'})

        # Call the scraping function
        result = scrape_emails(query_type, queries)

        return jsonify({
            'success': True,
            'message': f'Scraping completed! Found {result} new emails.',
            'count': result
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/scrape_options_modal')
def scrape_options_modal():
    """Route to return scrape_options.html content for modal"""
    return render_template('scrape_options.html')

@app.route('/scrape_single_modal')
def scrape_single_modal():
    """Route to return scrape_single.html content for modal"""
    return render_template('scrape_single.html')

@app.route('/scrape_multiple_modal')
def scrape_multiple_modal():
    """Route to return scrape_multiple.html content for modal"""
    return render_template('scrape_multiple.html')


@app.route('/config')
def config():
    """Show configuration page"""
    config = campaign_manager.load_email_config()
    return render_template(CONFIG_TEMPLATE, **config)


@app.route('/update_config', methods=['POST'])
def update_config():
    """Update email configuration"""
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ['batch_size', 'smtp_server', 'smtp_port', 'email_user',
                           'email_password', 'sender_name', 'sender_email']

        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'success': False, 'message': f'Missing required field: {field}'})

        # Validate batch_size is a positive integer
        try:
            data['batch_size'] = int(data['batch_size'])
            if data['batch_size'] <= 0:
                raise ValueError()
        except ValueError:
            return jsonify({'success': False, 'message': 'Batch size must be a positive integer'})

        # Validate smtp_port is an integer
        try:
            data['smtp_port'] = int(data['smtp_port'])
        except ValueError:
            return jsonify({'success': False, 'message': 'SMTP port must be an integer'})

        # Save configuration
        campaign_manager.save_email_config(data)

        # Update campaign manager instance
        campaign_manager.batch_size = data['batch_size']
        campaign_manager.smtp_server = data['smtp_server']
        campaign_manager.smtp_port = data['smtp_port']
        campaign_manager.email_user = data['email_user']
        campaign_manager.email_password = data['email_password']
        campaign_manager.sender_name = data['sender_name']
        campaign_manager.sender_email = data['sender_email']

        return jsonify({'success': True, 'message': 'Configuration updated successfully'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error updating configuration: {str(e)}'})


if __name__ == '__main__':
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Email', 'Customer Name', 'Address', 'Customer Number', 'Sent'])
            writer.writerow(['example@email.com', 'John Doe', '123 Main St', 'CUST001', 'No'])

    if not os.path.exists(EMAIL_TEMPLATE):
        with open(EMAIL_TEMPLATE, 'w', encoding='utf-8') as f:
            f.write('''
            <html>
            <body>
                <h1>Professional Website Services</h1>
                <p>Dear Valued Customer,</p>
                <p>Boost your online presence with a professional website!</p>
                <p>Best regards,<br>Web Development Team</p>
            </body>
            </html>
            ''')

    print("Email Campaign Manager is starting...")
    print("Access the web interface at: http://localhost:5000")
    print("\nMake sure to:")
    print("1. Update your email credentials in the script")
    print("2. Place your clients.csv file in the same directory")
    print("3. Create your emailbody.html template")
    print("4. Ensure seleniumScrapping.py is in the same directory")

    app.run(debug=True, host='0.0.0.0', port=5000)