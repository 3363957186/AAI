from apscheduler.schedulers.background import BackgroundScheduler
from scraper.browser import BrowserManager
from scraper.reviews import ReviewScraper
from storage.database import save_reviews
from config import FETCH_INTERVAL_MINUTES, HEADLESS

# 监控中的商品列表（可以持久化到 DB）
WATCHED_PRODUCTS = []

def scrape_job(product_id: str):
    print(f"[Scheduler] 开始抓取 product_id={product_id}")
    with BrowserManager(headless=HEADLESS) as bm:
        scraper = ReviewScraper(bm)
        reviews = scraper.fetch_reviews(product_id)
        save_reviews(product_id, reviews)
    print(f"[Scheduler] 完成，共抓取 {len(reviews)} 条评论")

def start_scheduler():
    scheduler = BackgroundScheduler()
    for product_id in WATCHED_PRODUCTS:
        scheduler.add_job(
            scrape_job,
            "interval",
            minutes=FETCH_INTERVAL_MINUTES,
            args=[product_id],
            id=f"scrape_{product_id}"
        )
    scheduler.start()
    return scheduler