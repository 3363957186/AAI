from storage.database import init_db, save_product, save_reviews
from storage.models import Product
from scraper.cookie_manager import get_cookies
from scraper.reviews import ReviewScraper

def run(product_id: str, product_name: str = ""):
    # 1. 初始化数据库
    init_db()

    # 2. 获取 cookies（首次需要手动登录）
    cookies = get_cookies()

    # 3. 保存商品基础信息
    product = Product(
        product_id = product_id,
        name       = product_name or product_id,
        shop_name  = "",
        price      = None,
    )
    save_product(product)

    # 4. 抓取评论
    scraper = ReviewScraper(cookies)
    reviews = scraper.fetch_reviews(product_id, max_count=200)

    # 5. 存入数据库
    save_reviews(product_id, reviews)
    print(f"\n完成！共抓取并存储 {len(reviews)} 条评论")


if __name__ == "__main__":
    # 从商品页 URL 里提取 product_id
    # 例: tiktok.com/shop/pdp/xxx/1732194301461434861
    run(
        product_id   = "1732194301461434861",
        product_name = "Soil and Plant Fertilizer Kit",
    )
