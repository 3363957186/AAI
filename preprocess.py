import re

# Filter conditions
MIN_LENGTH = 10          # Minimum comment length
MAX_LENGTH = 1000        # Maximum comment length (filter out abnormally long text)
SPAM_KEYWORDS = [
    "check my channel", "subscribe", "follow me",
    "visit my", "link in bio", "promo code"
]

def normalize(text: str) -> str:
    """Normalize text"""
    # Lowercase
    text = text.lower()
    # Remove URLs
    text = re.sub(r'http\S+|www\S+', '', text)
    # Remove @ mentions
    text = re.sub(r'@\w+', '', text)
    # Remove emojis (keep alphanumeric and basic punctuation)
    text = re.sub(r'[^\w\s\.,!?\'"-]', '', text)
    # Merge extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    # Merge repeated punctuation "!!!" → "!"
    text = re.sub(r'([!?.]){2,}', r'\1', text)
    return text


def is_valid(text: str) -> bool:
    """Check if this comment is worth keeping"""
    if len(text) < MIN_LENGTH:
        return False
    if len(text) > MAX_LENGTH:
        return False
    if any(spam in text.lower() for spam in SPAM_KEYWORDS):
        return False
    # Filter out pure symbols/numbers
    if not re.search(r'[a-zA-Z]', text):
        return False
    return True


def preprocess_comments(comments: list[dict]) -> list[dict]:
    """
    Input: Raw comment list from database get_all_comments()
    Output: Cleaned comment list with new clean_text field
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
            "clean_text": clean,   # Cleaned text for Agent to use
        })

    print(f"[Preprocess] Original: {len(comments)} → Valid: {len(results)} (filtered {skipped})")
    return results