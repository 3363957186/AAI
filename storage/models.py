from dataclasses import dataclass
from typing import Optional

@dataclass
class Video:
    video_id: str
    author: str
    description: str
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0

@dataclass
class Comment:
    comment_id: str
    video_id: str
    username: str
    text: str
    like_count: int = 0
    reply_count: int = 0
    created_at: Optional[str] = None
    parent_id: Optional[str] = None  # None 表示顶层评论，有值表示是某条评论的回复