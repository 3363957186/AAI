import json
import os

COOKIE_FILE = "cookies.json"
TIKTOK_DOMAINS = ["tiktok.com"]


def get_cookies(force_refresh: bool = False) -> dict:
    """
    优先读取本地缓存。
    没有缓存时直接从 Safari 读取已登录的 cookies，无需重新登录。
    """
    if not force_refresh and os.path.exists(COOKIE_FILE):
        print("[CookieManager] 从本地缓存加载 cookies")
        with open(COOKIE_FILE) as f:
            return json.load(f)

    print("[CookieManager] 正在从 Safari 读取 TikTok cookies...")
    cookies = _read_from_safari()

    # 缓存到本地，下次直接复用
    with open(COOKIE_FILE, "w") as f:
        json.dump(cookies, f, indent=2)
    print(f"[CookieManager] 已读取 {len(cookies)} 个 cookies 并缓存到 {COOKIE_FILE}")

    return cookies


def _read_from_safari() -> dict:
    # 优先用 rookiepy
    try:
        import rookiepy
        raw = rookiepy.safari(TIKTOK_DOMAINS)
        cookies = {c["name"]: c["value"] for c in raw}
        if not cookies:
            raise ValueError("读取到 0 个 cookies，请确认 Safari 中已登录 TikTok")
        return cookies
    except ImportError:
        pass  # 没安装，走下面的备用方案

    # 备用：browser_cookie3
    try:
        import browser_cookie3
        jar = browser_cookie3.safari(domain_name="tiktok.com")
        cookies = {c.name: c.value for c in jar}
        if not cookies:
            raise ValueError("读取到 0 个 cookies，请确认 Safari 中已登录 TikTok")
        return cookies
    except ImportError:
        pass

    raise RuntimeError(
        "请安装依赖：pip install rookiepy\n"
        "或者：pip install browser-cookie3"
    )


def clear_cache():
    """cookies 失效时调用这个清除缓存，下次重新从 Safari 读取"""
    if os.path.exists(COOKIE_FILE):
        os.remove(COOKIE_FILE)
        print(f"[CookieManager] 已清除缓存 {COOKIE_FILE}")