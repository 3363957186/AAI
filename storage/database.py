import sqlite3
from config import DB_PATH
from storage.models import Video, Comment

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS videos (
                video_id      TEXT PRIMARY KEY,
                author        TEXT,
                description   TEXT,
                view_count    INTEGER DEFAULT 0,
                like_count    INTEGER DEFAULT 0,
                comment_count INTEGER DEFAULT 0,
                fetched_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS comments (
                comment_id  TEXT PRIMARY KEY,
                video_id    TEXT,
                parent_id   TEXT,
                username    TEXT,
                text        TEXT,
                like_count  INTEGER DEFAULT 0,
                reply_count INTEGER DEFAULT 0,
                created_at  TIMESTAMP,
                fetched_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (video_id) REFERENCES videos(video_id)
            );
        """)

        # 自动迁移：如果旧表缺少 parent_id 列就补上
        existing = [
            row[1] for row in
            conn.execute("PRAGMA table_info(comments)").fetchall()
        ]
        if "parent_id" not in existing:
            conn.execute("ALTER TABLE comments ADD COLUMN parent_id TEXT")
            print("[DB] 已自动添加 parent_id 列")

def save_video(video: Video):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO videos
                (video_id, author, description, view_count, like_count, comment_count)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (video.video_id, video.author, video.description,
              video.view_count, video.like_count, video.comment_count))

def save_comments(comments: list[Comment]):
    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany("""
            INSERT OR IGNORE INTO comments
                (comment_id, video_id, parent_id, username, text,
                 like_count, reply_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [(c.comment_id, c.video_id, c.parent_id, c.username, c.text,
               c.like_count, c.reply_count, c.created_at) for c in comments])

def get_comments(video_id: str) -> list[dict]:
    """只返回顶层评论"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT * FROM comments
            WHERE video_id = ? AND parent_id IS NULL
            ORDER BY like_count DESC
        """, (video_id,)).fetchall()
    return [dict(r) for r in rows]

def get_replies(parent_id: str) -> list[dict]:
    """返回某条评论下的所有回复"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT * FROM comments
            WHERE parent_id = ?
            ORDER BY created_at ASC
        """, (parent_id,)).fetchall()
    return [dict(r) for r in rows]

def get_all_comments(video_id: str) -> list[dict]:
    """返回所有评论（含回复），按层级排列"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT * FROM comments
            WHERE video_id = ?
            ORDER BY 
                COALESCE(parent_id, comment_id),  -- 把回复归到对应的顶层评论旁边
                parent_id IS NOT NULL,             -- 顶层评论在前
                created_at ASC
        """, (video_id,)).fetchall()
    return [dict(r) for r in rows]