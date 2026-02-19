from transformers import pipeline

# First run will auto-download model (~250MB), then use local cache
_pipeline = None

def get_pipeline():
    global _pipeline
    if _pipeline is None:
        print("[Sentiment] Loading model (will download on first run)...")
        _pipeline = pipeline(
            "sentiment-analysis",
            model="cardiffnlp/twitter-roberta-base-sentiment-latest",
        )
        print("[Sentiment] Model loaded")
    return _pipeline


def analyze(clean_text: str) -> dict:
    """
    Input: clean_text (text after preprocessing)
    Output: {"label": "positive"/"negative", "score": 0.98}
    """
    if not clean_text.strip():
        return {"label": "neutral", "score": 0.0}

    try:
        result = get_pipeline()(clean_text[:512])[0]
        return {
            "label": result["label"].lower(),  # positive / negative
            "score": round(result["score"], 4),
        }
    except Exception as e:
        print(f"[Sentiment] Analysis failed: {e}")
        return {"label": "neutral", "score": 0.0}


def analyze_batch(comments: list[dict]) -> list[dict]:
    """
    Batch analysis, faster than individual calls
    Input: Output from preprocess_comments() (with clean_text field)
    Output: Each comment with added sentiment_label and sentiment_score
    """
    pipe = get_pipeline()
    texts = [c["clean_text"][:512] for c in comments]

    print(f"[Sentiment] Analyzing {len(texts)} comments...")
    raw_results = pipe(texts, batch_size=32, truncation=True)

    results = []
    for c, r in zip(comments, raw_results):
        results.append({
            **c,
            "sentiment_label": r["label"].lower(),
            "sentiment_score": round(r["score"], 4),
        })

    print("[Sentiment] Analysis complete")
    return results