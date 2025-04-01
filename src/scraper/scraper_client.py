"""
Web Scraper Client: Extracts articles and content from news websites with anti-detection features.

Exported Classes:
- ScraperClient(): Main scraper class with methods to extract article content from RSS feeds
  - discover_rss_feeds(website_url: str) -> List[str]: Discovers RSS feed URLs from a website
  - extract_rss_feed_content(feed_url: str, db_client=None, days=2) -> List[Dict[str, str]]: Extracts specific fields from an RSS feed, filtering by date and existing URLs
  - extract_article_content(article_url: str, referrer: Optional[str] = None) -> Optional[Dict[str, Any]]: Extracts content from an article URL
  - export_unique_domains(output_file: str = "unique_domains.json") -> None: Exports list of unique domains to a JSON file

Related Files:
- main.py: Main orchestration file that uses this client
- postgreSQL/postgreSQL_client.py: Handles database operations
- src/scraper/scraper_hooks/: Package containing the scraping components
"""
from typing import List, Dict, Optional, Any, Set
import logging
import urllib.parse
import time

# Import the modular scraping components
from .scraper_hooks import (
    extract_article_content,
    extract_rss_feed_urls,
    extract_content_from_rss_feed,
    filter_feed_content,
    filter_by_date,
    add_domain,
    add_domains_from_urls,
    export_domains
)

# Import rate limiter
from main_utils import RateLimiter

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ScraperClient:
    """
    Main scraper client class that orchestrates the modular scraping components.
    Provides a simple interface to extract article content from RSS feeds.
    """

    def __init__(self):
        logger.info("Initializing ScraperClient")
        self.unique_domains: Set[str] = set()

        # Initialize rate limiter with specified parameters
        self.rate_limiter = RateLimiter(
            max_concurrent=10,      # Allow 10 concurrent requests
            global_cooldown_ms=500,  # 500ms global cooldown
            domain_cooldown_ms=2000  # 2s per domain cooldown
        )
        logger.info(
            "Rate limiter initialized with settings: 10 concurrent requests, 500ms global cooldown, 2s per domain")

    def _get_domain_from_url(self, url: str) -> str:
        """Extract the domain from a URL for rate limiting purposes"""
        try:
            parsed_url = urllib.parse.urlparse(url)
            return parsed_url.netloc
        except Exception:
            # If parsing fails, use the URL as is
            return url

    def discover_rss_feeds(self, website_url: str) -> List[str]:
        """
        Discover RSS feed URLs from a website

        Args:
            website_url: URL of the website to scan for RSS feeds

        Returns:
            List of discovered RSS feed URLs
        """
        logger.info(f"Discovering RSS feeds from {website_url}")
        domain = self._get_domain_from_url(website_url)

        # Apply rate limiting
        while not self.rate_limiter.acquire(domain):
            time.sleep(0.1)  # Short sleep to avoid CPU spinning

        success = True
        try:
            # Store domain from website_url
            add_domain(self.unique_domains, website_url)

            # Discover RSS feeds
            feed_urls = extract_rss_feed_urls(website_url)

            # Store domains from feed URLs
            add_domains_from_urls(self.unique_domains, feed_urls)

            # Report success to rate limiter
            self.rate_limiter.report_success(domain)

            return feed_urls
        except Exception as e:
            success = False
            # Report error to rate limiter to increase backoff
            self.rate_limiter.report_error(domain)
            logger.error(
                f"Error discovering RSS feeds from {website_url}: {e}")
            raise
        finally:
            # Release the rate limiter slot
            if not success:
                self.rate_limiter.report_error(domain)
            self.rate_limiter.release(domain)

    def extract_rss_feed_content(self, feed_url: str, db_client=None, days: int = 2) -> List[Dict[str, str]]:
        """
        Extract specific fields from an RSS feed: language, title, description, link, and pubDate

        Args:
            feed_url: URL of the RSS feed to extract content from
            db_client: Optional PostgreSQL client to check if URLs already exist in the database
            days: Number of days to look back for articles (default: 2, meaning yesterday to today)

        Returns:
            List of dictionaries containing only the specified fields from RSS feed items
        """
        logger.info(f"Extracting specific fields from RSS feed: {feed_url}")
        domain = self._get_domain_from_url(feed_url)

        # Apply rate limiting
        while not self.rate_limiter.acquire(domain):
            time.sleep(0.1)  # Short sleep to avoid CPU spinning

        success = True
        try:
            # Store domain from feed_url
            add_domain(self.unique_domains, feed_url)

            # Get full content from the RSS feed
            all_content = extract_content_from_rss_feed(feed_url)

            if not all_content:
                logger.warning(
                    f"No content extracted from RSS feed: {feed_url}")
                return []

            # Filter to only include the fields we're interested in
            filtered_content = filter_feed_content(all_content)

            # Filter by publication date (only keep articles from the last 'days' days)
            logger.info(f"Filtering articles by date: last {days} days")
            date_filtered_content = filter_by_date(filtered_content, days)

            # If a database client is provided, filter out URLs that already exist in the database
            if db_client:
                logger.info(
                    f"Checking {len(date_filtered_content)} URLs against database")
                new_content = []
                existing_count = 0

                for item in date_filtered_content:
                    url = item.get('link', '')
                    if not url:
                        continue

                    # Check if URL exists in database
                    exists = db_client.check_url_in_database(url)

                    if exists:
                        existing_count += 1
                    else:
                        new_content.append(item)

                logger.info(
                    f"Filtered out {existing_count} existing URLs from RSS feed")

                # Report success to rate limiter
                self.rate_limiter.report_success(domain)

                return new_content

            # Report success to rate limiter
            self.rate_limiter.report_success(domain)

            return date_filtered_content
        except Exception as e:
            success = False
            # Report error to rate limiter to increase backoff
            self.rate_limiter.report_error(domain)
            logger.error(
                f"Error extracting content from RSS feed: {feed_url}: {e}")
            return []
        finally:
            # Release the rate limiter slot
            self.rate_limiter.release(domain)

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
        domain = self._get_domain_from_url(article_url)

        # Apply rate limiting
        while not self.rate_limiter.acquire(domain):
            time.sleep(0.1)  # Short sleep to avoid CPU spinning

        success = True
        try:
            # Store domain from article_url
            add_domain(self.unique_domains, article_url)

            # Extract article content
            content = extract_article_content(article_url, referrer)

            if content:
                # Report success to rate limiter
                self.rate_limiter.report_success(domain)
            else:
                # Report failure to rate limiter
                self.rate_limiter.report_error(domain)
                success = False

            return content
        except Exception as e:
            success = False
            # Report error to rate limiter to increase backoff
            self.rate_limiter.report_error(domain)
            logger.error(f"Error extracting content from {article_url}: {e}")
            return None
        finally:
            # Release the rate limiter slot
            self.rate_limiter.release(domain)

    def export_unique_domains(self, output_file: str = "unique_domains.json") -> None:
        """
        Export the list of unique domains encountered during scraping to a JSON file

        Args:
            output_file: Path where to save the JSON file
        """
        export_domains(self.unique_domains, output_file)
