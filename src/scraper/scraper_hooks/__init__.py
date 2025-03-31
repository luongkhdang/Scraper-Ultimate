"""
Scraper Hooks Package: Organized collection of web scraping components.

This package organizes scraping into two main phases:
1. URL extraction - Finding article URLs from website homepages and RSS feeds
2. Content extraction - Extracting content from those article URLs

Exported Functions:
- extract_article_urls(website_url: str, limit: int = 10) -> List[str]: Extracts article URLs from a website
- extract_article_content(article_url: str, referrer: Optional[str] = None) -> Optional[Dict[str, Any]]: Extracts content from an article URL

Related Files:
- src/scraper/scraper_client.py: Main client file that uses these hooks
"""

from .url_extractor import extract_article_urls
from .content_extractor import extract_article_content

__all__ = ['extract_article_urls', 'extract_article_content']
