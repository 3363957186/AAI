import sqlite3
from typing import Optional
from config import DB_PATH
from storage.models import Product, Review

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            product_id  TEXT PRIMARY KEY,
            name        TEXT,
            shop_name   TEXT,
            price       REAL,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS reviews (
            review_id   TEXT PRIMARY KEY,
            product_id  TEXT,
            username    TEXT,
            rating      INTEGER,
            content     TEXT,
            helpful_cnt INTEGER DEFAULT 0,
            created_at  TIMESTAMP,
            fetched_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );
    """)
    conn.commit()
    conn.close()

def save_product(product: Product):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO products (product_id, name, shop_name, price)
            VALUES (?, ?, ?, ?)
        """, (product.product_id, product.name, product.shop_name, product.price))

def save_reviews(product_id: str, reviews: list[Review]):
    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany("""
            INSERT OR IGNORE INTO reviews
                (review_id, product_id, username, rating, content, helpful_cnt, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            (r.review_id, product_id, r.username, r.rating,
             r.content, r.helpful_cnt, r.created_at)
            for r in reviews
        ])

def get_reviews(product_id: str, limit: int = 50, offset: int = 0) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT * FROM reviews
            WHERE product_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (product_id, limit, offset)).fetchall()
    return [dict(r) for r in rows]

def search_products(keyword: str) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT * FROM products WHERE name LIKE ?
        """, (f"%{keyword}%",)).fetchall()
    return [dict(r) for r in rows]