import re

# 过滤条件
MIN_LENGTH = 10          # 评论最少字符数
MAX_LENGTH = 1000        # 评论最多字符数（去掉异常长文本）
SPAM_KEYWORDS = [
    "check my channel", "subscribe", "follow me",
    "visit my", "link in bio", "promo code"
]

def normalize(text: str) -> str:
    """标准化文本"""
    # 转小写
    text = text.lower()
    # 去掉 URL
    text = re.sub(r'http\S+|www\S+', '', text)
    # 去掉 @ 提及
    text = re.sub(r'@\w+', '', text)
    # 去掉 emoji（保留字母数字和基本标点）
    text = re.sub(r'[^\w\s\.,!?\'"-]', '', text)
    # 合并多余空格
    text = re.sub(r'\s+', ' ', text).strip()
    # 合并重复标点 "!!!" → "!"
    text = re.sub(r'([!?.]){2,}', r'\1', text)
    return text


def is_valid(text: str) -> bool:
    """判断这条评论是否值得保留"""
    if len(text) < MIN_LENGTH:
        return False
    if len(text) > MAX_LENGTH:
        return False
    if any(spam in text.lower() for spam in SPAM_KEYWORDS):
        return False
    # 去掉纯符号/数字
    if not re.search(r'[a-zA-Z]', text):
        return False
    return True


def preprocess_comments(comments: list[dict]) -> list[dict]:
    """
    输入：从数据库 get_all_comments() 拿到的原始评论列表
    输出：清洗后的评论列表，新增 clean_text 字段
    """
    results = []
    skipped = 0

    for c in comments:
        raw_text = c.get("text", "")
        clean = normalize(raw_text)

        if not is_valid(clean):
            skipped += 1
            continue

        results.append({
            **c,
            "clean_text": clean,   # 清洗后的文本，给 Agent 用这个字段
        })

    print(f"[Preprocess] 原始: {len(comments)} 条 → 有效: {len(results)} 条（过滤 {skipped} 条）")
    return results