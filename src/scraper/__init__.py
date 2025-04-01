"""
Scraper Package: Contains modules for web scraping and content extraction.

Exported Classes:
- ScraperClient: Main scraper class with methods to extract article content from RSS feeds

Related Files:
- scraper_client.py: Implementation of the ScraperClient class
- scraper_hooks/: Package containing the scraping components
"""
from .scraper_client import ScraperClient

__all__ = ['ScraperClient']
