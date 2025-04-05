"""
Content Processor: Processes article content from URLs stored in the database.

Exported Functions:
- process_article_content(article: Dict, scraper, db_client) -> bool: Processes a single article's content
- process_pending_articles(scraper, db_client, batch_size: int = 100) -> int: Processes articles with pending status

Related Files:
- main.py: Main orchestration file that uses these functions
- scraper/scraper_client.py: Provides the ScraperClient class
- postgreSQL/postgreSQL_client.py: Provides the PostgreSQLClient class
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict
import os
from urllib.parse import urlparse

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration from environment variables
PARALLEL_WORKERS = int(os.environ.get('PARALLEL_WORKERS', '30'))
PENDING_BATCH_SIZE = int(os.environ.get('PENDING_BATCH_SIZE', '250'))


def process_article_content(article: Dict, scraper, db_client) -> bool:
    """
    Process a single article's content

    Args:
        article: Dictionary containing article data
        scraper: ScraperClient instance
        db_client: PostgreSQLClient instance

    Returns:
        True if successful, False otherwise
    """
    try:
        article_id = article['id']
        article_url = article['url']
        original_domain = article['domain']

        # Check if this is a Google News URL
        is_google_news = 'news.google.com' in original_domain
        if is_google_news:
            logger.info(
                f"Processing Google News URL: {article_url} (ID: {article_id})")

        # Extract article content
        content_data = scraper.extract_article_content(article_url)

        if content_data and content_data.get('content'):
            # Check if we have final_domain information from a redirect
            final_domain = content_data.get('final_domain')
            final_url = content_data.get('final_url')

            # Log available keys in content_data for debugging
            if is_google_news:
                logger.debug(f"Content data keys: {list(content_data.keys())}")

            # Debug logs to trace domain information
            logger.debug(f"Article {article_id} extraction complete:")
            logger.debug(f"  Original domain: {original_domain}")
            logger.debug(f"  Final domain from content: {final_domain}")

            # Fallback for Google News URLs if final_domain is missing but we have final_url
            if is_google_news and not final_domain and final_url:
                try:
                    computed_final_domain = urlparse(final_url).netloc.lower()
                    if computed_final_domain and computed_final_domain != original_domain:
                        logger.warning(
                            f"Using computed final_domain from final_url: {computed_final_domain}")
                        final_domain = computed_final_domain
                except Exception as e:
                    logger.error(f"Error computing domain from final_url: {e}")

            # Update the domain in the database if this was redirected
            # (from news.google.com, biztoc.com, or any other URL that redirects)
            if final_domain and final_domain != original_domain:
                logger.info(
                    f"Domain updated for article {article_id}: {original_domain} -> {final_domain}")
                if final_url:
                    logger.info(
                        f"URL updated: {article_url} -> {final_url}")

                # Update article with content and the new domain
                return db_client.update_article_content(
                    article_id,
                    content_data['content'],
                    error_message=None,
                    domain=final_domain
                )
            else:
                if is_google_news:
                    # More detailed diagnostic info
                    logger.warning(
                        f"Google News URL did not have final_domain in content_data. Domain not updated. URL: {article_url}")
                    logger.warning(
                        f"Content keys available: {list(content_data.keys())}")
                    if 'url' in content_data:
                        logger.warning(f"Content URL: {content_data['url']}")

                # Update article with content only
                return db_client.update_article_content(article_id, content_data['content'])
        else:
            # Update article with error message
            error_msg = "Failed to extract content: Content extraction returned empty result"
            return db_client.update_article_content(article_id, None, error_msg)

    except Exception as e:
        error_msg = f"Error extracting content: {str(e)}"
        logger.error(f"Error processing article {article['url']}: {e}")

        # Update article with error message
        return db_client.update_article_content(article['id'], None, error_msg)


def process_pending_articles(scraper, db_client, batch_size: int = PENDING_BATCH_SIZE, specific_urls: list = None) -> int:
    """
    Process pending articles and handle failures

    Args:
        scraper: ScraperClient instance
        db_client: PostgreSQLClient instance
        batch_size: Number of pending articles to process
        specific_urls: Optional list of specific URLs to process (overrides batch_size and pending check)

    Returns:
        Number of articles processed
    """
    try:
        # Get articles to process
        if specific_urls:
            # If specific URLs are provided, get their article data
            pending_articles = []
            for url in specific_urls:
                article_data = db_client.get_article_by_url(url)
                if article_data:
                    pending_articles.append(article_data)

            if not pending_articles:
                logger.info("No articles found with the specified URLs")
                return 0

            logger.info(
                f"Processing {len(pending_articles)} specific articles")
        else:
            # Otherwise get regular pending articles
            pending_articles = db_client.get_pending_articles(limit=batch_size)

            if not pending_articles:
                logger.info("No pending articles to process")
                return 0

            logger.info(f"Processing {len(pending_articles)} pending articles")

        # Process articles in parallel
        success_count = 0
        with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
            # Submit all article processing tasks
            future_to_article = {
                executor.submit(process_article_content, article, scraper, db_client): article
                for article in pending_articles
            }

            # Collect results as they complete
            for future in future_to_article:
                article = future_to_article[future]
                try:
                    success = future.result()
                    if success:
                        success_count += 1
                except Exception as e:
                    logger.error(
                        f"Error processing article {article['url']}: {e}")

        return success_count

    except Exception as e:
        logger.error(f"Error processing pending articles: {e}")
        return 0
