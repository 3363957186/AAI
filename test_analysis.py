# test_analysis.py
import os
from gemini_analysis import generate_full_analysis, export_analysis_json


def test_single_video():
    """
    Test analysis for a single video
    """
    # 测试参数
    video_id = "9HQx5pgUoiY"
    product_name = "M4 MacBook Air"  # 修改成你实际分析的产品
    directory = "comments"  # 确保文件在这个目录下

    print("=" * 60)
    print("LOCAL TEST - Gemini Analysis")
    print("=" * 60)
    print(f"Video ID: {video_id}")
    print(f"Product: {product_name}")
    print(f"Directory: {directory}")
    print("=" * 60)

    # 检查必需文件
    transcript_file = os.path.join(directory, f"{video_id}_transcript.txt")
    clean_file = os.path.join(directory, f"{video_id}_clean.txt")

    print("\nChecking required files...")

    if os.path.exists(transcript_file):
        print(f"  ✓ Found: {transcript_file}")
    else:
        print(f"  ✗ Missing: {transcript_file}")

    if os.path.exists(clean_file):
        print(f"  ✓ Found: {clean_file}")
    else:
        print(f"  ✗ Missing: {clean_file}")
        print(f"\n⚠️  ERROR: You need {video_id}_clean.txt with sentiment analysis results!")
        print(f"  Run the main analysis pipeline first to generate this file.")
        return

    print("\n" + "=" * 60)
    print("Starting Analysis...")
    print("=" * 60 + "\n")

    # 运行分析
    result = generate_full_analysis(
        video_id=video_id,
        product_name=product_name,
        directory=directory
    )

    if result:
        # 导出结果
        export_analysis_json(video_id, result, directory=directory)

        # 打印详细结果
        print("\n" + "=" * 60)
        print("DETAILED RESULTS")
        print("=" * 60)
        print(f"\nProduct: {result['product']}")
        print(f"Verdict: {result['recommendation']['verdict']}")
        print(f"Type: {result['recommendation']['type']}")
        print(f"Confidence: {result['confidence']}%")
        print(f"Value Score: {result['value']['score']}/100")

        print(f"\n--- Sentiment Breakdown ---")
        print(f"Positive: {result['sentiment']['positive']}%")
        print(f"Neutral:  {result['sentiment']['neutral']}%")
        print(f"Negative: {result['sentiment']['negative']}%")
        print(f"Total Reviews: {result['totalReviews']}")

        print(f"\n--- Executive Overview ---")
        print(result['recommendation']['summary'])

        print(f"\n--- Value Description ---")
        print(result['value']['description'])

        print(f"\n--- Pros ({len(result['pros'])}) ---")
        for i, pro in enumerate(result['pros'], 1):
            print(f"{i}. {pro}")

        print(f"\n--- Cons ({len(result['cons'])}) ---")
        for i, con in enumerate(result['cons'], 1):
            print(f"{i}. {con}")

        print("\n" + "=" * 60)
        print("✅ Test Complete!")
        print("=" * 60)

        # 显示输出文件位置
        output_file = os.path.join(directory, f"{video_id}_analysis.json")
        print(f"\n📁 Full results saved to: {output_file}")
        print(f"   You can use this JSON file with your Chrome extension.\n")

    else:
        print("\n❌ Analysis failed. Check error messages above.")


if __name__ == "__main__":

    test_single_video()