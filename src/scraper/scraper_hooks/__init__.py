"""
Scraper Hooks Package: Organized collection of web scraping components.

This package organizes scraping into three main phases:
1. RSS feed handling - Discovering and extracting content from RSS feeds
2. Content extraction - Extracting content from article URLs
3. Domain management - Tracking and exporting unique domains

Exported Functions:
- extract_article_content(article_url: str, referrer: Optional[str] = None) -> Optional[Dict[str, Any]]: Extracts content from an article URL
- extract_rss_feed_urls(website_url: str) -> List[str]: Discovers RSS feed URLs from a website
- extract_urls_from_rss_feeds(website_url: str, base_url: str, feed_urls: List[str]) -> Set[str]: Extracts article URLs from RSS feeds
- extract_content_from_rss_feed(feed_url: str) -> List[Dict[str, Any]]: Extracts full content from an RSS feed
- filter_feed_content(feed_items: List[Dict[str, Any]]) -> List[Dict[str, str]]: Filters feed content to include only specific fields
- filter_by_date(feed_items: List[Dict[str, str]], days: int = 1) -> List[Dict[str, str]]: Filters feed items by publication date (last N days)
- add_domain(domains_set: Set[str], url: str) -> None: Adds domain from URL to the domains set
- add_domains_from_urls(domains_set: Set[str], urls: List[str]) -> None: Adds domains from multiple URLs to the domains set
- export_domains(domains_set: Set[str], output_file: str = "unique_domains.json") -> None: Exports domains to JSON file

Related Files:
- src/scraper/scraper_client.py: Main client file that uses these hooks
"""
from typing import Dict, List, Set, Any, Optional

from .content_extractor import extract_article_content
from .rss_feed_extractor import (
    extract_rss_feed_urls,
    extract_urls_from_rss_feeds,
    extract_content_from_rss_feed
)
from .feed_processor import filter_feed_content, filter_by_date
from .domain_manager import (
    add_domain,
    add_domains_from_urls,
    export_domains
)

# Remove unused extract_article_urls from exports
__all__ = [
    'extract_article_content',
    'extract_rss_feed_urls',
    'extract_urls_from_rss_feeds',
    'extract_content_from_rss_feed',
    'filter_feed_content',
    'filter_by_date',
    'add_domain',
    'add_domains_from_urls',
    'export_domains'
]
