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


# ── 视频搜索 ──────────────────────────────────────────────────

def get_video_id_from_url(url: str) -> str:
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    if "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    return url

def _mode_search() -> list[Video]:
    keyword = input("\n请输入商品名称（英文）: ").strip()
    if not keyword:
        print("不能为空")
        return []
    return search_videos(keyword, max_results=MAX_VIDEOS)


def _mode_url() -> list[Video]:
    print("\n请输入视频链接（每行一个，最多 3 个，输入空行结束）:")
    urls = []
    while len(urls) < MAX_VIDEOS:
        line = input(f"  链接 {len(urls)+1}: ").strip()
        if not line:
            break
        if "youtube.com" in line or "youtu.be" in line:
            urls.append(line)
        else:
            print("  ⚠️  无效的 YouTube 链接，请重新输入")

    if not urls:
        print("未输入任何链接")
        return []

    # 批量获取视频信息
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
    print(f"[VideoSearcher] 搜索: '{keyword} review'")

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

    print(f"[VideoSearcher] 找到 {len(videos)} 个视频")
    return videos


# ── 评论抓取 ──────────────────────────────────────────────────

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
            print(f"    [回复] 请求失败: {e}")
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


def fetch_all_comments(video_id: str) -> list[Comment]:
    all_comments = []
    next_page_token = None
    page = 1

    while True:
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
            print(f"[第 {page} 页] 请求失败: {e}")
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
                    print(f"    └─ 获取 {reply_count} 条回复...")
                    all_comments.extend(fetch_replies(comment_id, video_id))

        top_count         = sum(1 for c in all_comments if c.parent_id is None)
        reply_count_total = sum(1 for c in all_comments if c.parent_id is not None)
        print(f"  第 {page} 页: 顶层 {top_count} 条，回复 {reply_count_total} 条")

        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            print("  已到最后一页")
            break

        page += 1

    return all_comments


# ── 导出 txt ──────────────────────────────────────────────────

def export_to_txt(video: Video, all_stored: list[dict]):
    os.makedirs(COMMENTS_DIR, exist_ok=True)
    filename = os.path.join(COMMENTS_DIR, f"{video.video_id}_comments.txt")
    top_level = [c for c in all_stored if c["parent_id"] is None]
    replies   = [c for c in all_stored if c["parent_id"] is not None]

    with open(filename, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write(f"视频标题：{video.description}\n")
        f.write(f"频道：    {video.author}\n")
        f.write(f"链接：    https://youtube.com/watch?v={video.video_id}\n")
        f.write(f"播放：    {video.view_count:,}\n")
        f.write(f"顶层评论：{len(top_level)} 条\n")
        f.write(f"回复：    {len(replies)} 条\n")
        f.write(f"总计：    {len(all_stored)} 条\n")
        f.write("=" * 60 + "\n\n")

        for i, c in enumerate(top_level, 1):
            f.write(f"[{i}] {c['username']}  👍{c['like_count']}  {c['created_at'][:10]}\n")
            f.write(f"{c['text']}\n")

            comment_replies = [r for r in replies if r["parent_id"] == c["comment_id"]]
            for r in comment_replies:
                f.write(f"\n    ↳ {r['username']}  👍{r['like_count']}  {r['created_at'][:10]}\n")
                f.write(f"    {r['text']}\n")

            f.write("\n" + "-" * 60 + "\n\n")

    print(f"  已导出到 {filename}")

def export_to_txt_v2(video: Video, all_stored: list[dict], summary: dict):
    os.makedirs(COMMENTS_DIR, exist_ok=True)
    filename = os.path.join(COMMENTS_DIR, f"{video.video_id}_comments_v2.txt")
    top_level = [c for c in all_stored if c["parent_id"] is None]
    replies   = [c for c in all_stored if c["parent_id"] is not None]
    total     = sum(summary.values())

    with open(filename, "w", encoding="utf-8") as f:

        # ── 视频基本信息 ──────────────────────────────────────
        f.write("=" * 60 + "\n")
        f.write(f"视频标题：{video.description}\n")
        f.write(f"频道：    {video.author}\n")
        f.write(f"链接：    https://youtube.com/watch?v={video.video_id}\n")
        f.write(f"播放：    {video.view_count:,}\n")
        f.write(f"顶层评论：{len(top_level)} 条\n")
        f.write(f"回复：    {len(replies)} 条\n")
        f.write(f"总计：    {len(all_stored)} 条\n")
        f.write("=" * 60 + "\n\n")

        # ── 情感分析汇总 ──────────────────────────────────────
        f.write("【情感分析汇总】\n")
        f.write("-" * 60 + "\n")
        if total > 0:
            f.write(f"正面 (Positive): {summary['positive']} 条 "
                    f"({summary['positive']/total*100:.1f}%)\n")
            f.write(f"负面 (Negative): {summary['negative']} 条 "
                    f"({summary['negative']/total*100:.1f}%)\n")
            f.write(f"中性 (Neutral):  {summary['neutral']}  条 "
                    f"({summary['neutral']/total*100:.1f}%)\n")
        f.write("\n")

        # 最正面 Top 5
        positives = sorted(
            [c for c in all_stored if c.get("sentiment_label") == "positive"],
            key=lambda x: x.get("sentiment_score", 0), reverse=True
        )
        f.write("Top 5 最正面评论：\n")
        for i, c in enumerate(positives[:5], 1):
            f.write(f"  {i}. [{c['sentiment_score']:.2f}] {c['clean_text'][:80]}\n")
        f.write("\n")

        # 最负面 Top 5
        negatives = sorted(
            [c for c in all_stored if c.get("sentiment_label") == "negative"],
            key=lambda x: x.get("sentiment_score", 0), reverse=True
        )
        f.write("Top 5 最负面评论：\n")
        for i, c in enumerate(negatives[:5], 1):
            f.write(f"  {i}. [{c['sentiment_score']:.2f}] {c['clean_text'][:80]}\n")
        f.write("\n")
        f.write("=" * 60 + "\n\n")

        # ── 所有评论正文（带情感标签）────────────────────────
        f.write("【所有评论】\n\n")
        LABEL_MAP = {"positive": "✅", "negative": "❌", "neutral": "➖"}

        for i, c in enumerate(top_level, 1):
            label = c.get("sentiment_label", "")
            score = c.get("sentiment_score", 0)
            icon  = LABEL_MAP.get(label, "")

            f.write(f"[{i}] {icon} {c['username']}  "
                    f"👍{c['like_count']}  {c['created_at'][:10]}\n")
            f.write(f"原文：{c['text']}\n")

            # 只有做过情感分析的才显示
            if label:
                f.write(f"情感：{label} (置信度 {score:.2f})\n")

            # 回复
            comment_replies = [r for r in replies
                               if r["parent_id"] == c["comment_id"]]
            for r in comment_replies:
                r_label = r.get("sentiment_label", "")
                r_score = r.get("sentiment_score", 0)
                r_icon  = LABEL_MAP.get(r_label, "")
                f.write(f"\n    ↳ {r_icon} {r['username']}  "
                        f"👍{r['like_count']}  {r['created_at'][:10]}\n")
                f.write(f"    原文：{r['text']}\n")
                if r_label:
                    f.write(f"    情感：{r_label} (置信度 {r_score:.2f})\n")

            f.write("\n" + "-" * 60 + "\n\n")

    print(f"  已导出到 {filename}")


def export_clean_json(video_id: str, analyzed: list[dict]):
    os.makedirs(COMMENTS_DIR, exist_ok=True)
    filename = os.path.join(COMMENTS_DIR, f"{video_id}_clean.txt")

    # 只保留有意义的字段，去掉数据库内部字段
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

    print(f"  已导出到 {filename}")

# ── 主流程 ────────────────────────────────────────────────────

def run():
    init_db()

    # ── 第一步：选择模式 ──────────────────────────────────────
    print("=" * 60)
    print("  YouTube 评论抓取工具")
    print("=" * 60)
    print("  1. 搜索商品名称（自动找相关视频）")
    print("  2. 直接输入视频链接")
    print("=" * 60)

    mode = input("请选择模式 (1/2): ").strip()

    if mode == "1":
        videos = _mode_search()
    elif mode == "2":
        videos = _mode_url()
    else:
        print("无效输入，请输入 1 或 2")
        return

    if not videos:
        print("未找到视频，请检查输入或 API Key")
        return

    # ── 第二步：确认视频 ──────────────────────────────────────
    print("\n找到以下视频：")
    print("-" * 60)
    for i, v in enumerate(videos, 1):
        print(f"{i}. {v.description[:55]}")
        print(f"   频道: {v.author}")
        print(f"   播放 {v.view_count:,} | 点赞 {v.like_count:,} | 评论 {v.comment_count:,}")
        print(f"   https://youtube.com/watch?v={v.video_id}")
    print("-" * 60)

    confirm = input(f"\n是否抓取以上 {len(videos)} 个视频的评论？(y/n): ").strip().lower()
    if confirm != "y":
        print("已取消")
        return

    # 3. 对每个视频抓取评论 + 回复 + 导出
    for i, video in enumerate(videos, 1):
        print(f"\n[{i}/{len(videos)}] 获取视频信息...")
        print(f"  标题:   {video.description}")
        print(f"  频道:   {video.author}")
        print(f"  播放:   {video.view_count:,}")
        print(f"  评论数: {video.comment_count:,}")
        save_video(video)

        print(f"\n开始抓取评论和回复...")
        comments = fetch_all_comments(video.video_id)
        save_comments(comments)

        all_stored = get_all_comments(video.video_id)
        top_level  = [c for c in all_stored if c["parent_id"] is None]
        replies    = [c for c in all_stored if c["parent_id"] is not None]

        print(f"\n{'='*50}")
        print(f"抓取完成！")
        print(f"  顶层评论: {len(top_level)} 条")
        print(f"  回复:     {len(replies)} 条")
        print(f"  总计:     {len(all_stored)} 条")
        print(f"{'='*50}")

        # 前 3 条预览
        print("\n前 3 条评论预览（含回复）：")
        count = 0
        for c in all_stored:
            if c["parent_id"] is not None:
                continue
            print(f"\n💬 @{c['username']}  👍{c['like_count']}")
            print(f"   {c['text'][:80]}{'...' if len(c['text']) > 80 else ''}")
            comment_replies = [r for r in all_stored if r["parent_id"] == c["comment_id"]]
            for r in comment_replies[:2]:
                print(f"   └─ @{r['username']}: {r['text'][:60]}{'...' if len(r['text']) > 60 else ''}")
            if len(comment_replies) > 2:
                print(f"   └─ ... 还有 {len(comment_replies) - 2} 条回复")
            count += 1
            if count >= 3:
                break

        print("\n正在导出 txt 文件...")
        export_to_txt(video, all_stored)

        all_stored = get_all_comments(video.video_id)

        cleaned = preprocess_comments(all_stored)
        analyzed = analyze_batch(cleaned)
        save_sentiment(analyzed)

        # 汇总输出
        summary = get_sentiment_summary(video.video_id)
        all_stored = get_all_comments(video.video_id)
        export_to_txt_v2(video, all_stored, summary)
        export_clean_json(video.video_id, analyzed)
        total = sum(summary.values())
        print(f"\n情感分析结果：")
        print(f"  正面: {summary['positive']} 条 ({summary['positive'] / total * 100:.1f}%)")
        print(f"  负面: {summary['negative']} 条 ({summary['negative'] / total * 100:.1f}%)")
        print(f"  中性: {summary['neutral']}  条 ({summary['neutral'] / total * 100:.1f}%)")

        # 打印最正面 / 最负面各 3 条
        positives = get_comments_by_sentiment(video.video_id, "positive")
        negatives = get_comments_by_sentiment(video.video_id, "negative")

        print("\n最正面的 3 条评论：")
        for r in positives[:3]:
            print(f"  [{r['sentiment_score']:.2f}] {r['clean_text'][:70]}")

        print("\n最负面的 3 条评论：")
        for r in negatives[:3]:
            print(f"  [{r['sentiment_score']:.2f}] {r['clean_text'][:70]}")

if __name__ == "__main__":
    run()