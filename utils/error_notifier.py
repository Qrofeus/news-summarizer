import logging
import smtplib
from email.mime.text import MIMEText

from config import Config


def send_error_email(error: str, traceback_str: str, config: Config) -> None:
    body = f'Error: {error}\n\nTraceback:\n{traceback_str}'
    try:
        msg = MIMEText(body, 'plain')
        msg['Subject'] = 'News Digest Pipeline Error'
        msg['From'] = config.smtp_from
        msg['To'] = config.admin_email
        with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(config.smtp_user, config.smtp_password)
            smtp.sendmail(config.smtp_from, config.admin_email, msg.as_string())
    except Exception as e:
        logging.error(f'Failed to send error notification: {e}')
