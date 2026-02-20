# api_server.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import os

from main import (
    search_videos, fetch_all_comments, save_video, save_comments,
    get_all_comments, init_db, export_to_txt, export_to_txt_v2,
    export_clean_json
)
from preprocess import preprocess_comments
from sentiment import analyze_batch
from storage.database import save_sentiment, get_sentiment_summary
from transcript import fetch_transcript_auto, export_transcript
from gemini_analysis import generate_full_analysis, export_analysis_json
from config import GEMINI_API_KEY, YOUTUBE_API_KEY

app = Flask(__name__)
CORS(app)

init_db()


@app.route('/api/analyze', methods=['POST'])
def analyze():
    try:
        data = request.json
        product_name = data.get('product', '').strip()

        if not product_name:
            return jsonify({"error": "Product name is required"}), 400

        print(f"\n{'=' * 60}")
        print(f"[API] Received analysis request: {product_name}")
        print(f"{'=' * 60}\n")

        # 1. 搜索视频
        print(f"[API] Searching videos...")
        videos = search_videos(product_name, max_results=3)

        if not videos:
            return jsonify({
                "error": "No review videos found",
                "message": f"Could not find YouTube reviews for '{product_name}'"
            }), 404

        print(f"[API] Found {len(videos)} videos")

        # 2. 分析第一个视频
        video = videos[0]
        video_id = video.video_id
        print(f"[API] Analyzing: {video.description[:60]}...")

        save_video(video)

        # 3. 获取字幕
        print(f"[API] Fetching transcript...")
        transcript_result = fetch_transcript_auto(video_id, debug=False)
        if transcript_result["success"]:
            export_transcript(video_id, transcript_result)
            print(f"  ✓ Saved: {video_id}_transcript.txt")

        # 4. 抓取评论
        print(f"[API] Fetching comments...")
        comments = fetch_all_comments(video_id, max_pages_per_order=3)
        save_comments(comments)

        all_stored = get_all_comments(video_id)
        print(f"  ✓ Fetched {len(all_stored)} comments")

        # 5. 导出原始评论文件
        print(f"[API] Exporting comment files...")
        export_to_txt(video, all_stored)
        print(f"  ✓ Saved: {video_id}_comments.txt")

        # 6. 预处理和情感分析
        print(f"[API] Analyzing sentiment...")
        cleaned = preprocess_comments(all_stored)
        analyzed = analyze_batch(cleaned)
        save_sentiment(analyzed)

        # 7. 导出情感分析结果
        summary = get_sentiment_summary(video_id)
        all_stored = get_all_comments(video_id)  # 重新获取带情感标签的数据
        export_to_txt_v2(video, all_stored, summary)
        print(f"  ✓ Saved: {video_id}_comments_v2.txt")

        export_clean_json(video_id, analyzed)
        print(f"  ✓ Saved: {video_id}_clean.txt")

        # 8.获取视频字幕
        transcript_result = fetch_transcript_auto(video.video_id)

        if transcript_result["success"]:
            print(f"  ✓ Got transcript ({transcript_result['language']})")
            export_transcript(video.video_id, transcript_result)
        else:
            print(f"  ⚠️  {transcript_result['error']}")
            print(f"     Video may not have captions/subtitles available")

        # 9. Gemini 完整分析
        print(f"[API] Running Gemini analysis...")
        analysis_result = generate_full_analysis(
            video_id=video_id,
            product_name=product_name,
            directory="comments"
        )

        if not analysis_result:
            return jsonify({
                "error": "Analysis failed",
                "message": "Could not complete Gemini analysis"
            }), 500

        export_analysis_json(video_id, analysis_result, directory="comments")
        print(f"  ✓ Saved: {video_id}_analysis.json")

        # 10. 打印摘要
        print(f"\n{'=' * 60}")
        print(f"[API] ✅ Analysis Complete!")
        print(f"  Product: {product_name}")
        print(f"  Verdict: {analysis_result['recommendation']['verdict']}")
        print(f"  Score: {analysis_result['value']['score']}/100")
        print(f"  Files saved in: comments/")
        print(f"{'=' * 60}\n")

        # 10. 返回结果给前端
        return jsonify(analysis_result)

    except Exception as e:
        print(f"\n[API] ❌ Error: {str(e)}\n")
        import traceback
        traceback.print_exc()

        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "message": "RateIQ API is running"})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)