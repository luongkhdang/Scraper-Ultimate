"""
RSS Feed Processor: Extracts and processes RSS feeds from websites.

Exported Functions:
- process_rss_feeds(website_url: str, scraper, db_client) -> int: Extracts and stores URLs from RSS feeds

Related Files:
- main.py: Main orchestration file that uses these functions
- scraper/scraper_client.py: Provides the ScraperClient class
- postgreSQL/postgreSQL_client.py: Provides the PostgreSQLClient class
"""
import logging
from urllib.parse import urlparse
from typing import Dict

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def process_rss_feeds(website_url: str, scraper, db_client) -> int:
    """
    Extract and store article URLs from RSS feeds

    Args:
        website_url: URL of the website to process
        scraper: ScraperClient instance
        db_client: PostgreSQLClient instance

    Returns:
        Number of article URLs stored
    """
    try:
        # Discover RSS feeds
        feed_urls = scraper.discover_rss_feeds(website_url)

        if not feed_urls:
            logger.warning(f"No RSS feeds found for {website_url}")
            return 0

        logger.info(f"Found {len(feed_urls)} RSS feeds for {website_url}")

        # Extract content from RSS feeds
        articles_stored = 0
        for feed_url in feed_urls:
            try:
                # Extract feed content
                feed_items = scraper.extract_rss_feed_content(feed_url)

                for item in feed_items:
                    # Extract necessary fields
                    url = item.get('link', '')
                    if not url:
                        continue

                    # Skip if URL already exists in database
                    if db_client.check_url_in_database(url):
                        continue

                    # Get domain from URL
                    parsed_url = urlparse(url)
                    domain = parsed_url.netloc

                    # Prepare article data for database
                    article_data = {
                        'url': url,
                        'domain': domain,
                        'title': item.get('title', ''),
                        'pub_date': item.get('pubDate', '')
                    }

                    # Store article URL in database
                    if db_client.store_article_url(article_data):
                        articles_stored += 1

            except Exception as e:
                logger.error(f"Error processing RSS feed {feed_url}: {e}")
                continue

        return articles_stored

    except Exception as e:
        logger.error(f"Error processing website {website_url}: {e}")
        return 0
