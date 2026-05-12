import logging

import requests

from config import Config


def send_error_email(error: str, traceback_str: str, config: Config) -> None:
    body = f'Error: {error}\n\nTraceback:\n{traceback_str}'
    try:
        requests.post(
            config.php_handler_url,
            data={'error_report': body},
            headers={'X-Digest-Token': config.php_handler_token},
            timeout=15,
        )
    except Exception as e:
        logging.error(f'Failed to send error notification: {e}')
