from app.core.constants import NEGATIVE_KEYWORDS, POSITIVE_KEYWORDS


def analyze_sentiment(articles: list[dict]) -> dict:
    if not articles:
        return {
            "score": 0.0,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "total_articles": 0,
            "top_headlines": [],
        }

    positive = 0
    negative = 0
    scored_articles = []

    for article in articles:
        text = f"{article.get('title', '')} {article.get('description', '')}".lower()
        pos = sum(1 for kw in POSITIVE_KEYWORDS if kw in text)
        neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text)

        article_score = 0.0
        if pos > neg:
            positive += 1
            article_score = min(pos * 0.2, 1.0)
        elif neg > pos:
            negative += 1
            article_score = -min(neg * 0.2, 1.0)

        scored_articles.append({
            "title": article.get("title", ""),
            "source": article.get("source", ""),
            "score": round(article_score, 2),
        })

    total = len(articles)
    neutral = total - positive - negative

    if total > 0:
        raw_score = (positive - negative) / total
        score = round(raw_score, 3)
    else:
        score = 0.0

    scored_articles.sort(key=lambda x: abs(x["score"]), reverse=True)

    return {
        "score": max(min(score, 1.0), -1.0),
        "positive_count": positive,
        "negative_count": negative,
        "neutral_count": neutral,
        "total_articles": total,
        "top_headlines": scored_articles[:5],
    }
