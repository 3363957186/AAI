import json
import os

import httpx
from config import YOUTUBE_API_KEY, MAX_VIDEOS, MAX_COMMENTS_PER_VIDEO
from storage.database import init_db, save_video, save_comments, get_all_comments
from storage.models import Video, Comment
from preprocess import preprocess_comments
from sentiment import analyze_batch
from storage.database import save_sentiment, get_sentiment_summary, get_comments_by_sentiment

VIDEO_URL    = "https://www.googleapis.com/youtube/v3/videos"
SEARCH_URL   = "https://www.googleapis.com/youtube/v3/search"
THREADS_URL  = "https://www.googleapis.com/youtube/v3/commentThreads"
COMMENTS_URL = "https://www.googleapis.com/youtube/v3/comments"
COMMENTS_DIR = "comments"


# ── Video Search ──────────────────────────────────────────────────

def get_video_id_from_url(url: str) -> str:
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    if "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    return url

def _mode_search() -> list[Video]:
    keyword = input("\nEnter product name (English): ").strip()
    if not keyword:
        print("Cannot be empty")
        return []
    return search_videos(keyword, max_results=MAX_VIDEOS)


def _mode_url() -> list[Video]:
    print("\nEnter video URLs (one per line, max 3, empty line to finish):")
    urls = []
    while len(urls) < MAX_VIDEOS:
        line = input(f"  Link {len(urls)+1}: ").strip()
        if not line:
            break
        if "youtube.com" in line or "youtu.be" in line:
            urls.append(line)
        else:
            print("  ⚠️  Invalid YouTube link, please try again")

    if not urls:
        print("No links entered")
        return []

    # Batch fetch video info
    video_ids = [get_video_id_from_url(u) for u in urls]
    resp = httpx.get(VIDEO_URL, params={
        "key":  YOUTUBE_API_KEY,
        "id":   ",".join(video_ids),
        "part": "snippet,statistics",
    })
    resp.raise_for_status()

    videos = []
    for item in resp.json().get("items", []):
        stats   = item.get("statistics", {})
        snippet = item.get("snippet", {})
        videos.append(Video(
            video_id      = item["id"],
            author        = snippet.get("channelTitle", ""),
            description   = snippet.get("title", ""),
            view_count    = int(stats.get("viewCount", 0)),
            like_count    = int(stats.get("likeCount", 0)),
            comment_count = int(stats.get("commentCount", 0)),
        ))

    return videos

def search_videos(keyword: str, max_results: int = 2) -> list[Video]:
    print(f"[VideoSearcher] Searching: '{keyword} review'")

    resp = httpx.get(SEARCH_URL, params={
        "key":               YOUTUBE_API_KEY,
        "q":                 f"{keyword} review",
        "part":              "snippet",
        "type":              "video",
        "maxResults":        max_results,
        "relevanceLanguage": "en",
    })
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        return []

    video_ids = [item["id"]["videoId"] for item in items]

    stats_resp = httpx.get(VIDEO_URL, params={
        "key":  YOUTUBE_API_KEY,
        "id":   ",".join(video_ids),
        "part": "snippet,statistics",
    })
    stats_resp.raise_for_status()

    videos = []
    for item in stats_resp.json().get("items", []):
        stats   = item.get("statistics", {})
        snippet = item.get("snippet", {})
        videos.append(Video(
            video_id      = item["id"],
            author        = snippet.get("channelTitle", ""),
            description   = snippet.get("title", ""),
            view_count    = int(stats.get("viewCount", 0)),
            like_count    = int(stats.get("likeCount", 0)),
            comment_count = int(stats.get("commentCount", 0)),
        ))

    print(f"[VideoSearcher] Found {len(videos)} videos")
    return videos


# ── Comment Fetching ──────────────────────────────────────────────────

def fetch_replies(parent_id: str, video_id: str) -> list[Comment]:
    replies = []
    next_page_token = None

    while True:
        params = {
            "key":        YOUTUBE_API_KEY,
            "parentId":   parent_id,
            "part":       "snippet",
            "maxResults": 100,
        }
        if next_page_token:
            params["pageToken"] = next_page_token

        try:
            resp = httpx.get(COMMENTS_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"    [Reply] Request failed: {e}")
            break

        for item in data.get("items", []):
            s = item["snippet"]
            replies.append(Comment(
                comment_id  = item["id"],
                video_id    = video_id,
                parent_id   = parent_id,
                username    = s.get("authorDisplayName", ""),
                text        = s.get("textOriginal", ""),
                like_count  = s.get("likeCount", 0),
                reply_count = 0,
                created_at  = s.get("publishedAt", ""),
            ))

        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break

    return replies


def fetch_all_comments(video_id: str,max_pages: int = 3) -> list[Comment]:
    all_comments = []
    next_page_token = None
    page = 1

    while page <= max_pages:
        params = {
            "key":        YOUTUBE_API_KEY,
            "videoId":    video_id,
            "part":       "snippet,replies",
            "maxResults": 100,
            "order":      "relevance",
        }
        if next_page_token:
            params["pageToken"] = next_page_token

        try:
            resp = httpx.get(THREADS_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[Page {page}] Request failed: {e}")
            break

        for item in data.get("items", []):
            top        = item["snippet"]["topLevelComment"]["snippet"]
            comment_id = item["snippet"]["topLevelComment"]["id"]
            reply_count = item["snippet"].get("totalReplyCount", 0)

            all_comments.append(Comment(
                comment_id  = comment_id,
                video_id    = video_id,
                parent_id   = None,
                username    = top.get("authorDisplayName", ""),
                text        = top.get("textOriginal", ""),
                like_count  = top.get("likeCount", 0),
                reply_count = reply_count,
                created_at  = top.get("publishedAt", ""),
            ))

            if reply_count > 0:
                embedded = item.get("replies", {}).get("comments", [])
                if reply_count <= len(embedded):
                    for r in embedded:
                        s = r["snippet"]
                        all_comments.append(Comment(
                            comment_id  = r["id"],
                            video_id    = video_id,
                            parent_id   = comment_id,
                            username    = s.get("authorDisplayName", ""),
                            text        = s.get("textOriginal", ""),
                            like_count  = s.get("likeCount", 0),
                            reply_count = 0,
                            created_at  = s.get("publishedAt", ""),
                        ))
                else:
                    print(f"    └─ Fetching {reply_count} replies...")
                    all_comments.extend(fetch_replies(comment_id, video_id))

        top_count         = sum(1 for c in all_comments if c.parent_id is None)
        reply_count_total = sum(1 for c in all_comments if c.parent_id is not None)
        print(f"  Page {page}: Top-level {top_count}, Replies {reply_count_total}")

        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            print("  Reached last page")
            break

        page += 1

    return all_comments


# ── Export TXT ──────────────────────────────────────────────────

def export_to_txt(video: Video, all_stored: list[dict]):
    os.makedirs(COMMENTS_DIR, exist_ok=True)
    filename = os.path.join(COMMENTS_DIR, f"{video.video_id}_comments.txt")
    top_level = [c for c in all_stored if c["parent_id"] is None]
    replies   = [c for c in all_stored if c["parent_id"] is not None]

    with open(filename, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write(f"Video Title: {video.description}\n")
        f.write(f"Channel:     {video.author}\n")
        f.write(f"URL:         https://youtube.com/watch?v={video.video_id}\n")
        f.write(f"Views:       {video.view_count:,}\n")
        f.write(f"Top-level:   {len(top_level)} comments\n")
        f.write(f"Replies:     {len(replies)} comments\n")
        f.write(f"Total:       {len(all_stored)} comments\n")
        f.write("=" * 60 + "\n\n")

        for i, c in enumerate(top_level, 1):
            f.write(f"[{i}] {c['username']}  👍{c['like_count']}  {c['created_at'][:10]}\n")
            f.write(f"{c['text']}\n")

            comment_replies = [r for r in replies if r["parent_id"] == c["comment_id"]]
            for r in comment_replies:
                f.write(f"\n    ↳ {r['username']}  👍{r['like_count']}  {r['created_at'][:10]}\n")
                f.write(f"    {r['text']}\n")

            f.write("\n" + "-" * 60 + "\n\n")

    print(f"  Exported to {filename}")

def export_to_txt_v2(video: Video, all_stored: list[dict], summary: dict):
    os.makedirs(COMMENTS_DIR, exist_ok=True)
    filename = os.path.join(COMMENTS_DIR, f"{video.video_id}_comments_v2.txt")
    top_level = [c for c in all_stored if c["parent_id"] is None]
    replies   = [c for c in all_stored if c["parent_id"] is not None]
    total     = sum(summary.values())

    with open(filename, "w", encoding="utf-8") as f:

        # ── Video Info ──────────────────────────────────────
        f.write("=" * 60 + "\n")
        f.write(f"Video Title: {video.description}\n")
        f.write(f"Channel:     {video.author}\n")
        f.write(f"URL:         https://youtube.com/watch?v={video.video_id}\n")
        f.write(f"Views:       {video.view_count:,}\n")
        f.write(f"Top-level:   {len(top_level)} comments\n")
        f.write(f"Replies:     {len(replies)} comments\n")
        f.write(f"Total:       {len(all_stored)} comments\n")
        f.write("=" * 60 + "\n\n")

        # ── Sentiment Analysis Summary ──────────────────────────────────────
        f.write("【Sentiment Analysis Summary】\n")
        f.write("-" * 60 + "\n")
        if total > 0:
            f.write(f"Positive: {summary['positive']} ({summary['positive']/total*100:.1f}%)\n")
            f.write(f"Negative: {summary['negative']} ({summary['negative']/total*100:.1f}%)\n")
            f.write(f"Neutral:  {summary['neutral']}  ({summary['neutral']/total*100:.1f}%)\n")
        f.write("\n")

        # Top 5 Positive
        positives = sorted(
            [c for c in all_stored if c.get("sentiment_label") == "positive"],
            key=lambda x: x.get("sentiment_score", 0), reverse=True
        )
        f.write("Top 5 Most Positive Comments:\n")
        for i, c in enumerate(positives[:5], 1):
            f.write(f"  {i}. [{c['sentiment_score']:.2f}] {c['clean_text'][:80]}\n")
        f.write("\n")

        # Top 5 Negative
        negatives = sorted(
            [c for c in all_stored if c.get("sentiment_label") == "negative"],
            key=lambda x: x.get("sentiment_score", 0), reverse=True
        )
        f.write("Top 5 Most Negative Comments:\n")
        for i, c in enumerate(negatives[:5], 1):
            f.write(f"  {i}. [{c['sentiment_score']:.2f}] {c['clean_text'][:80]}\n")
        f.write("\n")
        f.write("=" * 60 + "\n\n")

        # ── All Comments (with sentiment labels) ────────────────────────
        f.write("【All Comments】\n\n")
        LABEL_MAP = {"positive": "✅", "negative": "❌", "neutral": "➖"}

        for i, c in enumerate(top_level, 1):
            label = c.get("sentiment_label", "")
            score = c.get("sentiment_score", 0)
            icon  = LABEL_MAP.get(label, "")

            f.write(f"[{i}] {icon} {c['username']}  "
                    f"👍{c['like_count']}  {c['created_at'][:10]}\n")
            f.write(f"Original: {c['text']}\n")

            # Only show sentiment if analyzed
            if label:
                f.write(f"Sentiment: {label} (confidence {score:.2f})\n")

            # Replies
            comment_replies = [r for r in replies
                               if r["parent_id"] == c["comment_id"]]
            for r in comment_replies:
                r_label = r.get("sentiment_label", "")
                r_score = r.get("sentiment_score", 0)
                r_icon  = LABEL_MAP.get(r_label, "")
                f.write(f"\n    ↳ {r_icon} {r['username']}  "
                        f"👍{r['like_count']}  {r['created_at'][:10]}\n")
                f.write(f"    Original: {r['text']}\n")
                if r_label:
                    f.write(f"    Sentiment: {r_label} (confidence {r_score:.2f})\n")

            f.write("\n" + "-" * 60 + "\n\n")

    print(f"  Exported to {filename}")


def export_clean_json(video_id: str, analyzed: list[dict]):
    os.makedirs(COMMENTS_DIR, exist_ok=True)
    filename = os.path.join(COMMENTS_DIR, f"{video_id}_clean.txt")

    # Only keep meaningful fields
    clean_data = [
        {
            "comment_id": c["comment_id"],
            "video_id": c["video_id"],
            "parent_id": c["parent_id"],
            "username": c["username"],
            "clean_text": c["clean_text"],
            "like_count": c["like_count"],
            "reply_count": c["reply_count"],
            "created_at": c["created_at"],
            "sentiment_label": c["sentiment_label"],
            "sentiment_score": c["sentiment_score"],
        }
        for c in analyzed
    ]

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(clean_data, f, indent=2, ensure_ascii=False)

    print(f"  Exported to {filename}")

# ── Main Flow ────────────────────────────────────────────────────

def run():
    init_db()

    # ── Step 1: Select Mode ──────────────────────────────────────
    print("=" * 60)
    print("  YouTube Comment Scraper")
    print("=" * 60)
    print("  1. Search by product name (auto-find review videos)")
    print("  2. Enter video URLs directly")
    print("=" * 60)

    mode = input("Select mode (1/2): ").strip()

    if mode == "1":
        videos = _mode_search()
    elif mode == "2":
        videos = _mode_url()
    else:
        print("Invalid input, please enter 1 or 2")
        return

    if not videos:
        print("No videos found, please check input or API Key")
        return

    # ── Step 2: Confirm Videos ──────────────────────────────────────
    print("\nFound the following videos:")
    print("-" * 60)
    for i, v in enumerate(videos, 1):
        print(f"{i}. {v.description[:55]}")
        print(f"   Channel: {v.author}")
        print(f"   Views {v.view_count:,} | Likes {v.like_count:,} | Comments {v.comment_count:,}")
        print(f"   https://youtube.com/watch?v={v.video_id}")
    print("-" * 60)

    confirm = input(f"\nScrape comments from these {len(videos)} video(s)? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled")
        return

    # Step 3: Fetch comments + analyze + export
    for i, video in enumerate(videos, 1):
        print(f"\n[{i}/{len(videos)}] Fetching video info...")
        print(f"  Title:    {video.description}")
        print(f"  Channel:  {video.author}")
        print(f"  Views:    {video.view_count:,}")
        print(f"  Comments: {video.comment_count:,}")
        save_video(video)

        print(f"\nFetching comments and replies...")
        comments = fetch_all_comments(video.video_id)
        save_comments(comments)

        all_stored = get_all_comments(video.video_id)
        top_level  = [c for c in all_stored if c["parent_id"] is None]
        replies    = [c for c in all_stored if c["parent_id"] is not None]

        print(f"\n{'='*50}")
        print(f"Scraping complete!")
        print(f"  Top-level: {len(top_level)} comments")
        print(f"  Replies:   {len(replies)} comments")
        print(f"  Total:     {len(all_stored)} comments")
        print(f"{'='*50}")

        # Preview first 3 comments
        print("\nFirst 3 comments preview (with replies):")
        count = 0
        for c in all_stored:
            if c["parent_id"] is not None:
                continue
            print(f"\n💬 {c['username']}  👍{c['like_count']}")
            print(f"   {c['text'][:80]}{'...' if len(c['text']) > 80 else ''}")
            comment_replies = [r for r in all_stored if r["parent_id"] == c["comment_id"]]
            for r in comment_replies[:2]:
                print(f"   └─ {r['username']}: {r['text'][:60]}{'...' if len(r['text']) > 60 else ''}")
            if len(comment_replies) > 2:
                print(f"   └─ ... {len(comment_replies) - 2} more replies")
            count += 1
            if count >= 3:
                break

        print("\nExporting txt file...")
        export_to_txt(video, all_stored)

        all_stored = get_all_comments(video.video_id)

        cleaned = preprocess_comments(all_stored)
        analyzed = analyze_batch(cleaned)
        save_sentiment(analyzed)

        # Summary output
        summary = get_sentiment_summary(video.video_id)
        all_stored = get_all_comments(video.video_id)
        export_to_txt_v2(video, all_stored, summary)
        export_clean_json(video.video_id, analyzed)
        total = sum(summary.values())
        print(f"\nSentiment Analysis Results:")
        print(f"  Positive: {summary['positive']} ({summary['positive'] / total * 100:.1f}%)")
        print(f"  Negative: {summary['negative']} ({summary['negative'] / total * 100:.1f}%)")
        print(f"  Neutral:  {summary['neutral']}  ({summary['neutral'] / total * 100:.1f}%)")

        # Print top 3 most positive / negative
        positives = get_comments_by_sentiment(video.video_id, "positive")
        negatives = get_comments_by_sentiment(video.video_id, "negative")

        print("\nTop 3 Most Positive Comments:")
        for r in positives[:3]:
            print(f"  [{r['sentiment_score']:.2f}] {r['clean_text'][:70]}")

        print("\nTop 3 Most Negative Comments:")
        for r in negatives[:3]:
            print(f"  [{r['sentiment_score']:.2f}] {r['clean_text'][:70]}")

if __name__ == "__main__":
    run()