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
                comment_id      TEXT PRIMARY KEY,
                video_id        TEXT,
                parent_id       TEXT,
                username        TEXT,
                text            TEXT,
                like_count      INTEGER DEFAULT 0,
                reply_count     INTEGER DEFAULT 0,
                created_at      TIMESTAMP,
                fetched_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                clean_text      TEXT,               -- preprocess 后的文本
                sentiment_label TEXT,               -- positive/negative/neutral
                sentiment_score REAL,               -- 置信度 0-1
                FOREIGN KEY (video_id) REFERENCES videos(video_id)
            );
        """)

        # 自动迁移：旧表补列
        existing = [
            row[1] for row in
            conn.execute("PRAGMA table_info(comments)").fetchall()
        ]
        for col, col_type in [
            ("parent_id",       "TEXT"),
            ("clean_text",      "TEXT"),
            ("sentiment_label", "TEXT"),
            ("sentiment_score", "REAL"),
        ]:
            if col not in existing:
                conn.execute(f"ALTER TABLE comments ADD COLUMN {col} {col_type}")
                print(f"[DB] 已自动添加 {col} 列")

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

def save_sentiment(results: list[dict]):
    """将 clean_text + sentiment_label + sentiment_score 写回 comments 表"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany("""
            UPDATE comments
            SET clean_text      = ?,
                sentiment_label = ?,
                sentiment_score = ?
            WHERE comment_id = ?
        """, [(r["clean_text"], r["sentiment_label"],
               r["sentiment_score"], r["comment_id"]) for r in results])

def get_sentiment_summary(video_id: str) -> dict:
    """返回这个视频的情感统计"""
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("""
            SELECT sentiment_label, COUNT(*) as cnt
            FROM comments
            WHERE video_id = ? AND sentiment_label IS NOT NULL
            GROUP BY sentiment_label
        """, (video_id,)).fetchall()

    summary = {"positive": 0, "negative": 0, "neutral": 0}
    for label, cnt in rows:
        summary[label] = cnt
    return summary


def get_comments_by_sentiment(video_id: str, label: str) -> list[dict]:
    """按情感标签查询评论，按置信度排序"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT * FROM comments
            WHERE video_id = ? AND sentiment_label = ?
            ORDER BY sentiment_score DESC
        """, (video_id, label)).fetchall()
    return [dict(r) for r in rows]

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