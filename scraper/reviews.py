import httpx
import time
from datetime import datetime
from storage.models import Review


REVIEW_API_URL = "https://www.tiktok.com/api/shop/pdp_desktop/get_product_reviews?"

# 基础 Headers，从你的抓包直接复制
BASE_HEADERS = {
    "accept":           "application/json,*/*;q=0.8",
    "accept-language":  "en-US,en;q=0.9",
    "content-type":     "application/json",
    "origin":           "https://www.tiktok.com",
    "sec-fetch-dest":   "empty",
    "sec-fetch-mode":   "cors",
    "sec-fetch-site":   "same-origin",
    "user-agent":       "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/145.0.0.0 Safari/537.36",
}


class ReviewScraper:
    def __init__(self, cookies: dict):
        """
        cookies: 通过 CookieManager 从 Playwright 获取的登录态 cookies
        """
        self.cookies = cookies

    def fetch_reviews(self, product_id: str, max_count: int = 200) -> list[Review]:
        """分页拉取指定商品的所有评论"""
        reviews = []
        page_start = 1
        page_size = 10

        with httpx.Client(headers=BASE_HEADERS, cookies=self.cookies, timeout=15) as client:
            while len(reviews) < max_count:
                payload = {
                    "product_id":     product_id,
                    "page_start":     page_start,
                    "page_size":      page_size,
                    "sort_rule":      1,
                    "component_name": "pdp_left_reviews",
                    "review_filter":  {"filter_type": 1, "filter_value": 6},
                }

                try:
                    resp = client.post(REVIEW_API_URL, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    print(f"[ReviewScraper] 请求失败 page={page_start}: {e}")
                    break

                if data.get("code") != 0:
                    print(f"[ReviewScraper] API 返回错误: {data.get('message')}")
                    break

                batch = self._parse_reviews(product_id, data)
                if not batch:
                    print(f"[ReviewScraper] 第 {page_start} 页无数据，停止")
                    break

                reviews.extend(batch)
                print(f"[ReviewScraper] 已抓取 {len(reviews)} 条评论")

                # 检查是否还有更多页
                if not data.get("data", {}).get("has_more", False):
                    print("[ReviewScraper] 已到最后一页")
                    break

                page_start += 1
                time.sleep(1.5)  # 避免触发限速

        return reviews[:max_count]

    def _parse_reviews(self, product_id: str, raw_data: dict) -> list[Review]:
        reviews = []
        items = raw_data.get("data", {}).get("product_reviews", [])

        for item in items:
            reviews.append(Review(
                review_id   = str(item.get("review_id", "")),
                product_id  = product_id,
                username    = item.get("reviewer_name"),
                rating      = item.get("review_rating"),
                content     = item.get("review_text"),
                helpful_cnt = item.get("helpful_count", 0),
                created_at  = self._parse_timestamp(item.get("review_time")),
            ))
        return reviews

    @staticmethod
    def _parse_timestamp(ts) -> str | None:
        try:
            return datetime.fromtimestamp(int(ts) / 1000).isoformat()
        except:
            return None