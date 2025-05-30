import smtplib
from email.message import EmailMessage

# SMTP configuration
smtp_server = "smtp.gmail.com"
smtp_port = 587
smtp_username = "ahmnanzil33@gmail.com"
smtp_password = "hpitjdlzhhmnhurc"

# Email details
from_email = "ahmnanzil33@gmail.com"
to_email = "ahmnanzil111@gmail.com"
subject = "Test Email from Python"
body = "Hello! This is a test email sent using Python and Gmail SMTP."

# Compose the email
msg = EmailMessage()
msg["Subject"] = subject
msg["From"] = from_email
msg["To"] = to_email
msg.set_content(body)

# Send the email
try:
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()  # Secure the connection
        server.login(smtp_username, smtp_password)
        server.send_message(msg)
        print("Email sent successfully!")
except Exception as e:
    print(f"Failed to send email: {e}")
