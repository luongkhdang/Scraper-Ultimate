"""
Main Scraper Application: Orchestrates the scraping of news websites and stores content in PostgreSQL database.

This file acts as the main entry point and orchestrates the scraping workflow:
1. Extract URLs from RSS feeds (sources/rss.md)
2. Process pending articles 
3. Handle failed scrapes
4. Retry failed articles with a limited number of workers
5. Export domain statistics and failed feeds

Related Files:
- main_hooks/: Contains the core scraping functionality
- main_utils/: Contains utility functions
- scraper/: Provides the ScraperClient class for scraping
- postgreSQL/postgreSQL_client.py: Handles database operations
"""
from src.main_hooks import process_pending_articles
from src.main_utils import read_rss_feeds_from_file, wait_for_database, export_failed_domains, export_failed_feeds
from src.postgreSQL.postgreSQL_client import PostgreSQLClient
from src.scraper import ScraperClient
import os
import sys
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

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
PARALLEL_WORKERS = int(os.environ.get('PARALLEL_WORKERS', '30'))
PENDING_BATCH_SIZE = int(os.environ.get('PENDING_BATCH_SIZE', '250'))


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

        # Read RSS feeds from the file
        rss_feeds_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                      'sources', 'rss.md')
        rss_feeds = read_rss_feeds_from_file(rss_feeds_file)

        if not rss_feeds:
            logger.error("No RSS feeds found. Exiting.")
            return

        # Create two separate thread pools: one for RSS feeds, one for pending articles
        # Allocate 40% of workers for RSS feeds, minimum 5
        rss_workers = max(int(PARALLEL_WORKERS * 0.1), 1)
        # Allocate 60% of workers for articles, minimum 5
        article_workers = max(int(PARALLEL_WORKERS * 0.9), 5)

        logger.info(
            f"Creating thread pools with {rss_workers} RSS workers and {article_workers} article workers")

        # Process pending articles and RSS feeds concurrently
        total_processed = 0
        total_articles = 0
        failed_feeds = {}

        # Create a ThreadPoolExecutor for RSS feeds
        with ThreadPoolExecutor(max_workers=rss_workers) as rss_executor:
            # Submit all RSS feed processing tasks
            logger.info(
                f"Starting RSS feed scraping for {len(rss_feeds)} feeds")
            future_to_feed = {
                rss_executor.submit(process_rss_feed, feed, scraper, db_client): feed
                for feed in rss_feeds
            }

            # Start a separate thread pool for article processing
            with ThreadPoolExecutor(max_workers=article_workers) as article_executor:
                # Process pending articles in the background while RSS feeds are being processed
                # Use a shared flag to coordinate when to stop processing pending articles
                pending_processing_complete = False

                def process_pending_articles_continuously():
                    nonlocal total_processed
                    batch_count = 0
                    local_processed = 0

                    while not pending_processing_complete:
                        batch_count += 1
                        logger.info(
                            f"Processing batch #{batch_count} of pending articles (batch size: {PENDING_BATCH_SIZE})")
                        processed_count = process_pending_articles(
                            scraper, db_client, PENDING_BATCH_SIZE)

                        total_processed += processed_count
                        local_processed += processed_count
                        logger.info(
                            f"Batch #{batch_count} complete: processed {processed_count} articles")

                        if processed_count == 0:
                            # No more pending articles, but don't exit the loop yet
                            # Wait a bit to see if more articles come from RSS processing
                            logger.info(
                                "No pending articles, waiting for more from RSS feeds...")
                            time.sleep(5)

                    return local_processed

                # Start the pending article processing
                pending_future = article_executor.submit(
                    process_pending_articles_continuously)

                # Collect RSS feed results as they complete
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

                # Signal that RSS processing is complete
                logger.info(
                    f"RSS feed scraping completed. Total article URLs stored: {total_articles}")
                logger.info(
                    f"RSS feed scraping failed for {len(failed_feeds)} feeds")

                # Allow the pending article processor to finish any remaining articles
                # but stop after processing the current batch if no more articles
                pending_processing_complete = True

                # Wait for pending article processing to complete
                additional_processed = pending_future.result()
                logger.info(
                    f"Pending article processing complete. Total articles processed: {total_processed}")

        # STEP 4: Retry processing failed articles with limited workers
        logger.info(
            "========== STARTING STEP 4: RETRYING FAILED ARTICLES ==========")
        logger.info(
            f"Retrying articles with 'FAILED' status using up to {min(15, PARALLEL_WORKERS)} parallel workers...")

        # Get failed articles from the database
        failed_articles = db_client.get_failed_articles()

        if failed_articles:
            failed_count = len(failed_articles)
            logger.info(f"Found {failed_count} failed articles to retry")

            # Use a reasonable number of workers for retries
            # Maximum 15 workers for retries, which is half of our total PARALLEL_WORKERS
            retry_workers = min(15, PARALLEL_WORKERS // 2)

            # Extract URLs from failed articles
            failed_urls = [article['url'] for article in failed_articles]

            # Process failed articles in batches
            retry_batch_size = 50  # Process in smaller batches
            successfully_retried = 0

            for i in range(0, len(failed_urls), retry_batch_size):
                batch_urls = failed_urls[i:i+retry_batch_size]
                logger.info(
                    f"Processing retry batch {i//retry_batch_size + 1} of {(len(failed_urls) + retry_batch_size - 1) // retry_batch_size} ({len(batch_urls)} articles)")

                # Process this batch of failed articles
                success_count = process_pending_articles(
                    scraper,
                    db_client,
                    batch_size=retry_batch_size,
                    specific_urls=batch_urls
                )

                successfully_retried += success_count
                logger.info(
                    f"Retry batch complete: {success_count} articles successfully processed")

                # Add a small delay between batches
                if i + retry_batch_size < len(failed_urls):
                    time.sleep(2)

            logger.info(
                f"Retry processing complete. Successfully retried {successfully_retried} out of {failed_count} articles")
        else:
            logger.info("No failed articles found to retry")

        logger.info(
            "========== COMPLETED STEP 4: RETRYING FAILED ARTICLES ==========")

        # Check for remaining pending articles and process them until none remain
        logger.info(
            "========== FINAL CHECK: ENSURING NO PENDING ARTICLES REMAIN ==========")

        pending_count = db_client.get_pending_articles_count()
        while pending_count > 0:
            logger.info(
                f"Found {pending_count} remaining pending articles. Processing them now...")

            # Process in reasonable batches
            remaining_processed = process_pending_articles(
                scraper, db_client, PENDING_BATCH_SIZE)
            logger.info(
                f"Processed {remaining_processed} remaining pending articles")

            # Check if we still have pending articles
            pending_count = db_client.get_pending_articles_count()

            # Small delay to prevent tight loops
            if pending_count > 0:
                logger.info(
                    f"Still have {pending_count} pending articles. Continuing processing...")
                time.sleep(2)

        logger.info(
            "No pending articles remain in the database. Proceeding to export reports.")
        logger.info("========== COMPLETED FINAL CHECK ==========")

        # Clean up the database before generating reports
        logger.info("========== STARTING DATABASE CLEANUP ==========")
        logger.info(
            "Removing duplicate content and failed articles from the database...")
        deleted_count = db_client.clean_up_database()
        logger.info(
            f"Database cleanup complete: {deleted_count} articles removed")
        logger.info("========== COMPLETED DATABASE CLEANUP ==========")

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
