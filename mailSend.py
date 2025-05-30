import smtplib
from email.message import EmailMessage

# Create the email
msg = EmailMessage()
msg['Subject'] = 'Test Email'
msg['From'] = 'your_email@example.com'
msg['To'] = 'recipient@example.com'
msg.set_content('This is a test email sent from Python.')

# SMTP server connection (for Gmail, use smtp.gmail.com)
with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
    smtp.login('your_email@example.com', 'your_email_password_or_app_password')
    smtp.send_message(msg)

print("Email sent successfully!")
