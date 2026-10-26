from fastapi import APIRouter

from app.services.news_fetcher import fetch_all_news
from app.services.sentiment_analyzer import analyze_sentiment

router = APIRouter(prefix="/sentiment", tags=["sentiment"])


@router.get("/current")
def get_current_sentiment():
    articles = fetch_all_news()

    newsapi_count = sum(1 for a in articles if a["source"] == "newsapi")
    cryptopanic_count = sum(1 for a in articles if a["source"] == "cryptopanic")

    sentiment = analyze_sentiment(articles)

    return {
        "score": sentiment["score"],
        "positive_count": sentiment["positive_count"],
        "negative_count": sentiment["negative_count"],
        "total_articles": sentiment["total_articles"],
        "source_breakdown": {
            "newsapi": newsapi_count,
            "cryptopanic": cryptopanic_count,
        },
        "top_headlines": sentiment["top_headlines"],
    }
