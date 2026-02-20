# gemini_analysis.py
import os
import glob
import json
import google.generativeai as genai
from pydantic import BaseModel, Field
from config import GEMINI_API_KEY, YOUTUBE_API_KEY


# ═══════════════════════════════════════════════════════════
# Pydantic Model
# ═══════════════════════════════════════════════════════════

class ProductSummary(BaseModel):
    executive_overview: str = Field(description="100 words or less")
    key_features: list[str] = Field(description="5-7 key features")
    pros: list[str] = Field(description="5-7 pros")
    cons: list[str] = Field(description="5-7 cons")
    overall_sentiment: str = Field(description="Positive/Negative/Mixed")
    product_score: int = Field(description="Score 1-100")
    value_description: str = Field(description="1-2 sentence value assessment")


# ═══════════════════════════════════════════════════════════
# Configure API
# ═══════════════════════════════════════════════════════════

def setup_gemini():
    """Initialize Gemini API"""
    api_key = GEMINI_API_KEY
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found. Set environment variable.")
    genai.configure(api_key=api_key)


# ═══════════════════════════════════════════════════════════
# Sentiment Analysis
# ═══════════════════════════════════════════════════════════

def analyze_sentiment_data(video_id: str, directory: str = "comments"):
    """
    Analyze sentiment from {video_id}_clean.txt
    Returns: dict with sentiment statistics (包含三种情感)
    """
    file_path = os.path.join(directory, f"{video_id}_clean.txt")

    if not os.path.exists(file_path):
        print(f"  ⚠️  Sentiment file not found: {file_path}")
        return None

    print(f"  [Gemini] Analyzing sentiment data...")

    positive_weighted = 0.0
    negative_weighted = 0.0
    neutral_weighted = 0.0  # ← 包含中性
    total_sentiment_score = 0.0
    total_comments = 0

    sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            comments = json.load(file)

        for comment in comments:
            like_count = comment.get("like_count", 0)
            sentiment_score = comment.get("sentiment_score", 0.0)
            sentiment_label = comment.get("sentiment_label", "").lower()

            # Weighted score: higher likes = higher weight
            weighted_score = (1 + 0.05 * like_count) * sentiment_score

            if sentiment_label == "positive":
                positive_weighted += weighted_score
                sentiment_counts["positive"] += 1
            elif sentiment_label == "negative":
                negative_weighted += weighted_score
                sentiment_counts["negative"] += 1
            elif sentiment_label == "neutral":
                neutral_weighted += weighted_score
                sentiment_counts["neutral"] += 1

            total_sentiment_score += sentiment_score
            total_comments += 1

    except Exception as e:
        print(f"  ⚠️  Error analyzing sentiment: {e}")
        return None

    if total_comments == 0:
        return None

    # Calculate percentages (包含三种情感)
    total_weighted = positive_weighted + negative_weighted + neutral_weighted

    if total_weighted == 0:
        print("  ⚠️  All sentiment scores are 0")
        return None

    positive_pct = (positive_weighted / total_weighted * 100)
    negative_pct = (negative_weighted / total_weighted * 100)
    neutral_pct = (neutral_weighted / total_weighted * 100)

    avg_sentiment = total_sentiment_score / total_comments

    results = {
        "total_comments": total_comments,
        "sentiment_counts": sentiment_counts,
        "positive_percentage": round(positive_pct, 1),
        "negative_percentage": round(negative_pct, 1),
        "neutral_percentage": round(neutral_pct, 1),
        "average_sentiment_score": round(avg_sentiment, 4),
        "confidence": int(avg_sentiment * 100)
    }

    print(f"  ✓ Sentiment: {positive_pct:.1f}% positive, {negative_pct:.1f}% negative, {neutral_pct:.1f}% neutral")
    return results


# ═══════════════════════════════════════════════════════════
# Transcript Summarization
# ═══════════════════════════════════════════════════════════

def summarize_transcript(video_id: str, product_name: str, sentiment_data: dict, directory: str = "comments"):
    """
    Use Gemini to generate structured summary from video transcript
    传入情感数据以获得更准确的评分
    """
    file_path = os.path.join(directory, f"{video_id}_transcript.txt")

    if not os.path.exists(file_path):
        print(f"  ⚠️  Transcript not found: {file_path}")
        return None

    print(f"  [Gemini] Reading transcript...")

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            transcript_content = file.read()
    except Exception as e:
        print(f"  ⚠️  Error reading transcript: {e}")
        return None

    # 构造包含情感数据的 prompt
    sentiment_context = ""
    if sentiment_data:
        sentiment_context = f"""

**User Comment Sentiment Analysis:**
- Total comments: {sentiment_data['total_comments']}
- Positive: {sentiment_data['sentiment_counts']['positive']} ({sentiment_data['positive_percentage']:.1f}%)
- Negative: {sentiment_data['sentiment_counts']['negative']} ({sentiment_data['negative_percentage']:.1f}%)
- Neutral: {sentiment_data['sentiment_counts']['neutral']} ({sentiment_data['neutral_percentage']:.1f}%)
- Average sentiment score: {sentiment_data['average_sentiment_score']:.4f}

Use this sentiment data to calibrate your product_score.
"""

    prompt = f"""You are an expert product analyst. Below is a YouTube video transcript 
reviewing the product: '{product_name}'.
{sentiment_context}

Analyze this transcript AND the user sentiment data to extract:

- **executive_overview**: A concise 100-word summary
- **key_features**: 5-7 notable features mentioned
- **pros**: 5-7 advantages highlighted
- **cons**: 5-7 disadvantages or criticisms
- **overall_sentiment**: "Positive", "Negative", or "Mixed"
- **product_score**: Rate 1-100 based on BOTH video content (40%) and user comments (60%)
  * Scale: 1-20=Terrible, 21-40=Poor, 41-60=Average, 61-80=Good, 81-100=Excellent
  * {sentiment_data['positive_percentage']:.1f}% positive comments should push score toward {int(sentiment_data['positive_percentage'] * 0.8)}
  * Be generous with scoring if sentiment is highly positive
- **value_description**: 1-2 sentences on value for money

Transcript:
{transcript_content}
"""

    print(f"  [Gemini] Sending to API...")
    try:
        setup_gemini()
        model = genai.GenerativeModel('gemini-2.5-flash')

        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=ProductSummary,
            ),
        )

        summary_dict = json.loads(response.text)
        print(f"  ✓ Gemini analysis complete (Score: {summary_dict['product_score']}/100)")
        return summary_dict

    except Exception as e:
        print(f"  ⚠️  Gemini API error: {e}")
        return None


# ═══════════════════════════════════════════════════════════
# Full Analysis
# ═══════════════════════════════════════════════════════════

def generate_full_analysis(video_id: str, product_name: str, directory: str = "comments"):
    """
    Combine sentiment + transcript analysis
    Returns: Frontend-ready data structure
    """
    print(f"\n{'=' * 60}")
    print(f"[Gemini] Starting Full Analysis")
    print(f"  Product: {product_name}")
    print(f"  Video ID: {video_id}")
    print(f"{'=' * 60}\n")

    # 1. Analyze sentiment
    sentiment_data = analyze_sentiment_data(video_id, directory)
    if not sentiment_data:
        print("  ❌ No sentiment data")
        return None

    # 2. Summarize transcript (传入情感数据)
    transcript_summary = summarize_transcript(
        video_id,
        product_name,
        sentiment_data,  # ← 传入情感数据
        directory
    )

    if not transcript_summary:
        print("  ⚠️  Using fallback (no transcript)")
        # 基于情感数据生成 fallback 评分
        positive_pct = sentiment_data['positive_percentage']
        fallback_score = int(positive_pct * 0.8 + 20)

        transcript_summary = {
            "executive_overview": f"Based on {sentiment_data['total_comments']} user comments. Video transcript not available.",
            "key_features": ["User-reported features only"],
            "pros": ["Positive user feedback"],
            "cons": ["Negative user feedback"],
            "overall_sentiment": "Positive" if positive_pct >= 60 else "Negative" if positive_pct < 40 else "Mixed",
            "product_score": fallback_score,
            "value_description": f"Score based on {positive_pct:.1f}% positive sentiment."
        }

    # 3. Determine recommendation
    positive_pct = sentiment_data['positive_percentage']
    score = transcript_summary['product_score']

    if score >= 80:
        verdict = "Strong Buy"
        rec_type = "buy"
    elif score >= 60:
        verdict = "Buy"
        rec_type = "buy"
    elif score >= 50:
        verdict = "Consider"
        rec_type = "consider"
    elif score >= 40:
        verdict = "Don't Buy"
        rec_type = "dont-buy"
    else:
        verdict = "Strong Don't Buy"
        rec_type = "dont-buy"

    # 4. Format for frontend
    result = {
        "product": product_name,
        "confidence": sentiment_data['confidence'],
        "recommendation": {
            "verdict": verdict,
            "type": rec_type,
            "summary": transcript_summary['executive_overview']
        },
        "sentiment": {
            "positive": sentiment_data['positive_percentage'],
            "neutral": sentiment_data['neutral_percentage'],
            "negative": sentiment_data['negative_percentage']
        },
        "totalReviews": sentiment_data['total_comments'],
        "value": {
            "score": score,
            "description": transcript_summary['value_description']
        },
        "pros": transcript_summary['pros'],
        "cons": transcript_summary['cons'],
        "sources": [
            {
                "platform": "youtube",
                "name": "YouTube",
                "count": sentiment_data['total_comments']
            }
        ]
    }

    print(f"\n{'=' * 60}")
    print(f"✅ Analysis Complete!")
    print(f"  Verdict: {verdict}")
    print(f"  Score: {score}/100")
    print(
        f"  Sentiment: {positive_pct:.1f}% positive, {sentiment_data['negative_percentage']:.1f}% negative, {sentiment_data['neutral_percentage']:.1f}% neutral")
    print(f"{'=' * 60}\n")

    return result


# ═══════════════════════════════════════════════════════════
# Export Function (补上这个函数)
# ═══════════════════════════════════════════════════════════

def export_analysis_json(video_id: str, analysis_data: dict, directory: str = "comments"):
    """Export analysis result to JSON file"""
    if not analysis_data:
        print("  ⚠️  No analysis data to export")
        return

    output_path = os.path.join(directory, f"{video_id}_analysis.json")
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(analysis_data, f, indent=2, ensure_ascii=False)
        print(f"  ✓ Analysis exported to {output_path}")
    except Exception as e:
        print(f"  ⚠️  Failed to export analysis: {e}")