from config import MAX_VIDEOS, MAX_COMMENTS_PER_VIDEO
from storage.database import init_db, save_video, save_comments, get_comments
from scraper.video_searcher import VideoSearcher
from scraper.comment_scraper import CommentScraper

def run():
    init_db()

    keyword = input("请输入商品名称（英文）: ").strip()
    if not keyword:
        print("不能为空")
        return

    # 1. 搜索视频
    searcher = VideoSearcher()
    videos = searcher.search(keyword, max_results=MAX_VIDEOS)

    if not videos:
        print("未找到视频，请检查 API Key 或关键词")
        return

    # 2. 展示搜索结果
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

    # 3. 抓取评论
    scraper = CommentScraper()
    for i, video in enumerate(videos, 1):
        print(f"\n[{i}/{len(videos)}] {video.description[:50]}")
        save_video(video)
        comments = scraper.fetch_comments(video.video_id, max_count=MAX_COMMENTS_PER_VIDEO)
        save_comments(comments)
        print(f"    ✓ 存储 {len(comments)} 条评论")

    # 4. 汇总
    print("\n" + "=" * 60)
    total = 0
    for video in videos:
        count = len(get_comments(video.video_id))
        total += count
        print(f"  {video.description[:45]}  →  {count} 条评论")
    print(f"\n  共 {len(videos)} 个视频，{total} 条评论")
    print("=" * 60)

if __name__ == "__main__":
    run()