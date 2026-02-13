from dataclasses import dataclass
from typing import Optional

@dataclass
class Product:
    product_id: str
    name: str
    shop_name: str
    price: Optional[float]

@dataclass
class Review:
    review_id: str
    product_id: str
    username: Optional[str]
    rating: Optional[int]
    content: Optional[str]
    helpful_cnt: int = 0
    created_at: Optional[str] = None