import time
from playwright.sync_api import Page
from storage.models import Product
from typing import Optional

class ProductSearcher:
    def __init__(self, browser_manager):
        self.bm = browser_manager

    def search(self, keyword: str, max_results: int = 10) -> list[Product]:
        """通过关键词搜索 TikTok Shop 商品，返回 Product 列表"""
        products = []
        captured = []

        with self.bm.new_context() as ctx:
            page = ctx.new_page()

            # 拦截商品搜索的 API 响应
            def handle_response(response):
                if "tiktok.com" in response.url and "search" in response.url and response.status == 200:
                    try:
                        data = response.json()
                        captured.append(data)
                    except:
                        pass

            page.on("response", handle_response)

            # 访问 TikTok Shop 搜索页
            page.goto(
                f"https://www.tiktok.com/search?q={keyword}&type=product",
                wait_until="networkidle",
                timeout=30000
            )
            time.sleep(2)

            # 解析捕获的响应
            for data in captured:
                products.extend(self._parse_products(data))
                if len(products) >= max_results:
                    break

        return products[:max_results]

    def get_by_id(self, product_id: str) -> Optional[Product]:
        """直接通过 product_id 获取商品基础信息"""
        captured = []

        with self.bm.new_context() as ctx:
            page = ctx.new_page()

            def handle_response(response):
                if "product" in response.url and response.status == 200:
                    try:
                        captured.append(response.json())
                    except:
                        pass

            page.on("response", handle_response)
            page.goto(
                f"https://www.tiktok.com/shop/product/{product_id}",
                wait_until="networkidle",
                timeout=30000
            )
            time.sleep(2)

        for data in captured:
            products = self._parse_products(data)
            if products:
                return products[0]
        return None

    def _parse_products(self, raw_data: dict) -> list[Product]:
        """
        解析搜索结果，字段名需根据实际抓包结果调整。
        建议先用 Chrome DevTools → Network 过滤 'product' 看真实结构。
        """
        products = []
        # TikTok Shop 搜索结果常见结构，实际字段名以抓包为准
        items = (
            raw_data.get("data", {}).get("products", [])   # 搜索页
            or raw_data.get("data", {}).get("itemList", []) # 备选路径
        )
        for item in items:
            try:
                products.append(Product(
                    product_id = str(item.get("id") or item.get("product_id", "")),
                    name       = item.get("title") or item.get("name", ""),
                    shop_name  = item.get("shop_name") or item.get("shopName", ""),
                    price      = self._parse_price(item),
                ))
            except Exception:
                continue
        return products

    def _parse_price(self, item: dict) -> Optional[float]:
        """价格字段结构比较复杂，单独处理"""
        try:
            price_info = item.get("price") or item.get("priceInfo", {})
            if isinstance(price_info, (int, float)):
                return float(price_info)
            if isinstance(price_info, dict):
                raw = price_info.get("price") or price_info.get("originalPrice", 0)
                return float(raw) / 100  # TikTok 通常以分为单位
        except:
            return None