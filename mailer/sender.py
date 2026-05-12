import requests

from config import Config


def send_digest(html: str, config: Config) -> dict:
    response = requests.post(
        config.php_handler_url,
        data={'html_content': html},
        headers={'X-Digest-Token': config.php_handler_token},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()
