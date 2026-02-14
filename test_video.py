import httpx
from storage.database import init_db, save_video, save_comments, get_all_comments
from storage.models import Video, Comment
from config import YOUTUBE_API_KEY

VIDEO_URL    = "https://www.googleapis.com/youtube/v3/videos"
THREADS_URL  = "https://www.googleapis.com/youtube/v3/commentThreads"
COMMENTS_URL = "https://www.googleapis.com/youtube/v3/comments"


def get_video_id_from_url(url: str) -> str:
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    if "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    return url


def fetch_video_info(video_id: str) -> Video:
    resp = httpx.get(VIDEO_URL, params={
        "key":  YOUTUBE_API_KEY,
        "id":   video_id,
        "part": "snippet,statistics",
    })
    resp.raise_for_status()
    item    = resp.json()["items"][0]
    stats   = item.get("statistics", {})
    snippet = item.get("snippet", {})
    return Video(
        video_id      = video_id,
        author        = snippet.get("channelTitle", ""),
        description   = snippet.get("title", ""),
        view_count    = int(stats.get("viewCount", 0)),
        like_count    = int(stats.get("likeCount", 0)),
        comment_count = int(stats.get("commentCount", 0)),
    )


def fetch_replies(parent_id: str, video_id: str) -> list[Comment]:
    """拉取一条顶层评论下的所有回复"""
    replies = []
    next_page_token = None

    while True:
        params = {
            "key":       YOUTUBE_API_KEY,
            "parentId":  parent_id,
            "part":      "snippet",
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
                comment_id = item["id"],
                video_id   = video_id,
                parent_id  = parent_id,
                username   = s.get("authorDisplayName", ""),
                text       = s.get("textOriginal", ""),
                like_count = s.get("likeCount", 0),
                reply_count= 0,
                created_at = s.get("publishedAt", ""),
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
            "part":       "snippet,replies",  # replies 带最多5条回复预览
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

        items = data.get("items", [])
        for item in items:
            top     = item["snippet"]["topLevelComment"]["snippet"]
            comment_id   = item["snippet"]["topLevelComment"]["id"]
            reply_count  = item["snippet"].get("totalReplyCount", 0)

            # 存顶层评论
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

            # 如果有回复，拉取全部
            if reply_count > 0:
                embedded = item.get("replies", {}).get("comments", [])

                if reply_count <= len(embedded):
                    # 回复数 <= 5，API 已经全部返回了，直接用
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
                    # 回复数 > 5，需要单独调 comments API 拿全部
                    print(f"    └─ 获取 {reply_count} 条回复...")
                    replies = fetch_replies(comment_id, video_id)
                    all_comments.extend(replies)

        top_count   = sum(1 for c in all_comments if c.parent_id is None)
        reply_count_total = sum(1 for c in all_comments if c.parent_id is not None)
        print(f"  第 {page} 页: 顶层 {top_count} 条，回复 {reply_count_total} 条")

        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            print("  已到最后一页")
            break

        page += 1

    return all_comments

def export_to_txt(video: Video, all_stored: list[dict]):
    filename = f"{video.video_id}_comments.txt"
    top_level = [c for c in all_stored if c["parent_id"] is None]
    replies   = [c for c in all_stored if c["parent_id"] is not None]

    with open(filename, "w", encoding="utf-8") as f:
        # 文件头
        f.write("=" * 60 + "\n")
        f.write(f"视频标题：{video.description}\n")
        f.write(f"频道：    {video.author}\n")
        f.write(f"链接：    https://youtube.com/watch?v={video.video_id}\n")
        f.write(f"播放：    {video.view_count:,}\n")
        f.write(f"顶层评论：{len(top_level)} 条\n")
        f.write(f"回复：    {len(replies)} 条\n")
        f.write(f"总计：    {len(all_stored)} 条\n")
        f.write("=" * 60 + "\n\n")

        # 按顶层评论 → 回复的层级结构写入
        for i, c in enumerate(top_level, 1):
            f.write(f"[{i}] @{c['username']}  👍{c['like_count']}  {c['created_at'][:10]}\n")
            f.write(f"{c['text']}\n")

            comment_replies = [r for r in replies if r["parent_id"] == c["comment_id"]]
            for r in comment_replies:
                f.write(f"\n    ↳ @{r['username']}  👍{r['like_count']}  {r['created_at'][:10]}\n")
                f.write(f"    {r['text']}\n")

            f.write("\n" + "-" * 60 + "\n\n")

    print(f"  已导出到 {filename}")

def run():
    init_db()

    url      = "https://www.youtube.com/watch?v=1asZyBsL1vM"
    video_id = get_video_id_from_url(url)
    print(f"Video ID: {video_id}\n")

    # 1. 获取视频信息
    print("获取视频信息...")
    video = fetch_video_info(video_id)
    print(f"  标题:   {video.description}")
    print(f"  频道:   {video.author}")
    print(f"  播放:   {video.view_count:,}")
    print(f"  评论数: {video.comment_count:,}")
    save_video(video)

    # 2. 抓取所有评论 + 回复
    print("\n开始抓取评论和回复...")
    comments = fetch_all_comments(video_id)
    save_comments(comments)

    # 3. 汇总
    all_stored  = get_all_comments(video_id)
    top_level   = [c for c in all_stored if c["parent_id"] is None]
    replies     = [c for c in all_stored if c["parent_id"] is not None]

    print(f"\n{'='*50}")
    print(f"抓取完成！")
    print(f"  顶层评论: {len(top_level)} 条")
    print(f"  回复:     {len(replies)} 条")
    print(f"  总计:     {len(all_stored)} 条")
    print(f"{'='*50}")

    # 4. 预览（带回复的层级展示）
    print("\n前 3 条评论预览（含回复）：")
    count = 0
    for c in all_stored:
        if c["parent_id"] is not None:
            continue
        print(f"\n💬 @{c['username']}  👍{c['like_count']}")
        print(f"   {c['text'][:80]}{'...' if len(c['text']) > 80 else ''}")

        # 打印这条评论下的回复
        comment_replies = [r for r in all_stored if r["parent_id"] == c["comment_id"]]
        for r in comment_replies[:2]:  # 每条评论最多预览 2 条回复
            print(f"   └─ @{r['username']}: {r['text'][:60]}{'...' if len(r['text']) > 60 else ''}")
        if len(comment_replies) > 2:
            print(f"   └─ ... 还有 {len(comment_replies) - 2} 条回复")

        count += 1
        if count >= 3:
            break

    # 4. 导出 txt
    print("\n正在导出 txt 文件...")
    export_to_txt(video, all_stored)


if __name__ == "__main__":
    run()
