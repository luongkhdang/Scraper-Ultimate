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
        # logger.info(f"Processing RSS feed: {feed_url}") # Removed

        # Extract feed content, passing db_client to filter out existing URLs
        # Get only articles from the last 1 days
        feed_items = scraper.extract_rss_feed_content(
            feed_url, db_client, days=1)

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

        # logger.info(
        #    f"Stored {articles_stored} articles from RSS feed: {feed_url}") # Removed
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
            # Kept - might be useful config info
            f"Creating thread pools with {rss_workers} RSS workers and {article_workers} article workers")

        # Process pending articles and RSS feeds concurrently
        total_processed = 0
        total_articles = 0
        failed_feeds = {}

        # Create a ThreadPoolExecutor for RSS feeds
        with ThreadPoolExecutor(max_workers=rss_workers) as rss_executor:
            # Submit all RSS feed processing tasks
            # logger.info(
            #     f"Starting RSS feed scraping for {len(rss_feeds)} feeds") # Removed
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
                        # logger.info(
                        #     f"Processing batch #{batch_count} of pending articles (batch size: {PENDING_BATCH_SIZE})") # Removed
                        processed_count = process_pending_articles(
                            scraper, db_client, PENDING_BATCH_SIZE)

                        total_processed += processed_count
                        local_processed += processed_count
                        # logger.info(
                        #     f"Batch #{batch_count} complete: processed {processed_count} articles") # Removed

                        if processed_count == 0:
                            # No more pending articles, but don't exit the loop yet
                            # Wait a bit to see if more articles come from RSS processing
                            # logger.info(
                            #     "No pending articles, waiting for more from RSS feeds...") # Removed
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
                # logger.info(
                #     f"RSS feed scraping completed. Total article URLs stored: {total_articles}") # Removed
                logger.info(  # Kept - Summary info
                    f"RSS feed scraping failed for {len(failed_feeds)} feeds")

                # Allow the pending article processor to finish any remaining articles
                # but stop after processing the current batch if no more articles
                pending_processing_complete = True

                # Wait for pending article processing to complete
                additional_processed = pending_future.result()
                logger.info(  # Kept - Summary info
                    f"Pending article processing complete. Total articles processed: {total_processed}")

                # Check for failed articles
                failed_articles = db_client.get_failed_articles()
                failed_count = len(failed_articles)

                # logger.info( # Removed
                #     "\n========== STARTING FINAL CHECK ==========")

                if failed_count > 0:
                    # Kept - Summary info
                    logger.info(
                        f"Found {failed_count} failed articles to retry")
                    # logger.info("Retrying failed articles...") # Removed

                    # Limit retry workers to avoid overwhelming resources
                    retry_workers = min(
                        article_workers, max(5, PARALLEL_WORKERS // 4))
                    # Kept - config info
                    logger.info(
                        f"Retrying failed articles with {retry_workers} workers...")

                    # Retry failed articles with a smaller, dedicated pool
                    with ThreadPoolExecutor(max_workers=retry_workers) as retry_executor:
                        retry_futures = [
                            retry_executor.submit(
                                process_pending_articles, scraper, db_client, 1, specific_urls=[article['url']]
                            )
                            for article in failed_articles
                        ]
                        retried_count = 0
                        for future in retry_futures:
                            try:
                                result = future.result()
                                if result > 0:
                                    retried_count += 1
                            except Exception as e:
                                logger.error(f"Error during retry: {e}")

                        # Kept - Summary info
                        logger.info(
                            f"Completed retrying failed articles. Successfully retried: {retried_count}/{failed_count}")
                else:
                    # Kept - Summary info
                    logger.info("No failed articles found to retry")

                # logger.info( # Removed
                #     "\n========== COMPLETED FINAL CHECK ==========")

                # logger.info( # Removed
                #     "\n========== STARTING DATABASE CLEANUP ==========")
                # logger.info("Cleaning up old articles...") # Removed
                # Call cleanup function
                db_client.clean_up_database()
                # logger.info("Database cleanup complete.") # Removed
                # logger.info( # Removed
                #     "\n========== COMPLETED DATABASE CLEANUP ==========")

        # logger.info("\nExporting failed items...") # Removed

        # Export failed RSS feeds
        # logger.info("Exporting failed RSS feeds...") # Removed
        failed_feeds_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                         'output', 'failed_feeds.json')
        if export_failed_feeds(failed_feeds, failed_feeds_file):
            # Kept - Output location
            logger.info(f"Failed RSS feeds exported to {failed_feeds_file}")
        else:
            logger.info("No failed RSS feeds to export")  # Kept - Summary info

        # Export failed domains
        # logger.info("Exporting failed domains...") # Removed
        output_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                   'output', 'failed_domains.json')
        if export_failed_domains(db_client, output_file):
            # Kept - Output location
            logger.info(f"Failed domains exported to {output_file}")
        else:
            logger.info("No failed domains to export")  # Kept - Summary info

        # Export unique domains and their counts
        unique_domains_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                           'output', 'unique_domains.csv')
        # if db_client.export_unique_domains_to_csv(unique_domains_file): # Commented out - Method not found
        #    logger.info(f"Unique domains exported to {unique_domains_file}") # Kept - Output location

    except Exception as e:
        logger.error(f"Error in main function: {e}", exc_info=True)
    finally:
        pass  # Added pass to fix indentation error


if __name__ == "__main__":
    main()
