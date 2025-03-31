"""
Main Scraper Application: Orchestrates the scraping of news websites and stores content in PostgreSQL database.

Exported Functions:
- read_websites_from_file(file_path: str) -> List[str]: Reads website URLs from a file
- process_website(website_url: str, scraper: ScraperClient, db_client: PostgreSQLClient, max_articles: int) -> int: Processes a website
- main() -> None: Main function that orchestrates the scraping process

Related Files:
- scraper/scraper_client.py: Provides the ScraperClient class for scraping
- postgreSQL/postgreSQL_client.py: Handles database operations
"""
from scraper.scraper_client import ScraperClient
from postgreSQL.postgreSQL_client import PostgreSQLClient
import os
import sys
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict
from dotenv import load_dotenv
import psycopg2

# Load environment variables from .env file if present
load_dotenv()

# Add the src directory to the path so we can import the scraper client
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Scraper configuration from environment variables
MAX_ARTICLES_PER_WEBSITE = int(
    os.environ.get('MAX_ARTICLES_PER_WEBSITE', '10'))
PARALLEL_WORKERS = int(os.environ.get('PARALLEL_WORKERS', '10'))
DB_RETRY_ATTEMPTS = int(os.environ.get('DB_RETRY_ATTEMPTS', '5'))
DB_RETRY_DELAY = int(os.environ.get('DB_RETRY_DELAY', '5'))

logger.info(
    f"Scraper configuration: max_articles={MAX_ARTICLES_PER_WEBSITE}, workers={PARALLEL_WORKERS}")


def read_websites_from_file(file_path: str) -> List[str]:
    """Read website URLs from a file"""
    try:
        with open(file_path, 'r') as f:
            # Read lines and strip whitespace
            urls = [line.strip() for line in f.readlines() if line.strip()
                    and not line.strip().startswith('#')]
        logger.info(f"Read {len(urls)} websites from {file_path}")
        return urls
    except Exception as e:
        logger.error(f"Error reading websites from {file_path}: {e}")
        return []


def wait_for_database(db_client: PostgreSQLClient, max_retries: int = DB_RETRY_ATTEMPTS, delay: int = DB_RETRY_DELAY) -> bool:
    """Wait for the database to become available"""
    logger.info(
        f"Waiting for database to become available (max retries: {max_retries}, delay: {delay}s)...")

    for attempt in range(1, max_retries + 1):
        try:
            # Try to get a connection
            conn = db_client.get_connection()
            conn.close()
            logger.info("Database is available")
            return True
        except psycopg2.OperationalError as e:
            logger.warning(
                f"Database not available yet (attempt {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                logger.info(f"Waiting {delay} seconds before next attempt...")
                time.sleep(delay)
            else:
                logger.error(
                    "Maximum retry attempts reached. Database is not available.")
                return False
        except Exception as e:
            logger.error(f"Unexpected error while connecting to database: {e}")
            return False

    return False


def process_website(website_url: str, scraper: ScraperClient, db_client: PostgreSQLClient, max_articles: int = MAX_ARTICLES_PER_WEBSITE) -> int:
    """Process a single website, extract and store articles"""
    try:
        # Extract article URLs
        article_urls = scraper.extract_article_urls(
            website_url, limit=max_articles)

        # Process each article URL
        success_count = 0
        for url in article_urls:
            # Skip if URL already exists in database
            if db_client.check_url_in_database(url):
                logger.info(f"Skipping already processed URL: {url}")
                continue

            # Extract article content
            article_data = scraper.extract_article_content(url)

            # Store article if extraction was successful
            if article_data and db_client.store_article(article_data):
                success_count += 1

            # Add a small delay to avoid overloading the server
            time.sleep(1)

        return success_count
    except Exception as e:
        logger.error(f"Error processing website {website_url}: {e}")
        return 0


def main():
    """Main function to extract and store news articles"""
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

        # Read websites from the file
        websites_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                     'sources', 'websites.md')
        websites = read_websites_from_file(websites_file)

        if not websites:
            logger.error("No websites found. Exiting.")
            return

        logger.info(f"Starting scraping of {len(websites)} websites")

        # Process websites in parallel using ThreadPoolExecutor
        total_articles = 0
        with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
            # Submit all website processing tasks
            future_to_website = {
                executor.submit(process_website, website, scraper, db_client): website
                for website in websites
            }

            # Collect results as they complete
            for future in future_to_website:
                website = future_to_website[future]
                try:
                    articles_count = future.result()
                    total_articles += articles_count
                    logger.info(
                        f"Processed {articles_count} articles from {website}")
                except Exception as e:
                    logger.error(f"Error processing {website}: {e}")

        logger.info(
            f"Scraping completed. Total articles processed: {total_articles}")
    except Exception as e:
        logger.error(f"Error in main function: {e}")


if __name__ == "__main__":
    main()
