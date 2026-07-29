from unittest.mock import Mock, patch

from twstock_lab.cache import SQLiteCache
from twstock_lab.news import GDELTNewsProvider


def test_news_sentiment_and_cache(tmp_path):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "articles": [
            {"title": "Company reports record profit and growth"},
            {"title": "Demand surge drives upgrade"},
            {"title": "Investigation creates risk warning"},
        ]
    }
    provider = GDELTNewsProvider(SQLiteCache(tmp_path / "news.sqlite3"))
    with patch("twstock_lab.news.requests.get", return_value=response) as request:
        result = provider.analyze("test company")
        cached = provider.analyze("test company")
    assert result.score > 50
    assert result.article_count == 3
    assert cached == result
    assert request.call_count == 1


def test_news_failure_is_neutral(tmp_path):
    provider = GDELTNewsProvider(SQLiteCache(tmp_path / "news.sqlite3"))
    with patch("twstock_lab.news.requests.get", side_effect=TimeoutError("timeout")):
        result = provider.analyze("unavailable")
    assert result.score == 50
    assert result.article_count == 0
    assert result.warning
