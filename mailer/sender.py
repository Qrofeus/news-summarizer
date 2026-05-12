import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import Config


def send_digest(html: str, config: Config) -> dict:
    now = datetime.now(timezone.utc)
    subject = f"Daily News Digest — {now.strftime('%B')} {now.day}, {now.year}"

    sent, failed = 0, []
    with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(config.smtp_user, config.smtp_password)
        for recipient in config.recipients:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = config.smtp_from
            msg['To'] = recipient
            msg.attach(MIMEText(html, 'html'))
            try:
                smtp.sendmail(config.smtp_from, recipient, msg.as_string())
                sent += 1
            except Exception:
                failed.append(recipient)

    return {'success': len(failed) == 0, 'sent': sent, 'failed': len(failed)}
