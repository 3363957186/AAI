import httpx
from datetime import datetime
from config import YOUTUBE_API_KEY
from storage.models import Comment

COMMENTS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"

class CommentScraper:
    def fetch_comments(self, video_id: str, max_count: int = 100) -> list[Comment]:
        print(f"[CommentScraper] 抓取视频 {video_id} 的评论")
        comments = []
        next_page_token = None

        while len(comments) < max_count:
            params = {
                "key":        YOUTUBE_API_KEY,
                "videoId":    video_id,
                "part":       "snippet",
                "maxResults": min(100, max_count - len(comments)),
                "order":      "relevance",  # 或 "time" 按时间排序
            }
            if next_page_token:
                params["pageToken"] = next_page_token

            try:
                resp = httpx.get(COMMENTS_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                print(f"[CommentScraper] 请求失败: {e}")
                break

            for item in data.get("items", []):
                top = item["snippet"]["topLevelComment"]["snippet"]
                comments.append(Comment(
                    comment_id  = item["id"],
                    video_id    = video_id,
                    username    = top.get("authorDisplayName", ""),
                    text        = top.get("textOriginal", ""),
                    like_count  = top.get("likeCount", 0),
                    reply_count = item["snippet"].get("totalReplyCount", 0),
                    created_at  = top.get("publishedAt", ""),
                ))

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                print("[CommentScraper] 已到最后一页")
                break

        print(f"[CommentScraper] 共抓取 {len(comments)} 条评论")
        return comments