from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv
import os

load_dotenv()


@dataclass
class Config:
    gemini_api_key: str
    guardian_api_key: str
    worldnews_api_key: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_from: str
    recipients: List[str]
    admin_email: str
    user_agent: str
    request_delay: float
    enable_llm: bool
    enable_fallback: bool

    @classmethod
    def from_env(cls):
        recipients_raw = os.getenv('RECIPIENTS', '')
        recipients = [r.strip() for r in recipients_raw.split(',') if r.strip()]
        smtp_user = os.getenv('SMTP_USER')
        return cls(
            gemini_api_key=os.getenv('GEMINI_API_KEY'),
            guardian_api_key=os.getenv('GUARDIAN_API_KEY', 'test'),
            worldnews_api_key=os.getenv('WORLDNEWS_API_KEY', 'test'),
            smtp_host=os.getenv('SMTP_HOST'),
            smtp_port=int(os.getenv('SMTP_PORT', '587')),
            smtp_user=smtp_user,
            smtp_password=os.getenv('SMTP_PASSWORD'),
            smtp_from=os.getenv('SMTP_FROM') or smtp_user,
            recipients=recipients,
            admin_email=os.getenv('ADMIN_EMAIL'),
            user_agent=os.getenv('USER_AGENT', 'NewsDigest/1.0'),
            request_delay=float(os.getenv('REQUEST_DELAY', 2.5)),
            enable_llm=os.getenv('ENABLE_LLM', 'true').lower() == 'true',
            enable_fallback=os.getenv('ENABLE_FALLBACK', 'true').lower() == 'true',
        )
