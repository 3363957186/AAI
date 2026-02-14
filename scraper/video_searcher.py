import httpx
from config import YOUTUBE_API_KEY
from storage.models import Video

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEO_URL  = "https://www.googleapis.com/youtube/v3/videos"

class VideoSearcher:
    def search(self, keyword: str, max_results: int = 2) -> list[Video]:
        print(f"[VideoSearcher] 搜索: '{keyword} review'")

        # 第一步：搜索视频，拿到 video_id 列表
        resp = httpx.get(SEARCH_URL, params={
            "key":        YOUTUBE_API_KEY,
            "q":          f"{keyword} review",
            "part":       "snippet",
            "type":       "video",
            "maxResults": max_results,
            "relevanceLanguage": "en",
        })
        resp.raise_for_status()
        items = resp.json().get("items", [])

        if not items:
            print("[VideoSearcher] 未找到视频")
            return []

        video_ids = [item["id"]["videoId"] for item in items]

        # 第二步：拿播放量/点赞/评论数等统计数据
        stats_resp = httpx.get(VIDEO_URL, params={
            "key":  YOUTUBE_API_KEY,
            "id":   ",".join(video_ids),
            "part": "snippet,statistics",
        })
        stats_resp.raise_for_status()
        stats_items = stats_resp.json().get("items", [])

        videos = []
        for item in stats_items:
            stats = item.get("statistics", {})
            snippet = item.get("snippet", {})
            videos.append(Video(
                video_id      = item["id"],
                author        = snippet.get("channelTitle", ""),
                description   = snippet.get("title", ""),
                view_count    = int(stats.get("viewCount", 0)),
                like_count    = int(stats.get("likeCount", 0)),
                comment_count = int(stats.get("commentCount", 0)),
            ))

        print(f"[VideoSearcher] 找到 {len(videos)} 个视频")
        return videos