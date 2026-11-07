import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

SMTP_SERVERS = {
    'gmail': {'host': 'smtp.gmail.com', 'port': 587, 'ssl': False, 'tls': True},
    'outlook': {'host': 'smtp-mail.outlook.com', 'port': 587, 'ssl': False, 'tls': True},
    'yahoo': {'host': 'smtp.mail.yahoo.com', 'port': 587, 'ssl': False, 'tls': True},
    'custom': {'host': '', 'port': 587, 'ssl': False, 'tls': True}
}

def get_smtp_config(provider, custom_host=None, custom_port=None, use_ssl=False):
    p = provider.lower()
    if p in SMTP_SERVERS and p != 'custom':
        return SMTP_SERVERS[p]['host'], SMTP_SERVERS[p]['port'], SMTP_SERVERS[p]['ssl']
    return custom_host or 'smtp.gmail.com', int(custom_port or 587), bool(use_ssl)

def test_smtp_connection(provider, sender_email, password, custom_host=None, custom_port=None, use_ssl=False):
    """
    Tests SMTP connection and authentication.
    Returns: (bool success, str message)
    """
    host, port, ssl_mode = get_smtp_config(provider, custom_host, custom_port, use_ssl)
    sender_email = sender_email.strip()
    password = password.strip().replace(" ", "")

    try:
        if ssl_mode or port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)
            server.ehlo()
            server.starttls()
            server.ehlo()

        server.login(sender_email, password)
        server.quit()
        return True, "SMTP connection successful! Credentials are valid."
    except smtplib.SMTPAuthenticationError as e:
        return False, f"Authentication failed: Check email or App Password. For Gmail, use an App Password (not your normal password)."
    except Exception as e:
        return False, f"Connection error: {str(e)}"

def send_email(provider, sender_email, password, recipient_email, subject, body, 
               attachments=None, custom_host=None, custom_port=None, use_ssl=False, is_html=False):
    """
    Sends an email to a single recipient with optional attachments.
    Returns: (bool success, str message)
    """
    if not recipient_email or '@' not in str(recipient_email):
        return False, "Invalid recipient email address"

    host, port, ssl_mode = get_smtp_config(provider, custom_host, custom_port, use_ssl)
    sender_email = sender_email.strip()
    password = password.strip().replace(" ", "")
    recipient_email = str(recipient_email).strip()

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject or "No Subject"

    # Message body
    content_type = 'html' if is_html else 'plain'
    msg.attach(MIMEText(body or "", content_type, 'utf-8'))

    # Attachments
    if attachments:
        for file_path in attachments:
            if os.path.isfile(file_path):
                try:
                    filename = os.path.basename(file_path)
                    with open(file_path, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", f"attachment; filename= {filename}")
                    msg.attach(part)
                except Exception as ex:
                    print(f"Failed to attach {file_path}: {ex}")

    try:
        if ssl_mode or port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=20)
        else:
            server = smtplib.SMTP(host, port, timeout=20)
            server.ehlo()
            server.starttls()
            server.ehlo()

        server.login(sender_email, password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.quit()
        return True, "Email sent successfully"
    except smtplib.SMTPAuthenticationError:
        return False, "Authentication failed. Check your App Password."
    except Exception as e:
        return False, f"Failed: {str(e)}"
