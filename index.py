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
            'sender_email': 'ahmnanzil@web.service'
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
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Email Campaign Manager</title>
    <link rel="icon" href="data:,">
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
        h1, h2 { color: #333; }
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
        button:hover { background-color: #45a049; }
        button.reset {
            background-color: #f44336;
        }
        button.reset:hover { background-color: #d32f2f; }
        button.scraping {
            background-color: #ff9800;
        }
        button.scraping:hover { background-color: #e68900; }
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
        .alert-error {
            background-color: #f2dede;
            color: #a94442;
            border: 1px solid #ebccd1;
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
        .modal {
            display: none; /* Keep this as none by default */
            justify-content: center;
            align-items: center;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.5);
        }
        
        .modal-content {
            background-color: #fefefe;
            padding: 20px;
            border: 1px solid #888;
            width: 50%;
            border-radius: 8px;
            position: relative;
        }
        
        .close {
            color: #aaa;
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
        }
        .close:hover {
            color: black;
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
        
        <div id="result"></div>
        
        <form id="emailForm">
            <button type="submit" id="sendBatch">Send Next Batch ({{ batch_size }} emails)</button>
            <button type="button" onclick="resetCampaign()" class="reset">Reset Campaign</button>
            <button type="button" onclick="startScraping()" id="scrapingBtn" class="scraping">Start Scraping</button>
            <button type="button" onclick="showModal()" id="modalBtn" class="scraping">Modal Show</button>
            <button type="button" onclick="window.location.href='/config'" class="reset">⚙️ Settings</button>

        </form>

        

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

        <p style="text-align: center; margin-top: 20px;">Signed by Ahm Nanzil</p>
    </div>

    <div id="myModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal()">&times;</span>
            <div id="modal-body">
                <!-- Content will be loaded here -->
            </div>
        </div>
    </div>

    <script>
        function bindModalForm() {
            console.log("✅ Entered script");

            const formSingle = document.getElementById('scrapeFormSingle');
            const formMultiple = document.getElementById('scrapeFormMultiple');

            if (formSingle) {
                console.log("🟢 Binding Single Query Form");

                formSingle.addEventListener('submit', function(e) {
                    e.preventDefault();
                    const query = document.getElementById('querySingle').value;
                    const resultDiv = document.getElementById('resultSingle');

                    if (!query.trim()) {
                        resultDiv.innerHTML = '<div class="result error">Please enter a search query.</div>';
                        resultDiv.style.display = 'block';
                        return;
                    }

                    resultDiv.innerHTML = '<div class="result loading">Scraping in progress...</div>';
                    resultDiv.style.display = 'block';

                    fetch('/process_scrape', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ type: 'single', queries: [query] })
                    })
                    .then(response => response.json())
                    .then(data => {
                        resultDiv.innerHTML = '<div class="result ' + (data.success ? 'success' : 'error') + '">' + data.message + '</div>';
                    })
                    .catch(error => {
                        resultDiv.innerHTML = '<div class="result error">Error: ' + error.message + '</div>';
                    });
                });

            } else if (formMultiple) {
                console.log("🟢 Binding Multiple Query Form");

                formMultiple.addEventListener('submit', function(e) {
                    e.preventDefault();

                    const queriesText = document.getElementById('queries') ? document.getElementById('queries').value : '';
                    const resultDiv = document.getElementById('result');

                    const queries = queriesText.split('\\n').filter(function(q) { return q.trim() !== ''; });

                    if (queries.length === 0) {
                        resultDiv.innerHTML = '<div class="result error">Please enter valid search queries.</div>';
                        resultDiv.style.display = 'block';
                        return;
                    }

                    resultDiv.innerHTML = '<div class="result loading">Scraping ' + queries.length + ' queries in progress...</div>';
                    resultDiv.style.display = 'block';

                    fetch('/process_scrape', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            type: 'multiple',
                            queries: queries
                        })
                    })
                    .then(response => response.json())
                    .then(data => {
                        resultDiv.innerHTML = '<div class="result ' + (data.success ? 'success' : 'error') + '">' + data.message + '</div>';
                    })
                    .catch(error => {
                        resultDiv.innerHTML = '<div class="result error">Error: ' + error.message + '</div>';
                    });
                });

            } else {
                console.warn("⚠️ No matching form found in modal.");
            }
        }

        function startScraping() {
            window.location.href = '/scrape_options';
        }

        function showModal() {
            fetch('/scrape_options_modal')
                .then(response => response.text())
                .then(html => {
                    document.getElementById('modal-body').innerHTML = html;
                    document.getElementById('myModal').style.display = 'flex';
                    bindModalForm();
                })
                .catch(error => {
                    console.error('Error loading modal content:', error);
                });
        }

        function loadModalContent(url) {
            fetch(url)
                .then(response => response.text())
                .then(html => {
                    document.getElementById('modal-body').innerHTML = html;
                    bindModalForm();
                })
                .catch(error => {
                    console.error('Error loading content:', error);
                });
        }

        function closeModal() {
            document.getElementById('myModal').style.display = 'none';
        }

        function resetCampaign() {
            if (confirm('Are you sure you want to reset the entire campaign?')) {
                fetch('/reset')
                    .then(response => response.json())
                    .then(data => {
                        const resultDiv = document.getElementById('result');
                        resultDiv.style.display = 'block';
                        resultDiv.innerHTML = '<div class="alert alert-success"><h3>Campaign Reset</h3><p>' + data.message + '</p></div>';
                        updateProgress();
                        setTimeout(function() { window.location.reload(); }, 2000);
                    });
            }
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
                    resultDiv.innerHTML = '<div class="alert alert-success"><h3>Batch Sent Successfully</h3><p>Sent ' + data.sent_count + ' emails</p><p>Failed: ' + (data.failed_count || 0) + ' emails</p><p>Total processed: ' + data.total_processed + ' out of ' + data.total_clients + '</p></div>';
                } else {
                    resultDiv.innerHTML = '<div class="alert alert-info"><h3>' + (data.status === 'reset' ? 'Campaign Reset' : 'Batch Skipped') + '</h3><p>' + data.message + '</p></div>';
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
</html>'''
CONFIG_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Email Configuration</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
        .container { max-width: 600px; margin: 50px auto; padding: 20px; background-color: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; text-align: center; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; color: #555; }
        input[type="text"], input[type="email"], input[type="number"], input[type="password"] { 
            width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; 
        }
        button { background-color: #4CAF50; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-size: 16px; width: 100%; }
        button:hover { background-color: #45a049; }
        .back-btn { background-color: #2196F3; margin-bottom: 20px; width: auto; }
        .back-btn:hover { background-color: #1976D2; }
        .alert { padding: 15px; margin-bottom: 20px; border-radius: 4px; }
        .alert-success { background-color: #dff0d8; color: #3c763d; border: 1px solid #d6e9c6; }
        .alert-error { background-color: #f2dede; color: #a94442; border: 1px solid #ebccd1; }
    </style>
</head>
<body>
    <div class="container">
        <button onclick="window.location.href='/'" class="back-btn">← Back to Dashboard</button>

        <h1>Email Configuration</h1>

        <div id="message"></div>

        <form id="configForm">
            <div class="form-group">
                <label for="batch_size">Batch Size:</label>
                <input type="number" id="batch_size" name="batch_size" value="{{ batch_size }}" min="1" required>
            </div>

            <div class="form-group">
                <label for="smtp_server">SMTP Server:</label>
                <input type="text" id="smtp_server" name="smtp_server" value="{{ smtp_server }}" required>
            </div>

            <div class="form-group">
                <label for="smtp_port">SMTP Port:</label>
                <input type="number" id="smtp_port" name="smtp_port" value="{{ smtp_port }}" required>
            </div>

            <div class="form-group">
                <label for="email_user">Email Username:</label>
                <input type="email" id="email_user" name="email_user" value="{{ email_user }}" required>
            </div>

            <div class="form-group">
                <label for="email_password">Email Password:</label>
                <input type="password" id="email_password" name="email_password" value="{{ email_password }}" required>
            </div>

            <div class="form-group">
                <label for="sender_name">Sender Name:</label>
                <input type="text" id="sender_name" name="sender_name" value="{{ sender_name }}" required>
            </div>

            <div class="form-group">
                <label for="sender_email">Sender Email Display:</label>
                <input type="email" id="sender_email" name="sender_email" value="{{ sender_email }}" required>
            </div>

            <button type="submit">Update Configuration</button>
        </form>
    </div>

    <script>
        document.getElementById('configForm').addEventListener('submit', function(e) {
            e.preventDefault();

            const formData = new FormData(e.target);
            const data = {};
            for (let [key, value] of formData.entries()) {
                data[key] = value;
            }

            fetch('/update_config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(result => {
                const messageDiv = document.getElementById('message');
                if (result.success) {
                    messageDiv.innerHTML = '<div class="alert alert-success">' + result.message + '</div>';
                    setTimeout(() => window.location.href = '/', 2000);
                } else {
                    messageDiv.innerHTML = '<div class="alert alert-error">' + result.message + '</div>';
                }
            })
            .catch(error => {
                document.getElementById('message').innerHTML = '<div class="alert alert-error">Error: ' + error.message + '</div>';
            });
        });
    </script>
</body>
</html>'''

@app.route('/')
@app.route('/')
def index():
    tracking = campaign_manager.initialize_tracking_data()
    total_rows = campaign_manager.count_total_rows() - 1
    config = campaign_manager.load_email_config()  # ADD THIS LINE

    overall_progress = round((tracking['total_processed'] / max(1, total_rows)) * 100, 1)
    batch_progress = round((tracking['current_batch_progress'] / max(1, config['batch_size'])) * 100, 1)  # USE config['batch_size']

    return render_template_string(HTML_TEMPLATE,
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
    return render_template_string(CONFIG_TEMPLATE, **config)


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