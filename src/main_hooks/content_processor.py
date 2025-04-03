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

        # Extract article content
        content_data = scraper.extract_article_content(article_url)

        if content_data and content_data.get('content'):
            # Check if we have final_domain information from a redirect
            final_domain = content_data.get('final_domain')

            # Update the domain in the database if this was redirected
            # (especially for news.google.com and other redirect services)
            if final_domain and final_domain != original_domain:
                logger.info(
                    f"Domain updated for article {article_id}: {original_domain} -> {final_domain}")

                # Update article with content and the new domain
                return db_client.update_article_content(
                    article_id,
                    content_data['content'],
                    error_message=None,
                    domain=final_domain
                )
            else:
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
