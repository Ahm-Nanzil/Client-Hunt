import yagmail
import os

# Email configuration
smtp_username = "ahmnanzil33@gmail.com"
smtp_password = "hpitjdlzhhmnhurc"

from_name = "Web Development"
recipient_email = "ahmnanzilofficial@gmail.com"
recipient_name = "Client"

# Load email body
template_path = os.path.join(os.path.dirname(__file__), "emailbody.html")
try:
    with open(template_path, "r", encoding="utf-8") as file:
        email_body = file.read()
except FileNotFoundError:
    print("Error: emailbody.html not found.")
    exit(1)

# Send email
try:
    yag = yagmail.SMTP(user=smtp_username, password=smtp_password)
    yag.send(
        to=recipient_email,
        subject="Boost Your Online Presence with a Professional Website 🌐",
        contents=email_body,
    )
    print(f"Email has been sent successfully to {recipient_email}!")
except Exception as e:
    print(f"Email could not be sent. Error: {str(e)}")
