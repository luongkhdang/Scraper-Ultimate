"""
Database Utilities: Functions for database connection and management.

Exported Functions:
- wait_for_database(db_client, max_retries: int = 5, delay: int = 5) -> bool: Waits for the database to become available

Related Files:
- main.py: Main orchestration file that uses these utilities
- postgreSQL/postgreSQL_client.py: Provides the PostgreSQLClient class
"""
import logging
import time
import psycopg2
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration from environment variables
DB_RETRY_ATTEMPTS = int(os.environ.get('DB_RETRY_ATTEMPTS', '5'))
DB_RETRY_DELAY = int(os.environ.get('DB_RETRY_DELAY', '5'))

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def wait_for_database(db_client, max_retries: int = DB_RETRY_ATTEMPTS, delay: int = DB_RETRY_DELAY) -> bool:
    """
    Wait for the database to become available

    Args:
        db_client: PostgreSQLClient instance
        max_retries: Maximum number of connection attempts
        delay: Delay in seconds between attempts

    Returns:
        True if database is available, False otherwise
    """
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
