import logging
import sys


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)-8s %(name)s — %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%SZ',
        stream=sys.stdout,
        force=True,
    )
