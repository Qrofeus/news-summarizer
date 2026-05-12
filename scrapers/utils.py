import time


class RateLimiter:
    def __init__(self, delay: float = 2.5):
        self.delay = delay
        self.last_request: float = 0.0

    def wait(self):
        elapsed = time.time() - self.last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self.last_request = time.time()
