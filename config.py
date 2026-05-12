from dataclasses import dataclass
from dotenv import load_dotenv
import os

load_dotenv()


@dataclass
class Config:
    gemini_api_key: str
    guardian_api_key: str
    mysql_host: str
    mysql_user: str
    mysql_password: str
    mysql_database: str
    php_handler_url: str
    php_handler_token: str
    admin_email: str
    user_agent: str
    request_delay: float
    enable_llm: bool
    enable_fallback: bool
    dry_run: bool

    @classmethod
    def from_env(cls):
        return cls(
            gemini_api_key=os.getenv('GEMINI_API_KEY'),
            guardian_api_key=os.getenv('GUARDIAN_API_KEY', 'test'),
            mysql_host=os.getenv('MYSQL_HOST'),
            mysql_user=os.getenv('MYSQL_USER'),
            mysql_password=os.getenv('MYSQL_PASSWORD'),
            mysql_database=os.getenv('MYSQL_DATABASE'),
            php_handler_url=os.getenv('PHP_HANDLER_URL'),
            php_handler_token=os.getenv('PHP_HANDLER_TOKEN'),
            admin_email=os.getenv('ADMIN_EMAIL'),
            user_agent=os.getenv('USER_AGENT', 'NewsDigest/1.0'),
            request_delay=float(os.getenv('REQUEST_DELAY', 2.5)),
            enable_llm=os.getenv('ENABLE_LLM', 'true').lower() == 'true',
            enable_fallback=os.getenv('ENABLE_FALLBACK', 'true').lower() == 'true',
            dry_run=os.getenv('DRY_RUN', 'false').lower() == 'true',
        )
