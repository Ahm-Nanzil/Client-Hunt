import smtplib
from email.message import EmailMessage
import os

# Email configuration
smtp_server = "smtp.gmail.com"
smtp_port = 587
smtp_username = "ahmnanzil33@gmail.com"
smtp_password = "hpitjdlzhhmnhurc"

from_email = "ahmnanzil@web.service"  # This might cause issues if not a verified domain
from_name = "Web Development"

# Recipient info
recipient_email = "recipient@example.com"  # <- change this
recipient_name = "Client"

# Load email body
template_path = os.path.join(os.path.dirname(__file__), "emailbody.html")

try:
    with open(template_path, "r", encoding="utf-8") as file:
        email_body = file.read()
except FileNotFoundError:
    print("Error: emailbody.html not found.")
    exit(1)

if not recipient_email:
    print("Error: Recipient email address is missing.")
    exit(1)

# Create email
msg = EmailMessage()
msg["Subject"] = "Boost Your Online Presence with a Professional Website 🌐"
msg["From"] = f"{from_name} <{from_email}>"
msg["To"] = f"{recipient_name} <{recipient_email}>"

msg.set_content("This is a fallback plain-text version of the email.")
msg.add_alternative(email_body, subtype="html")

# Send email
try:
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.send_message(msg)
        print(f"Email has been sent successfully to {recipient_email}!")
except Exception as e:
    print(f"Email could not be sent. Error: {str(e)}")
