"""
Main Scraper Application: Orchestrates the scraping of news websites and stores content in PostgreSQL database.

This file acts as the main entry point and orchestrates the scraping workflow:
1. Extract URLs from RSS feeds (sources/rss.md)
2. Process pending articles 
3. Handle failed scrapes
4. Export domain statistics and failed feeds

Related Files:
- main_hooks/: Contains the core scraping functionality
- main_utils/: Contains utility functions
- scraper/: Provides the ScraperClient class for scraping
- postgreSQL/postgreSQL_client.py: Handles database operations
"""
from main_hooks import process_pending_articles
from main_utils import read_rss_feeds_from_file, wait_for_database, export_failed_domains, export_failed_feeds
from postgreSQL.postgreSQL_client import PostgreSQLClient
from scraper import ScraperClient
import os
import sys
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from dotenv import load_dotenv

# Add the src directory to the path so we can import the scraper client
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the scraper and database clients

# Import utility functions

# Import core scraping functionality

# Load environment variables from .env file if present
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Scraper configuration from environment variables
PARALLEL_WORKERS = int(os.environ.get('PARALLEL_WORKERS', '10'))
PENDING_BATCH_SIZE = int(os.environ.get('PENDING_BATCH_SIZE', '100'))


def process_rss_feed(feed_url: str, scraper: ScraperClient, db_client: PostgreSQLClient) -> int:
    """
    Process a single RSS feed and store article URLs

    Args:
        feed_url: URL of the RSS feed to process
        scraper: ScraperClient instance
        db_client: PostgreSQLClient instance

    Returns:
        Number of article URLs stored
    """
    try:
        logger.info(f"Processing RSS feed: {feed_url}")

        # Extract feed content, passing db_client to filter out existing URLs
        # Get only articles from the last 2 days
        feed_items = scraper.extract_rss_feed_content(
            feed_url, db_client, days=2)

        if not feed_items:
            logger.warning(
                f"No new recent items found in RSS feed: {feed_url}")
            return 0

        # Log number of items found
        logger.info(
            f"Found {len(feed_items)} new recent items in RSS feed: {feed_url}")

        # Process each item in the feed
        articles_stored = 0
        for item in feed_items:
            # Extract necessary fields
            url = item.get('link', '')
            if not url:
                continue

            # Parse domain from URL
            try:
                domain = url.split(
                    '/')[2] if '//' in url else url.split('/')[0]
            except IndexError:
                logger.warning(f"Malformed URL: {url}")
                continue

            # Get date
            pub_date = item.get('pubDate', '')

            # Get title with fallback
            title = item.get('title', '')
            if not title:
                title = f"Untitled article from {domain}"

            # Prepare article data for database
            article_data = {
                'url': url,
                'domain': domain,
                'title': title,
                'pub_date': pub_date
            }

            # Log the article being stored
            logger.debug(f"Storing article: {title} - {url}")

            # Store article URL in database
            result = db_client.store_article_url(article_data)
            if result:
                articles_stored += 1
                logger.debug(f"Successfully stored article: {title}")
            else:
                logger.warning(f"Failed to store article: {title} - {url}")

        logger.info(
            f"Stored {articles_stored} articles from RSS feed: {feed_url}")
        return articles_stored

    except Exception as e:
        logger.error(
            f"Error processing RSS feed {feed_url}: {e}", exc_info=True)
        return 0


def main():
    """Main function to orchestrate the scraping process"""
    try:
        # Initialize the PostgreSQL client
        db_client = PostgreSQLClient()

        # Wait for database to be available
        if not wait_for_database(db_client):
            logger.error("Could not connect to database. Exiting.")
            return

        # Set up the database
        db_client.setup_database()

        # Initialize the scraper client
        scraper = ScraperClient()

        # STEP 1: Process any pending articles from previous runs
        logger.info(
            "Starting to process pending articles before RSS scraping...")
        total_processed = 0
        batch_count = 0
        while True:
            batch_count += 1
            logger.info(
                f"Processing batch #{batch_count} of pending articles (batch size: {PENDING_BATCH_SIZE})")
            processed_count = process_pending_articles(
                scraper, db_client, PENDING_BATCH_SIZE)

            total_processed += processed_count
            logger.info(
                f"Batch #{batch_count} complete: processed {processed_count} articles")

            if processed_count == 0:
                logger.info(
                    "No more pending articles to process, moving to RSS feed scraping")
                break
            else:
                logger.info(
                    f"Continuing to next batch, {processed_count} articles processed in this batch")

        logger.info(
            f"Initial pending article processing complete. Total articles processed: {total_processed}")

        # STEP 2: Read RSS feeds from the file
        rss_feeds_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                      'sources', 'rss.md')
        rss_feeds = read_rss_feeds_from_file(rss_feeds_file)

        if not rss_feeds:
            logger.error("No RSS feeds found. Exiting.")
            return

        logger.info(f"Starting RSS feed scraping for {len(rss_feeds)} feeds")

        # Process RSS feeds in parallel
        total_articles = 0
        failed_feeds = {}
        with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
            # Submit all RSS feed processing tasks
            future_to_feed = {
                executor.submit(process_rss_feed, feed, scraper, db_client): feed
                for feed in rss_feeds
            }

            # Collect results as they complete
            for future in future_to_feed:
                feed = future_to_feed[future]
                try:
                    articles_count = future.result()
                    total_articles += articles_count

                    # Track feeds with zero articles as potentially failed
                    if articles_count == 0:
                        failed_feeds[feed] = {
                            "error": "No articles extracted",
                            "timestamp": str(datetime.now())
                        }
                except Exception as e:
                    logger.error(f"Error processing RSS feed {feed}: {e}")
                    failed_feeds[feed] = {
                        "error": str(e),
                        "timestamp": str(datetime.now())
                    }

        logger.info(
            f"RSS feed scraping completed. Total article URLs stored: {total_articles}")
        logger.info(f"RSS feed scraping failed for {len(failed_feeds)} feeds")

        # STEP 3: Process any new pending articles that were just added from RSS feeds
        if total_articles > 0:
            logger.info(
                "Processing newly added pending articles from RSS feeds...")
            additional_processed = 0
            new_batch_count = 0
            while True:
                new_batch_count += 1
                logger.info(
                    f"Processing batch #{new_batch_count} of new pending articles (batch size: {PENDING_BATCH_SIZE})")
                processed_count = process_pending_articles(
                    scraper, db_client, PENDING_BATCH_SIZE)

                additional_processed += processed_count
                logger.info(
                    f"Batch #{new_batch_count} complete: processed {processed_count} articles")

                if processed_count == 0:
                    logger.info(
                        "No more pending articles to process, exiting loop")
                    break
                else:
                    logger.info(
                        f"Continuing to next batch, {processed_count} articles processed in this batch")

            logger.info(
                f"Additional pending article processing complete. Total new articles processed: {additional_processed}")
            total_processed += additional_processed

        logger.info(
            f"All pending article processing complete. Grand total processed: {total_processed}")

        # Export failed RSS feeds
        if failed_feeds:
            failed_feeds_file = os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), 'failed_feeds.json')
            export_failed_feeds(failed_feeds, failed_feeds_file)
            logger.info(
                f"Exported {len(failed_feeds)} failed RSS feeds to {failed_feeds_file}")
        else:
            logger.info("No failed RSS feeds to export")

        # Export failed domains with error messages
        failed_domains = db_client.get_failed_domains()
        if failed_domains:
            failed_domains_file = os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), 'failed_domains.json')
            export_failed_domains(failed_domains, failed_domains_file)
            logger.info(
                f"Exported {len(failed_domains)} failed domains to {failed_domains_file}")
        else:
            logger.info("No failed domains to export")

        # Export unique domains encountered during scraping
        output_file = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), 'unique_domains.json')
        scraper.export_unique_domains(output_file)
        logger.info(f"Unique domains exported to {output_file}")

    except Exception as e:
        logger.error(f"Error in main function: {e}")


if __name__ == "__main__":
    main()
