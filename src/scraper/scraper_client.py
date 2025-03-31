"""
Web Scraper Client: Extracts articles and content from news websites with anti-detection features.

Exported Classes:
- ScraperClient(): Main scraper class with methods to extract article URLs and content
  - extract_article_urls(website_url: str, limit: int = 10) -> List[str]: Extracts article URLs from a website
  - extract_article_content(article_url: str, referrer: Optional[str] = None) -> Optional[Dict[str, Any]]: Extracts content from an article URL

Related Files:
- main.py: Main orchestration file that uses this client
- postgreSQL/postgreSQL_client.py: Handles database operations
- src/scraper/scraper_hooks/: Package containing the scraping components
"""
from typing import List, Dict, Optional, Any
import logging

# Import the modular scraping components
from .scraper_hooks import extract_article_urls, extract_article_content

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ScraperClient:
    """
    Main scraper client class that orchestrates the modular scraping components.
    Provides a simple interface to extract article URLs and content from news websites.
    """

    def __init__(self):
        logger.info("Initializing ScraperClient")

    def extract_article_urls(self, website_url: str, limit: int = 10) -> List[str]:
        """
        Extract article URLs from a website's homepage

        Args:
            website_url: URL of the website homepage
            limit: Maximum number of URLs to extract

        Returns:
            List of article URLs
        """
        logger.info(
            f"Extracting up to {limit} article URLs from {website_url}")
        return extract_article_urls(website_url, limit)

    def extract_article_content(self, article_url: str, referrer: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Extract content from an article URL

        Args:
            article_url: URL of the article to extract
            referrer: Optional referrer URL (if None, a random one will be used)

        Returns:
            Dictionary containing article details or None if extraction fails
        """
        logger.info(f"Extracting content from {article_url}")
        return extract_article_content(article_url, referrer)
