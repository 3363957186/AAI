from playwright.sync_api import sync_playwright

class BrowserManager:
    def __init__(self, headless=True):
        self.headless = headless
        self._playwright = None
        self._browser = None

    def __enter__(self):
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        return self

    def new_context(self):
        # 伪装成普通用户，绕过基础反爬
        return self._browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="America/New_York",
        )

    def __exit__(self, *args):
        self._browser.close()
        self._playwright.stop()