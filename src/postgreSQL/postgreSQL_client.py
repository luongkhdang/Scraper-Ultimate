"""
PostgreSQL Database Client: Handles database connections and operations for the scraper.

Exported Functions:
- setup_database() -> None: Sets up required database tables
- store_article_url(article_data: Dict) -> bool: Stores article URL and metadata from RSS
- update_article_content(article_id: int, content: str, error_message: Optional[str] = None, domain: Optional[str] = None) -> bool: Updates article with scraped content
- get_pending_articles(limit: int = 100) -> list: Gets articles with 'Pending' status
- check_url_in_database(url: str) -> bool: Checks if a URL exists in the database
- check_urls_in_database(urls: List[str]) -> Dict[str, bool]: Batch checks multiple URLs against the database

Related Files:
- main.py: Main orchestration file that uses this client
- scraper/scraper_client.py: Provides the ScraperClient class for scraping
"""
import os
import sys
import logging
import psycopg2
from psycopg2.extras import Json
from typing import Dict, Optional, Any, List
from dotenv import load_dotenv
from psycopg2 import pool
import threading
import time

# Load environment variables from .env file if present
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database configuration from environment variables
DB_CONFIG = {
    'dbname': os.environ.get('DB_NAME', 'news-db'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', 'postgres'),
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': os.environ.get('DB_PORT', '5432')
}

# Get PARALLEL_WORKERS from environment for connection pool sizing
PARALLEL_WORKERS = int(os.environ.get('PARALLEL_WORKERS', '10'))

# Configure connection pool size based on parallel workers
# We need at least as many connections as workers, plus some overhead
MIN_CONNECTIONS = max(3, PARALLEL_WORKERS // 2)
MAX_CONNECTIONS = max(15, PARALLEL_WORKERS + 5)

# Pool health monitoring
CONNECTION_TIMEOUT = 30  # seconds to wait for a connection before timeout
POOL_MONITORING_INTERVAL = 300  # check pool health every 5 minutes


class PostgreSQLClient:
    def __init__(self, db_config=None):
        """Initialize the PostgreSQL client with database configuration"""
        self.db_config = db_config or DB_CONFIG
        logger.info(
            f"Database connection: {self.db_config['dbname']} on {self.db_config['host']}:{self.db_config['port']} as {self.db_config['user']}")
        logger.info(
            f"Connection pool configured with min={MIN_CONNECTIONS}, max={MAX_CONNECTIONS} connections")

        # Initialize connection pool
        self._connection_pool = None
        self._init_connection_pool()

        # Track active connections for monitoring
        self._active_connections = 0
        self._connection_lock = threading.Lock()

        # Start pool monitoring in background
        self._start_pool_monitoring()

    def _init_connection_pool(self):
        """Initialize the connection pool"""
        try:
            self._connection_pool = pool.ThreadedConnectionPool(
                MIN_CONNECTIONS,
                MAX_CONNECTIONS,
                **self.db_config
            )
            logger.info(
                f"Connection pool created with min={MIN_CONNECTIONS}, max={MAX_CONNECTIONS} connections")
        except Exception as e:
            logger.error(f"Error creating connection pool: {e}")
            # Fall back to single connections if pool creation fails
            self._connection_pool = None

    def _start_pool_monitoring(self):
        """Start a background thread to monitor pool health"""
        def monitor_pool():
            while True:
                time.sleep(POOL_MONITORING_INTERVAL)
                with self._connection_lock:
                    logger.info(
                        f"Connection pool status: {self._active_connections} active connections")
                    # If too many active connections, consider expanding the pool
                    if self._active_connections > MAX_CONNECTIONS * 0.8:
                        logger.warning(
                            f"Connection pool utilization high: {self._active_connections}/{MAX_CONNECTIONS}")

        # Start monitoring thread
        monitor_thread = threading.Thread(target=monitor_pool, daemon=True)
        monitor_thread.start()

    def get_connection(self):
        """Get a connection to the database with timeout"""
        start_time = time.time()
        exception = None

        # Try to get a connection with exponential backoff
        backoff = 0.1
        max_backoff = 1.0

        while time.time() - start_time < CONNECTION_TIMEOUT:
            try:
                if self._connection_pool:
                    conn = self._connection_pool.getconn()
                    with self._connection_lock:
                        self._active_connections += 1
                    return conn
                else:
                    return psycopg2.connect(**self.db_config)
            except (psycopg2.pool.PoolError, Exception) as e:
                exception = e
                # Wait with exponential backoff
                time.sleep(min(backoff, max_backoff))
                backoff *= 1.5

        # If we got here, we timed out
        logger.error(
            f"Timed out getting database connection after {CONNECTION_TIMEOUT}s: {exception}")
        raise psycopg2.OperationalError(
            f"Connection pool timeout after {CONNECTION_TIMEOUT}s: {exception}")

    def release_connection(self, conn):
        """Return a connection to the pool"""
        if self._connection_pool and conn:
            try:
                self._connection_pool.putconn(conn)
                with self._connection_lock:
                    self._active_connections -= 1
            except Exception as e:
                logger.error(f"Error returning connection to pool: {e}")
                # Try to close the connection if we can't return it to the pool
                try:
                    conn.close()
                except:
                    pass

    def setup_database(self) -> None:
        """Create the necessary tables in the database if they don't exist"""
        conn = None
        cursor = None
        try:
            logger.info(f"Attempting to connect to database...")
            conn = self.get_connection()
            cursor = conn.cursor()

            # Check if table exists first
            cursor.execute(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'articles')")
            table_exists = cursor.fetchone()[0]

            if not table_exists:
                # Create articles table with the schema
                logger.info("Creating articles table...")
                cursor.execute("""
                    CREATE TABLE articles (
                        id SERIAL PRIMARY KEY,
                        proceeding_status TEXT NOT NULL DEFAULT 'Pending',
                        url TEXT UNIQUE NOT NULL,
                        domain TEXT,
                        title TEXT,
                        content TEXT,
                        pub_date TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        scraped_at TIMESTAMP,
                        error_message TEXT
                    )
                """)
                conn.commit()
                logger.info("Created articles table successfully")
            else:
                logger.info(
                    "Articles table already exists, keeping existing data")

            conn.commit()
            logger.info("Database setup completed successfully")

        except psycopg2.OperationalError as e:
            logger.error(f"Database connection error: {e}")
            logger.error(
                "Please ensure PostgreSQL is running and credentials are correct.")
            logger.error(
                f"Connection attempted with: host={self.db_config['host']}, port={self.db_config['port']}, dbname={self.db_config['dbname']}, user={self.db_config['user']}")
            raise
        except Exception as e:
            logger.error(f"Error setting up database: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.release_connection(conn)

    def store_article_url(self, article_data: Dict) -> bool:
        """
        Store article URL and metadata from RSS feed
        Sets proceeding_status to 'Pending' for later content scraping

        Args:
            article_data: Dictionary containing url, domain, title, and pub_date

        Returns:
            True if successful, False otherwise
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Insert article data from RSS feed
            cursor.execute("""
                INSERT INTO articles (
                    url, domain, title, pub_date, proceeding_status, created_at
                ) VALUES (
                    %s, %s, %s, %s, 'Pending', CURRENT_TIMESTAMP
                )
                ON CONFLICT (url) 
                DO UPDATE SET
                    domain = EXCLUDED.domain,
                    title = EXCLUDED.title,
                    pub_date = EXCLUDED.pub_date
                RETURNING id
            """, (
                article_data['url'],
                article_data['domain'],
                article_data['title'],
                article_data['pub_date']
            ))

            article_id = cursor.fetchone()[0]
            conn.commit()
            logger.info(
                f"Stored article URL: {article_data['title']} (ID: {article_id})")
            return article_id
        except Exception as e:
            logger.error(
                f"Error storing article URL {article_data.get('url')}: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.release_connection(conn)

    def update_article_content(self, article_id: int, content: str, error_message: Optional[str] = None, domain: Optional[str] = None) -> bool:
        """
        Update article with scraped content or error message

        Args:
            article_id: ID of the article to update
            content: Article content (can be None if scraping failed)
            error_message: Error message if scraping failed
            domain: Updated domain if article was redirected

        Returns:
            True if successful, False otherwise
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            if error_message:
                # Update with error message and mark as FAILED
                cursor.execute("""
                    UPDATE articles
                    SET proceeding_status = 'FAILED',
                        error_message = %s,
                        scraped_at = CURRENT_TIMESTAMP
                        {}
                    WHERE id = %s
                """.format("," + "domain = %s" if domain else ""),
                    (error_message, domain, article_id) if domain else (error_message, article_id))
                status = "FAILED"
            else:
                # Update with content and mark as ReadyForReview
                cursor.execute("""
                    UPDATE articles
                    SET proceeding_status = 'ReadyForReview',
                        content = %s,
                        scraped_at = CURRENT_TIMESTAMP
                        {}
                    WHERE id = %s
                """.format("," + "domain = %s" if domain else ""),
                    (content, domain, article_id) if domain else (content, article_id))
                status = "ReadyForReview"

            conn.commit()
            if domain:
                logger.info(
                    f"Updated article ID {article_id}: Status = {status}, Domain updated to {domain}")
            else:
                logger.info(
                    f"Updated article ID {article_id}: Status = {status}")
            return True
        except Exception as e:
            logger.error(f"Error updating article {article_id}: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.release_connection(conn)

    def get_pending_articles(self, limit: int = 100) -> list:
        """
        Get articles with 'Pending' status for content scraping

        Args:
            limit: Maximum number of articles to retrieve

        Returns:
            List of dictionaries containing article data
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, url, domain, title
                FROM articles
                WHERE proceeding_status = 'Pending'
                ORDER BY id ASC
                LIMIT %s
            """, (limit,))

            articles = []
            for row in cursor.fetchall():
                articles.append({
                    'id': row[0],
                    'url': row[1],
                    'domain': row[2],
                    'title': row[3]
                })

            logger.info(f"Retrieved {len(articles)} pending articles")
            return articles
        except Exception as e:
            logger.error(f"Error getting pending articles: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.release_connection(conn)

    def check_url_in_database(self, url: str) -> bool:
        """
        Check if a URL already exists in the database

        Args:
            url: URL to check

        Returns:
            True if URL exists, False otherwise
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT EXISTS(SELECT 1 FROM articles WHERE url = %s)",
                (url,)
            )
            return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error checking URL in database: {e}")
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.release_connection(conn)

    def check_urls_in_database(self, urls: List[str]) -> Dict[str, bool]:
        """
        Check if multiple URLs already exist in the database (batch operation)

        Args:
            urls: List of URLs to check

        Returns:
            Dictionary mapping each URL to a boolean indicating if it exists
        """
        if not urls:
            return {}

        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # If there are too many URLs, split into batches to avoid query limits
            batch_size = 1000  # Increase from default to boost performance
            url_exists_map = {}

            for i in range(0, len(urls), batch_size):
                batch_urls = urls[i:i+batch_size]

                # Use a VALUES expression for better performance with larger batches
                placeholders = ",".join([f"(%s)" for _ in batch_urls])
                query = f"""
                    WITH input_urls(url) AS (
                        VALUES {placeholders}
                    )
                    SELECT i.url, EXISTS(
                        SELECT 1 FROM articles a WHERE a.url = i.url
                    )
                    FROM input_urls i
                """

                # Flatten the list for the query parameters
                cursor.execute(query, batch_urls)

                # Add results to the map
                batch_results = {row[0]: row[1] for row in cursor.fetchall()}
                url_exists_map.update(batch_results)

            # Ensure all URLs are in the result map
            for url in urls:
                if url not in url_exists_map:
                    url_exists_map[url] = False

            return url_exists_map
        except Exception as e:
            logger.error(f"Error batch checking URLs in database: {e}")
            # Fall back to individual checks on error, but use a more efficient approach
            logger.info("Falling back to individual URL checks")

            # Create a more efficient fallback that still batches requests
            url_exists_map = {}
            try:
                # Try with smaller batches
                small_batch_size = 100
                for i in range(0, len(urls), small_batch_size):
                    small_batch = urls[i:i+small_batch_size]
                    for url in small_batch:
                        url_exists_map[url] = self.check_url_in_database(url)
                return url_exists_map
            except:
                # Last resort: one by one
                return {url: self.check_url_in_database(url) for url in urls}
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.release_connection(conn)

    def get_failed_domains(self) -> Dict[str, Dict[str, Any]]:
        """
        Get unique domains that had failed article processing along with their error messages

        Returns:
            Dictionary with domains as keys and a dictionary of error statistics as values
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Query to get unique domains with failed articles, including error messages and counts
            cursor.execute("""
                SELECT 
                    domain,
                    COUNT(*) as failed_count,
                    array_agg(DISTINCT error_message) as error_messages,
                    array_agg(id) as article_ids
                FROM articles
                WHERE proceeding_status = 'FAILED'
                GROUP BY domain
                ORDER BY failed_count DESC
            """)

            failed_domains = {}
            for row in cursor.fetchall():
                domain = row[0]
                count = row[1]
                error_messages = row[2]
                article_ids = row[3]

                # Create dictionary entry for this domain
                failed_domains[domain] = {
                    'failed_count': count,
                    'error_messages': error_messages,
                    # Limit to first 10 IDs to avoid huge output
                    'article_ids': article_ids[:10]
                }

            logger.info(
                f"Retrieved {len(failed_domains)} domains with failed articles")
            return failed_domains
        except Exception as e:
            logger.error(f"Error getting failed domains: {e}")
            return {}
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.release_connection(conn)

    def get_failed_articles(self, limit: int = 1000) -> list:
        """
        Get articles with 'FAILED' status for retry processing

        Args:
            limit: Maximum number of articles to retrieve

        Returns:
            List of dictionaries containing failed article data
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, url, domain, title, error_message
                FROM articles
                WHERE proceeding_status = 'FAILED'
                ORDER BY id ASC
                LIMIT %s
            """, (limit,))

            articles = []
            for row in cursor.fetchall():
                articles.append({
                    'id': row[0],
                    'url': row[1],
                    'domain': row[2],
                    'title': row[3],
                    'error_message': row[4]
                })

            logger.info(f"Retrieved {len(articles)} failed articles for retry")
            return articles
        except Exception as e:
            logger.error(f"Error getting failed articles: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.release_connection(conn)

    def get_article_by_url(self, url: str) -> Optional[Dict]:
        """
        Get article data for a specific URL

        Args:
            url: The URL of the article to retrieve

        Returns:
            Dictionary containing article data or None if not found
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, url, domain, title
                FROM articles
                WHERE url = %s
            """, (url,))

            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'url': row[1],
                    'domain': row[2],
                    'title': row[3]
                }

            logger.warning(f"Article not found for URL: {url}")
            return None
        except Exception as e:
            logger.error(f"Error getting article by URL {url}: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.release_connection(conn)
