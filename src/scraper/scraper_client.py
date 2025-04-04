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
import json

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

        # Initialize rate limiter with bandwidth-conserving parameters
        self.rate_limiter = RateLimiter(
            max_concurrent=10,     # Reduced from 50 to 10 due to bandwidth constraints
            global_cooldown_ms=200,  # Increased from 100ms to 200ms to reduce request frequency
            # Increased from 500ms to 1000ms to reduce per-domain request frequency
            domain_cooldown_ms=1000
        )
        logger.info(
            "Rate limiter initialized with settings: 10 concurrent requests, 200ms global cooldown, 1000ms per domain")

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

        try:
            # Store domain from website_url
            add_domain(self.unique_domains, website_url)

            # Discover RSS feeds
            feed_urls = extract_rss_feed_urls(website_url)

            # Store domains from feed URLs
            add_domains_from_urls(self.unique_domains, feed_urls)

            return feed_urls
        except Exception as e:
            logger.error(
                f"Error discovering RSS feeds from {website_url}: {e}")
            raise

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
            # Pass feed_url to allow for special handling of certain feeds
            logger.info(f"Filtering articles by date: last {days} days")
            date_filtered_content = filter_by_date(
                filtered_content, days, feed_url)

            # If a database client is provided, filter out URLs that already exist in the database
            if db_client:
                logger.info(
                    f"Checking {len(date_filtered_content)} URLs against database")

                # Extract all URLs for batch checking
                urls_to_check = []
                url_to_item_map = {}

                for item in date_filtered_content:
                    url = item.get('link', '')
                    if url:
                        urls_to_check.append(url)
                        url_to_item_map[url] = item

                if not urls_to_check:
                    logger.warning("No valid URLs found in feed items")
                    return []

                try:
                    # Try to use the batch check method if available
                    if hasattr(db_client, 'check_urls_in_database'):
                        # Batch check URLs against database
                        url_exists_map = db_client.check_urls_in_database(
                            urls_to_check)

                        # Filter out existing URLs
                        new_content = []
                        existing_count = 0

                        for url, exists in url_exists_map.items():
                            if exists:
                                existing_count += 1
                            else:
                                new_content.append(url_to_item_map[url])
                    else:
                        # Fallback to individual checks if batch method not available
                        logger.warning(
                            "Batch URL checking not available, falling back to individual checks")
                        new_content = []
                        existing_count = 0

                        for url in urls_to_check:
                            # Check if URL exists in database
                            exists = db_client.check_url_in_database(url)

                            if exists:
                                existing_count += 1
                            else:
                                new_content.append(url_to_item_map[url])
                except Exception as e:
                    logger.error(f"Error checking URLs against database: {e}")
                    # Fallback to individual checks on exception
                    new_content = []
                    existing_count = 0

                    for url in urls_to_check:
                        try:
                            # Check if URL exists in database
                            exists = db_client.check_url_in_database(url)

                            if exists:
                                existing_count += 1
                            else:
                                new_content.append(url_to_item_map[url])
                        except Exception as url_check_error:
                            logger.error(
                                f"Error checking URL {url}: {url_check_error}")
                            # Include the item if we can't determine if it exists
                            new_content.append(url_to_item_map[url])

                logger.info(
                    f"Filtered out {existing_count} existing URLs from RSS feed")

                return new_content

            return date_filtered_content
        except Exception as e:
            logger.error(
                f"Error extracting content from RSS feed: {feed_url}: {e}")
            return []

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

        # Special handling for Google News URLs
        is_google_news = 'news.google.com' in domain
        if is_google_news:
            logger.info(
                f"Detected Google News URL: {article_url}, will wait for redirect")

        # Apply rate limiting
        while not self.rate_limiter.acquire(domain):
            time.sleep(0.1)  # Short sleep to avoid CPU spinning

        success = True
        try:
            # Store domain from article_url
            add_domain(self.unique_domains, article_url)

            # Handle Google News redirects
            final_url = article_url
            final_domain = domain

            if is_google_news:
                from urllib.request import Request, urlopen
                # time is already imported at the top level of the file

                # Create a request with headers to avoid being blocked
                req = Request(
                    article_url,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Referer': 'https://www.google.com/'
                    }
                )

                try:
                    # Open the URL but don't read it yet - we just want the redirect
                    redirect_start = time.time()
                    # Increase timeout to 15 seconds for slow redirects
                    response = urlopen(req, timeout=15)
                    final_url = response.geturl()
                    redirect_time = time.time() - redirect_start

                    # Get the final domain
                    final_domain = self._get_domain_from_url(final_url)

                    # Log the redirect information
                    logger.info(
                        f"Google News redirect: {article_url} -> {final_url} (took {redirect_time:.2f}s)")

                    # If the domain changed, we need to acquire a rate limit slot for the new domain
                    if final_domain != domain:
                        # Release the Google News rate limiter slot
                        self.rate_limiter.release(domain)

                        # Acquire for the new domain - this might block
                        while not self.rate_limiter.acquire(final_domain):
                            time.sleep(0.1)

                        # Update the domain for later use
                        domain = final_domain

                except Exception as redirect_error:
                    logger.error(
                        f"Error following Google News redirect: {redirect_error}")
                    # Continue with the original URL if redirect fails
                    logger.info(f"Continuing with original URL: {article_url}")

            # Extract article content from the final URL
            content = extract_article_content(final_url, referrer)

            if content:
                # Store the original and final URLs in the content
                if is_google_news and final_url != article_url:
                    content['original_url'] = article_url
                    content['final_url'] = final_url
                    content['final_domain'] = final_domain

                # Validate content length
                article_text = content.get('content', '')
                if article_text:
                    # Count characters and words to check if it's a valid article
                    char_count = len(article_text)
                    word_count = len(article_text.split())

                    # Check if content is too short (less than 800 chars or 100 words)
                    if char_count < 800 and word_count < 100:
                        logger.warning(
                            f"Article content too short: {char_count} chars, {word_count} words for {article_url}")
                        self.rate_limiter.report_error(domain)
                        success = False
                        return None

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
            if not success:
                self.rate_limiter.report_error(domain)
            self.rate_limiter.release(domain)

    def process_failed_feeds(self, failed_feeds_file: str, db_client=None, days: int = 5) -> Dict[str, Any]:
        """
        Process previously failed RSS feeds with enhanced retry mechanisms

        Args:
            failed_feeds_file: Path to the failed_feeds.json file
            db_client: Optional PostgreSQL client to check if URLs already exist
            days: Number of days to look back for articles (default: 5, increased from standard 2)

        Returns:
            Dictionary with statistics on retry results
        """
        logger.info(f"Processing failed feeds from {failed_feeds_file}")

        # Statistics to return
        stats = {
            "total_feeds_processed": 0,
            "successful_feeds": 0,
            "failed_feeds": 0,
            "total_articles_found": 0,
            "successful_feeds_list": [],
            "still_failing_feeds": {}
        }

        # Read failed feeds from file
        try:
            with open(failed_feeds_file, 'r') as f:
                failed_data = json.load(f)

            # Extract feed URLs from the data
            if "feeds" not in failed_data:
                logger.error(
                    f"Invalid failed feeds file format: {failed_feeds_file}")
                return stats

            feeds = list(failed_data["feeds"].keys())
            stats["total_feeds_processed"] = len(feeds)

            if not feeds:
                logger.info("No failed feeds found to process")
                return stats

            logger.info(f"Found {len(feeds)} failed feeds to retry")

            # Process each feed with enhanced parameters
            for feed_url in feeds:
                domain = self._get_domain_from_url(feed_url)
                logger.info(f"Retrying failed feed: {feed_url}")

                # Apply rate limiting
                while not self.rate_limiter.acquire(domain):
                    time.sleep(0.1)  # Short sleep to avoid CPU spinning

                success = True
                try:
                    # Store domain
                    add_domain(self.unique_domains, feed_url)

                    # Extract full content with enhanced parameters
                    # Note: We're using the extract_content_from_rss_feed function directly
                    # which now has enhanced retry mechanisms and multiple parsing approaches
                    all_content = extract_content_from_rss_feed(feed_url)

                    if not all_content:
                        logger.warning(
                            f"Still unable to extract content from {feed_url}")
                        stats["failed_feeds"] += 1
                        stats["still_failing_feeds"][feed_url] = {
                            "error": "No content extracted after retries",
                            "timestamp": str(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
                        }
                        continue

                    # Process the successfully extracted content
                    filtered_content = filter_feed_content(all_content)

                    # Use a more generous date range for failed feeds
                    # Pass feed_url for special handling of exempt feeds
                    logger.info(
                        f"Filtering articles by date: last {days} days")
                    date_filtered_content = filter_by_date(
                        filtered_content, days, feed_url)

                    articles_count = len(date_filtered_content)

                    # Check if we actually found any articles after date filtering
                    if articles_count == 0:
                        logger.warning(
                            f"No recent articles found in feed: {feed_url}")
                        stats["failed_feeds"] += 1
                        stats["still_failing_feeds"][feed_url] = {
                            "error": "No recent articles found",
                            "timestamp": str(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
                        }
                        continue

                    # If we have a database client, store the articles
                    if db_client:
                        stored_count = 0
                        for item in date_filtered_content:
                            url = item.get('link', '')
                            if not url:
                                continue

                            # Parse domain from URL
                            try:
                                item_domain = url.split(
                                    '/')[2] if '//' in url else url.split('/')[0]
                            except IndexError:
                                logger.warning(f"Malformed URL: {url}")
                                continue

                            # Skip if URL already exists
                            if db_client.check_url_in_database(url):
                                continue

                            # Prepare article data
                            article_data = {
                                'url': url,
                                'domain': item_domain,
                                'title': item.get('title', f"Untitled article from {item_domain}"),
                                'pub_date': item.get('pubDate', '')
                            }

                            # Store in database
                            if db_client.store_article_url(article_data):
                                stored_count += 1

                        logger.info(
                            f"Stored {stored_count} articles from previously failed feed: {feed_url}")
                        stats["total_articles_found"] += stored_count
                    else:
                        # If no database client, just count the articles
                        logger.info(
                            f"Found {articles_count} articles in previously failed feed: {feed_url}")
                        stats["total_articles_found"] += articles_count

                    # Record successful retry
                    stats["successful_feeds"] += 1
                    stats["successful_feeds_list"].append(feed_url)

                    # Report success to rate limiter
                    self.rate_limiter.report_success(domain)

                except Exception as e:
                    success = False
                    # Report error to rate limiter
                    self.rate_limiter.report_error(domain)
                    logger.error(
                        f"Error processing failed feed {feed_url}: {e}")

                    stats["failed_feeds"] += 1
                    stats["still_failing_feeds"][feed_url] = {
                        "error": str(e),
                        "timestamp": str(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
                    }
                finally:
                    # Release rate limiter slot
                    if not success:
                        self.rate_limiter.report_error(domain)
                    self.rate_limiter.release(domain)

            # Log summary
            success_rate = (stats["successful_feeds"] / stats["total_feeds_processed"]
                            ) * 100 if stats["total_feeds_processed"] > 0 else 0
            logger.info(
                f"Finished processing failed feeds. Success rate: {success_rate:.1f}%")
            logger.info(
                f"Successfully processed {stats['successful_feeds']} out of {stats['total_feeds_processed']} feeds")
            logger.info(
                f"Found {stats['total_articles_found']} articles in previously failed feeds")

            return stats

        except Exception as e:
            logger.error(
                f"Error processing failed feeds file {failed_feeds_file}: {e}")
            return stats

    def retry_feed(self, feed_url: str, db_client=None, days: int = 5) -> Dict[str, Any]:
        """
        Manually retry a specific RSS feed URL with enhanced retry mechanisms and verbose logging

        Args:
            feed_url: The RSS feed URL to retry
            db_client: Optional PostgreSQL client to check if URLs already exist
            days: Number of days to look back for articles

        Returns:
            Dictionary with results of the retry attempt
        """
        result = {
            "feed_url": feed_url,
            "success": False,
            "articles_found": 0,
            "articles_stored": 0,
            "error": None
        }

        logger.info(f"Manually retrying feed: {feed_url}")
        domain = self._get_domain_from_url(feed_url)

        # Apply rate limiting
        while not self.rate_limiter.acquire(domain):
            time.sleep(0.1)  # Short sleep to avoid CPU spinning

        success = True
        try:
            # Store domain
            add_domain(self.unique_domains, feed_url)

            # Extract content with enhanced parameters from rss_feed_extractor
            all_content = extract_content_from_rss_feed(feed_url)

            if not all_content:
                error_msg = "No content extracted after multiple retry attempts"
                logger.warning(f"{error_msg} for {feed_url}")
                result["error"] = error_msg
                return result

            # Process the content
            filtered_content = filter_feed_content(all_content)

            # Filter by date
            # Pass feed_url for special handling of exempt feeds
            logger.info(f"Filtering articles by date: last {days} days")
            date_filtered_content = filter_by_date(
                filtered_content, days, feed_url)

            result["articles_found"] = len(date_filtered_content)

            if result["articles_found"] == 0:
                error_msg = "No recent articles found after date filtering"
                logger.warning(f"{error_msg} for {feed_url}")
                result["error"] = error_msg
                return result

            # Log all found articles for debugging
            logger.info(
                f"Found {result['articles_found']} articles in feed {feed_url}:")
            # Show first 10 only to avoid log spam
            for idx, item in enumerate(date_filtered_content[:10]):
                logger.info(
                    f"  Article {idx+1}: {item.get('title', 'No title')} - {item.get('link', 'No link')}")

            if len(date_filtered_content) > 10:
                logger.info(
                    f"  ... and {len(date_filtered_content) - 10} more articles")

            # Store articles if db_client provided
            if db_client:
                stored_count = 0
                for item in date_filtered_content:
                    url = item.get('link', '')
                    if not url:
                        continue

                    # Parse domain
                    try:
                        item_domain = url.split(
                            '/')[2] if '//' in url else url.split('/')[0]
                    except IndexError:
                        logger.warning(f"Malformed URL: {url}")
                        continue

                    # Skip if URL already exists
                    if db_client.check_url_in_database(url):
                        logger.debug(f"URL already exists in database: {url}")
                        continue

                    # Prepare article data
                    article_data = {
                        'url': url,
                        'domain': item_domain,
                        'title': item.get('title', f"Untitled article from {item_domain}"),
                        'pub_date': item.get('pubDate', '')
                    }

                    # Store in database
                    if db_client.store_article_url(article_data):
                        stored_count += 1
                        logger.debug(
                            f"Stored article: {article_data['title']}")

                result["articles_stored"] = stored_count
                logger.info(
                    f"Stored {stored_count} articles from feed {feed_url}")

            # Report success
            result["success"] = True
            self.rate_limiter.report_success(domain)

        except Exception as e:
            success = False
            error_msg = str(e)
            logger.error(f"Error retrying feed {feed_url}: {error_msg}")
            result["error"] = error_msg
            self.rate_limiter.report_error(domain)
        finally:
            # Release rate limiter slot
            if not success:
                self.rate_limiter.report_error(domain)
            self.rate_limiter.release(domain)

        return result

    def export_unique_domains(self, output_file: str = "unique_domains.json") -> None:
        """
        Export the list of unique domains encountered during scraping to a JSON file

        Args:
            output_file: Path where to save the JSON file
        """
        export_domains(self.unique_domains, output_file)
