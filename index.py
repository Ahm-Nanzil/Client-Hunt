#!/usr/bin/env python3
"""
Email Campaign Manager - Fixed Scraping Version
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
from flask import Flask, request, jsonify, render_template_string, redirect, url_for
import threading
import gc

# Configuration
BATCH_SIZE = 1
CSV_FILE = 'clients.csv'
TRACKING_FILE = 'email_tracking.json'
EMAIL_TEMPLATE = 'emailbody.html'
SCRAPING_SCRIPT = 'seleniumScrapping.py'

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

    def run_scraping_with_queries(self, scrape_type, queries):
        """Run scraping with specific queries"""
        try:
            if not os.path.exists(SCRAPING_SCRIPT):
                return {
                    'status': 'error',
                    'message': f'Scraping script {SCRAPING_SCRIPT} not found in directory'
                }

            # Prepare arguments for the scraping script
            if scrape_type == 'single':
                args = ['python', SCRAPING_SCRIPT, '--single', queries[0]]
            else:  # multiple
                # Create a temporary file with queries
                temp_queries_file = 'temp_queries.txt'
                with open(temp_queries_file, 'w', encoding='utf-8') as f:
                    for query in queries:
                        f.write(query.strip() + '\n')

                args = ['python', SCRAPING_SCRIPT, '--multiple', temp_queries_file]

            # Run the scraping script
            result = subprocess.run(args, capture_output=True, text=True, timeout=600)

            # Clean up temporary file if created
            if scrape_type == 'multiple' and os.path.exists('temp_queries.txt'):
                os.remove('temp_queries.txt')

            if result.returncode == 0:
                # Count new emails added
                output_lines = result.stdout.strip().split('\n')
                emails_found = len([line for line in output_lines if '@' in line and 'Found' in line])

                return {
                    'status': 'success',
                    'message': f'Scraping completed! Processed {len(queries)} queries.',
                    'emails_found': emails_found,
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
                'message': 'Scraping timeout (10 minutes exceeded)'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Scraping error: {str(e)}'
            }


campaign_manager = EmailCampaignManager()

# Main Dashboard HTML Template
MAIN_HTML_TEMPLATE = '''
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
            <button type="button" onclick="resetCampaign()" class="reset">Reset Campaign</button>
            <button type="button" onclick="window.location.href='/scrape_options'" class="scraping">Start Scraping</button>
        </form>

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

        <p style="text-align: center; margin-top: 20px;">Signed by Ahm Nanzil</p>
    </div>

    <script>
        function resetCampaign() {
            if (confirm('Are you sure you want to reset the entire campaign?')) {
                fetch('/reset')
                    .then(response => response.json())
                    .then(data => {
                        const resultDiv = document.getElementById('result');
                        resultDiv.style.display = 'block';
                        resultDiv.innerHTML = `
                            <div class="alert alert-success">
                                <h3>Campaign Reset</h3>
                                <p>${data.message}</p>
                            </div>
                        `;
                        updateProgress();
                        setTimeout(() => window.location.reload(), 2000);
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

# Scraping Options Template
SCRAPE_OPTIONS_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Email Scraping Options</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            max-width: 800px; 
            margin: 50px auto; 
            padding: 20px; 
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .option-card { 
            border: 1px solid #ddd; 
            padding: 20px; 
            margin: 20px 0; 
            border-radius: 8px; 
            background-color: #f9f9f9;
        }
        .btn { 
            padding: 15px 30px; 
            background: #007bff; 
            color: white; 
            text-decoration: none; 
            border-radius: 5px; 
            display: inline-block; 
            margin: 10px; 
        }
        .btn:hover { background: #0056b3; }
        .btn-back {
            background: #6c757d;
            padding: 10px 20px;
            margin-bottom: 20px;
        }
        .btn-back:hover { background: #545b62; }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="btn btn-back">← Back to Dashboard</a>

        <h1>Email Scraping Options</h1>

        <div class="option-card">
            <h3>Single Query</h3>
            <p>Scrape emails using one search query at a time. Perfect for testing or targeting specific searches.</p>
            <a href="/scrape_single" class="btn">Single Query</a>
        </div>

        <div class="option-card">
            <h3>Multiple Queries</h3>
            <p>Scrape emails using multiple search queries in sequence. Ideal for bulk scraping with different search terms.</p>
            <a href="/scrape_multiple" class="btn">Multiple Queries</a>
        </div>
    </div>
</body>
</html>
'''

# Single Query Scraping Template
SCRAPE_SINGLE_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Single Query Scraping</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            max-width: 800px; 
            margin: 50px auto; 
            padding: 20px; 
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .form-group { margin: 20px 0; }
        label { display: block; margin-bottom: 10px; font-weight: bold; }
        input[type="text"] { 
            width: 100%; 
            padding: 12px; 
            border: 1px solid #ddd; 
            border-radius: 4px; 
            box-sizing: border-box;
        }
        .btn { 
            padding: 15px 30px; 
            background: #007bff; 
            color: white; 
            border: none; 
            border-radius: 5px; 
            cursor: pointer; 
        }
        .btn:hover { background: #0056b3; }
        .btn-back {
            background: #6c757d;
            padding: 10px 20px;
            margin-bottom: 20px;
            text-decoration: none;
            display: inline-block;
        }
        .btn-back:hover { background: #545b62; }
        .result { margin: 20px 0; padding: 15px; border-radius: 5px; }
        .success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .loading { background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
        .example { 
            background: #e9ecef; 
            padding: 10px; 
            border-radius: 4px; 
            margin-top: 10px; 
            font-style: italic;
        }
    </style>
</head>
<body>
    <div class="container">
        <a href="/scrape_options" class="btn btn-back">← Back to Scraping Options</a>

        <h1>Single Query Email Scraping</h1>

        <form id="scrapeForm">
            <div class="form-group">
                <label for="query">Search Query:</label>
                <input type="text" id="query" name="query" 
                       value='site:instagram.com "fitness Coach" "@gmail.com"' 
                       placeholder="Enter your search query">
                <div class="example">
                    Example: site:instagram.com "fitness Coach" "@gmail.com"<br>
                    This will search Instagram for fitness coaches with Gmail addresses.
                </div>
            </div>

            <button type="submit" class="btn