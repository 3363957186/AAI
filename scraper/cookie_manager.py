import json
import os
from playwright.sync_api import sync_playwright

COOKIE_FILE = "cookies.json"


def get_cookies(force_refresh: bool = False) -> dict:
    """
    优先读取本地缓存的 cookies。
    如果不存在或强制刷新，打开浏览器让用户手动登录一次后保存。
    """
    if not force_refresh and os.path.exists(COOKIE_FILE):
        print("[CookieManager] 从本地加载 cookies")
        with open(COOKIE_FILE) as f:
            cookie_list = json.load(f)
        return {c["name"]: c["value"] for c in cookie_list}

    print("[CookieManager] 未找到 cookies，打开浏览器请手动登录 TikTok...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # 必须有头，让用户能操作
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://www.tiktok.com/login", wait_until="networkidle")

        # 等待用户手动完成登录（检测到跳转到首页为止）
        print("[CookieManager] 请在浏览器中完成登录，登录成功后会自动继续...")
        page.wait_for_url("https://www.tiktok.com/", timeout=120000)

        # 保存 cookies
        cookie_list = context.cookies()
        with open(COOKIE_FILE, "w") as f:
            json.dump(cookie_list, f, indent=2)
        print(f"[CookieManager] Cookies 已保存到 {COOKIE_FILE}")

        browser.close()

    return {c["name"]: c["value"] for c in cookie_list}