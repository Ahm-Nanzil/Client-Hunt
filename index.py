#!/usr/bin/env python3
"""
Email Campaign Manager - Python Version
Converted from PHP to Python with Flask web framework
"""

import csv
import json
import os
import time
import smtplib
import logging
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
import re
from flask import Flask, request, jsonify, render_template_string
import threading
import gc
import subprocess

# Configuration
BATCH_SIZE = 1
CSV_FILE = 'clients.csv'
TRACKING_FILE = 'email_tracking.json'
EMAIL_TEMPLATE = 'emailbody.html'

# Flask app setup
app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class EmailCampaignManager:
    def __init__(self):
        self.batch_size = BATCH_SIZE
        self.csv_file = CSV_FILE
        self.tracking_file = TRACKING_FILE
        self.email_template = EMAIL_TEMPLATE

        # Email settings
        self.smtp_server = 'smtp.gmail.com'
        self.smtp_port = 587
        self.email_user = 'ahmnanzil33@gmail.com'
        self.email_password = 'hpitjdlzhhmnhurc'
        self.sender_name = 'Web Development'
        self.sender_email = 'ahmnanzil@web.service'

    def initialize_tracking_data(self):
        """Initialize or load tracking data from JSON file"""
        if os.path.exists(self.tracking_file):
            try:
                with open(self.tracking_file, 'r') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
            except (json.JSONDecodeError, IOError):
                pass

        # Create default tracking data
        default_data = {
            'current_index': 0,
            'total_processed': 0,
            'last_batch_time': None,
            'all_sent': False,
            'current_batch_progress': 0
        }

        # Ensure directory exists
        os.makedirs(os.path.dirname(self.tracking_file) if os.path.dirname(self.tracking_file) else '.', exist_ok=True)

        # Save default data
        self.save_tracking_data(default_data)
        return default_data

    def save_tracking_data(self, data):
        """Save tracking data to JSON file"""
        with open(self.tracking_file, 'w') as f:
            json.dump(data, f, indent=2)

    def validate_email(self, email):
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    def get_clients_from_csv(self, start_index, batch_size):
        """Read clients from CSV file starting from specific index"""
        clients = []
        count = 0
        current_index = 0

        try:
            with open(self.csv_file, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)

                # Skip header row
                next(reader, None)

                for row in reader:
                    # Skip rows until we reach starting index
                    if current_index < start_index:
                        current_index += 1
                        continue

                    # Extract client data with safe indexing
                    email = row[0].strip() if len(row) > 0 else ''
                    name = row[1].strip() if len(row) > 1 else ''
                    address = row[2].strip() if len(row) > 2 else ''
                    customer_number = row[3].strip() if len(row) > 3 else ''
                    sent_status = row[4].strip() if len(row) > 4 else 'No'

                    # Validate email
                    if not self.validate_email(email):
                        current_index += 1
                        continue

                    # Only include clients that haven't been sent
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
            'total_rows': self.count_total_rows() - 1  # Subtract header
        }

    def count_total_rows(self):
        """Count total rows in CSV file"""
        try:
            with open(self.csv_file, 'r', newline='', encoding='utf-8') as csvfile:
                return sum(1 for _ in csv.reader(csvfile))
        except FileNotFoundError:
            return 0

    def mark_clients_as_sent(self, clients):
        """Mark clients as sent in CSV file"""
        # Process in chunks to avoid memory issues
        chunk_size = 50
        for i in range(0, len(clients), chunk_size):
            chunk = clients[i:i + chunk_size]
            self.mark_client_chunk_as_sent(chunk)

    def mark_client_chunk_as_sent(self, client_chunk):
        """Process a chunk of clients and mark as sent"""
        # Read entire CSV file
        rows = []
        try:
            with open(self.csv_file, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                rows = list(reader)
        except FileNotFoundError:
            logger.error(f"CSV file {self.csv_file} not found")
            return

        # Update sent status for processed clients
        for client in client_chunk:
            row_index = client['row_index'] + 1  # +1 because header is row 0
            if row_index < len(rows):
                # Ensure row has at least 5 columns
                while len(rows[row_index]) < 5:
                    rows[row_index].append("")
                rows[row_index][4] = "Yes"  # Mark as sent

        # Write updated data back to CSV
        with open(self.csv_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(rows)

    def reset_all_clients(self):
        """Reset all clients as unsent"""
        rows = []
        try:
            with open(self.csv_file, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                rows = list(reader)
        except FileNotFoundError:
            logger.error(f"CSV file {self.csv_file} not found")
            return

        # Reset sent status for all rows except header
        for i in range(1, len(rows)):
            # Ensure row has at least 5 columns
            while len(rows[i]) < 5:
                rows[i].append("")
            rows[i][4] = "No"  # Reset sent status

        # Write updated data back to CSV
        with open(self.csv_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(rows)

    def send_emails(self, clients):
        """Send emails to clients using SMTP"""
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

        # Process clients in chunks
        for i in range(0, len(clients), chunk_size):
            client_chunk = clients[i:i + chunk_size]

            # Update progress
            tracking['current_batch_progress'] = sent_count
            self.save_tracking_data(tracking)

            # Send emails for this chunk
            for client in client_chunk:
                try:
                    # Create message
                    msg = MIMEMultipart('alternative')
                    msg['Subject'] = "Boost Your Online Presence with a Professional Website 🌐"
                    msg['From'] = formataddr((self.sender_name, self.sender_email))
                    msg['To'] = formataddr((client['name'], client['email']))

                    # Add HTML content
                    html_part = MIMEText(email_content, 'html', 'utf-8')
                    msg.attach(html_part)

                    # Send email
                    with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                        server.starttls()
                        server.login(self.email_user, self.email_password)
                        server.send_message(msg)

                    sent_count += 1
                    logger.info(f"Email sent successfully to: {client['email']}")

                    # Small delay between emails
                    time.sleep(0.1)

                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to send email to {client['email']}: {str(e)}")

                # Update progress periodically
                if sent_count % 10 == 0:
                    tracking['current_batch_progress'] = sent_count
                    self.save_tracking_data(tracking)

            # Mark chunk as sent
            self.mark_clients_as_sent(client_chunk)

            # Cleanup and pause
            gc.collect()
            time.sleep(1)

        return {
            'sent': sent_count,
            'failed': failed_count,
            'total': total_to_send
        }

    def process_emails(self):
        """Main function to process and send emails"""
        # Initialize tracking
        tracking = self.initialize_tracking_data()
        tracking['current_batch_progress'] = 0
        self.save_tracking_data(tracking)

        # Get clients for current batch
        result = self.get_clients_from_csv(tracking['current_index'], self.batch_size)
        clients = result['clients']
        total_rows = result['total_rows']

        # Check if no clients to process
        if not clients:
            if tracking['total_processed'] >= total_rows or tracking['all_sent']:
                # Reset everything
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
                # Move to next batch
                tracking['current_index'] = result['last_index']
                self.save_tracking_data(tracking)
                return {
                    'status': 'skip',
                    'message': 'No new clients to process at this position. Moving to next batch.'
                }

        # Send emails
        email_result = self.send_emails(clients)
        sent_count = email_result['sent']
        failed_count = email_result['failed']

        # Update tracking
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
        """Get current progress for AJAX calls"""
        tracking = self.initialize_tracking_data()
        total_rows = self.count_total_rows() - 1

        return {
            'current_batch_progress': tracking['current_batch_progress'],
            'batch_size': self.batch_size,
            'total_processed': tracking['total_processed'],
            'total_clients': total_rows,
            'progress_percentage': round((tracking['total_processed'] / max(1, total_rows)) * 100, 1)
        }


# Initialize campaign manager
campaign_manager = EmailCampaignManager()

# HTML template for the web interface
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Email Campaign Manager</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 900px;
            margin: 50px auto;
            padding: 20px;
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1, h2 {
            color: #333;
        }
        .stats {
            margin: 20px 0;
            padding: 15px;
            background-color: #f9f9f9;
            border-radius: 4px;
        }
        .progress-bar {
            height: 20px;
            background-color: #e0e0e0;
            border-radius: 4px;
            margin: 10px 0;
            overflow: hidden;
        }
        .progress-bar-fill {
            height: 100%;
            background-color: #4CAF50;
            width: {{ overall_progress }}%;
            transition: width 0.5s;
        }
        .batch-progress-bar {
            height: 20px;
            background-color: #e0e0e0;
            border-radius: 4px;
            margin: 10px 0;
            overflow: hidden;
        }
        .batch-progress-bar-fill {
            height: 100%;
            background-color: #2196F3;
            width: {{ batch_progress }}%;
            transition: width 0.5s;
        }
        button {
            background-color: #4CAF50;
            color: white;
            border: none;
            padding: 10px 15px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            margin-right: 10px;
        }
        button:hover {
            background-color: #45a049;
        }
        button.reset {
            background-color: #f44336;
        }
        button.reset:hover {
            background-color: #d32f2f;
        }
        .alert {
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 4px;
        }
        .alert-success {
            background-color: #dff0d8;
            color: #3c763d;
            border: 1px solid #d6e9c6;
        }
        .alert-warning {
            background-color: #fcf8e3;
            color: #8a6d3b;
            border: 1px solid #faebcc;
        }
        .alert-info {
            background-color: #d9edf7;
            color: #31708f;
            border: 1px solid #bce8f1;
        }
        #result {
            margin-top: 20px;
            padding: 15px;
            background-color: #f0f0f0;
            border-radius: 4px;
            display: none;
        }
        .csv-info {
            margin-top: 30px;
            padding: 15px;
            background-color: #f0f0f0;
            border-radius: 4px;
        }
        .back-link {
            display: block;
            margin-top: 20px;
            text-align: center;
        }
        #sending-status {
            display: none;
            padding: 15px;
            background-color: #fff9c4;
            border-radius: 4px;
            margin-top: 20px;
            border: 1px solid #ffd54f;
        }
        .spinner {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid rgba(0,0,0,0.1);
            border-radius: 50%;
            border-top-color: #4CAF50;
            animation: spin 1s ease-in-out infinite;
            margin-right: 10px;
            vertical-align: middle;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Email Campaign Manager</h1>

        <div class="stats">
            <h2>Campaign Status</h2>
            <p><strong>Total Clients:</strong> <span id="total-clients">{{ total_clients }}</span></p>
            <p><strong>Batch Size:</strong> {{ batch_size }}</p>
            <p><strong>Emails Sent:</strong> <span id="emails-sent">{{ emails_sent }}</span></p>
            <p><strong>Next Batch Starting At:</strong> {{ next_batch_start }}</p>
            <p><strong>Last Batch Sent:</strong> {{ last_batch_time }}</p>

            <h3>Overall Progress</h3>
            <div class="progress-bar">
                <div class="progress-bar-fill" id="overall-progress"></div>
            </div>
            <p><span id="overall-percentage">{{ overall_progress }}</span>% Complete</p>

            <h3>Current Batch Progress</h3>
            <div class="batch-progress-bar">
                <div class="batch-progress-bar-fill" id="batch-progress"></div>
            </div>
            <p><span id="batch-percentage">{{ batch_progress }}</span>% of Current Batch</p>
        </div>

        <div id="sending-status">
            <div class="spinner"></div>
            <span id="status-text">Sending emails, please wait...</span>
            <p>Sent <span id="current-sent">0</span> of {{ batch_size }} emails</p>
        </div>

        <form id="emailForm">
            <button type="submit" id="sendBatch">Send Next Batch ({{ batch_size }} emails)</button>
            <button type="button" onclick="window.location.href='/reset'" class="reset" 
                    onclick="return confirm('Are you sure you want to reset the entire campaign?');">
                Reset Campaign
            </button>
            <button type="button" onclick="window.location.href='/manual'">Manual Lead Entry</button>
        <button type="button" id="startScrapingBtn">Start Scraping</button>
        </form>

        <script>
        document.getElementById('startScrapingBtn').addEventListener('click', () => {
            fetch('/start-scraping', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        alert('Scraping started successfully!');
                        console.log(data.output);
                    } else {
                        alert('Error: ' + data.message);
                    }
                })
                .catch(err => alert('Request failed: ' + err));
        });
        </script>


        <div id="result"></div>

        <div class="csv-info">
            <h3>CSV File Information</h3>
            <p>Make sure clients.csv file has the following columns:</p>
            <ul>
                <li>Email - Client email address</li>
                <li>Customer Name - Client's name</li>
                <li>Address - Client's address</li>
                <li>Customer Number - Unique identifier</li>
                <li>Sent - Tracking column (Yes/No)</li>
            </ul>
            <p><strong>Note:</strong> The system will automatically update the "Sent" column as emails are processed.</p>
        </div>

        <p class="back-link">Signed by Ahm Nanzil</p>
    </div>

    <script>
            function startScraping() {
                    const scrapingBtn = document.getElementById('scrapingBtn');
                    scrapingBtn.disabled = true;
                    scrapingBtn.textContent = 'Scraping...';
                    
                    fetch('/scraping')
                        .then(response => response.json())
                        .then(data => {
                            if (data.status === 'success') {
                                alert(`${data.message}\n\nDetails:\n- Total emails found: ${data.leads_scraped}\n- New leads added: ${data.new_leads_added}\n- Existing leads skipped: ${data.existing_leads_skipped}`);
                            } else {
                                alert('Scraping failed: ' + data.message);
                            }
                            scrapingBtn.disabled = false;
                            scrapingBtn.textContent = 'Start Scraping';
                            
                            // Refresh the page to update statistics
                            window.location.reload();
                        })
                        .catch(error => {
                            alert('Scraping failed: ' + error);
                            scrapingBtn.disabled = false;
                            scrapingBtn.textContent = 'Start Scraping';
                        });
                }
    
        function updateProgress() {
            fetch('/progress')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('emails-sent').textContent = data.total_processed;
                    document.getElementById('total-clients').textContent = data.total_clients;

                    const overallProgress = (data.total_processed / Math.max(1, data.total_clients)) * 100;
                    document.getElementById('overall-progress').style.width = overallProgress + '%';
                    document.getElementById('overall-percentage').textContent = overallProgress.toFixed(1);

                    const batchProgress = (data.current_batch_progress / Math.max(1, data.batch_size)) * 100;
                    document.getElementById('batch-progress').style.width = batchProgress + '%';
                    document.getElementById('batch-percentage').textContent = batchProgress.toFixed(1);
                    document.getElementById('current-sent').textContent = data.current_batch_progress;

                    if (document.getElementById('sending-status').style.display === 'block') {
                        setTimeout(updateProgress, 2000);
                    }
                })
                .catch(error => console.error('Error fetching progress:', error));
        }

        document.getElementById('emailForm').addEventListener('submit', function(e) {
            e.preventDefault();

            const sendButton = document.getElementById('sendBatch');
            sendButton.disabled = true;
            sendButton.textContent = 'Sending...';

            document.getElementById('sending-status').style.display = 'block';
            updateProgress();

            fetch('/send', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'}
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('sending-status').style.display = 'none';

                const resultDiv = document.getElementById('result');
                resultDiv.style.display = 'block';

                if (data.status === 'success') {
                    resultDiv.innerHTML = `
                        <div class="alert alert-success">
                            <h3>Batch Sent Successfully</h3>
                            <p>Sent ${data.sent_count} emails</p>
                            <p>Failed: ${data.failed_count || 0} emails</p>
                            <p>Total processed: ${data.total_processed} out of ${data.total_clients}</p>
                        </div>
                    `;
                } else {
                    resultDiv.innerHTML = `
                        <div class="alert alert-info">
                            <h3>${data.status === 'reset' ? 'Campaign Reset' : 'Batch Skipped'}</h3>
                            <p>${data.message}</p>
                        </div>
                    `;
                }

                updateProgress();
                sendButton.disabled = false;
                sendButton.textContent = 'Send Next Batch ({{ batch_size }} emails)';
            })
            .catch(error => {
                document.getElementById('sending-status').style.display = 'none';
                sendButton.disabled = false;
                sendButton.textContent = 'Send Next Batch ({{ batch_size }} emails)';
            });
        });

        document.addEventListener('DOMContentLoaded', updateProgress);
    </script>
</body>
</html>
'''
MANUAL_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Manual Lead Entry</title>
    <!-- Add same CSS styles as main template -->
</head>
<body>
    <div class="container">
        <h1>Manual Lead Entry</h1>
        <form id="manualForm">
            <input type="email" placeholder="Email" required>
            <input type="text" placeholder="Name" required>
            <input type="text" placeholder="Address">
            <input type="text" placeholder="Customer Number">
            <button type="submit">Add Lead</button>
        </form>
        <a href="/">Back to Dashboard</a>
    </div>
</body>
</html>
'''

# Flask routes
@app.route('/manual')
def manual_page():
    """Manual lead entry page"""
    return render_template_string(MANUAL_TEMPLATE)

@app.route('/start-scraping', methods=['POST'])
def start_scraping():
    try:
        # Run scrapping.py script as a subprocess
        result = subprocess.run(['python', 'scraping.py'], capture_output=True, text=True)
        # You can return output or status
        return jsonify({'status': 'success', 'output': result.stdout})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/')
def index():
    """Main dashboard page"""
    tracking = campaign_manager.initialize_tracking_data()
    total_rows = campaign_manager.count_total_rows() - 1

    overall_progress = round((tracking['total_processed'] / max(1, total_rows)) * 100, 1)
    batch_progress = round((tracking['current_batch_progress'] / max(1, BATCH_SIZE)) * 100, 1)

    return render_template_string(HTML_TEMPLATE,
                                  total_clients=total_rows,
                                  batch_size=BATCH_SIZE,
                                  emails_sent=tracking['total_processed'],
                                  next_batch_start=tracking['current_index'],
                                  last_batch_time=tracking['last_batch_time'] or 'Never',
                                  overall_progress=overall_progress,
                                  batch_progress=batch_progress
                                  )


@app.route('/progress')
def get_progress():
    """Get current progress via AJAX"""
    return jsonify(campaign_manager.get_current_progress())


@app.route('/send', methods=['POST'])
def send_emails():
    """Process and send email batch"""

    def send_in_background():
        return campaign_manager.process_emails()

    # Run email sending in background thread for better responsiveness
    result = send_in_background()
    return jsonify(result)


@app.route('/reset')
def reset_campaign():
    """Reset the entire campaign"""
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


if __name__ == '__main__':
    # Create required files if they don't exist
    if not os.path.exists(CSV_FILE):
        # Create sample CSV file
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Email', 'Customer Name', 'Address', 'Customer Number', 'Sent'])
            writer.writerow(['example@email.com', 'John Doe', '123 Main St', 'CUST001', 'No'])

    if not os.path.exists(EMAIL_TEMPLATE):
        # Create sample email template
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

    app.run(debug=True, host='0.0.0.0', port=5000)