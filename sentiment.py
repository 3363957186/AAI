from transformers import pipeline

# 第一次运行会自动下载模型（约 250MB），之后用本地缓存
_pipeline = None

def get_pipeline():
    global _pipeline
    if _pipeline is None:
        print("[Sentiment] 正在加载模型（首次运行需下载）...")
        _pipeline = pipeline(
            "sentiment-analysis",
            model="cardiffnlp/twitter-roberta-base-sentiment-latest",
        )
        print("[Sentiment] 模型加载完成")
    return _pipeline


def analyze(clean_text: str) -> dict:
    """
    输入：clean_text（preprocess 之后的文本）
    输出：{"label": "positive"/"negative", "score": 0.98}
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
        print(f"[Sentiment] 分析失败: {e}")
        return {"label": "neutral", "score": 0.0}


def analyze_batch(comments: list[dict]) -> list[dict]:
    """
    批量分析，比逐条调用快
    输入：preprocess_comments() 的输出（含 clean_text 字段）
    输出：每条评论加上 sentiment_label 和 sentiment_score
    """
    pipe = get_pipeline()
    texts = [c["clean_text"][:512] for c in comments]

    print(f"[Sentiment] 分析 {len(texts)} 条评论...")
    raw_results = pipe(texts, batch_size=32, truncation=True)

    results = []
    for c, r in zip(comments, raw_results):
        results.append({
            **c,
            "sentiment_label": r["label"].lower(),
            "sentiment_score": round(r["score"], 4),
        })

    print("[Sentiment] 分析完成")
    return results