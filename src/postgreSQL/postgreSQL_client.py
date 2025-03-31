"""
PostgreSQL Database Client: Handles database connections and operations for the scraper.

Exported Functions:
- setup_database() -> None: Sets up required database tables
- store_article(article_data: Dict) -> bool: Stores article data in the database
- check_url_in_database(url: str) -> bool: Checks if a URL exists in the database

Related Files:
- main.py: Main orchestration file that uses this client
- scraper/scraper_client.py: Provides the ScraperClient class for scraping
"""
import os
import sys
import logging
import psycopg2
from psycopg2.extras import Json
from typing import Dict, Optional, Any
from dotenv import load_dotenv

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


class PostgreSQLClient:
    def __init__(self, db_config=None):
        """Initialize the PostgreSQL client with database configuration"""
        self.db_config = db_config or DB_CONFIG
        logger.info(
            f"Database connection: {self.db_config['dbname']} on {self.db_config['host']}:{self.db_config['port']} as {self.db_config['user']}")

    def get_connection(self):
        """Get a connection to the database"""
        return psycopg2.connect(**self.db_config)

    def setup_database(self) -> None:
        """Create the necessary tables in the database if they don't exist"""
        conn = None
        cursor = None
        try:
            logger.info(f"Attempting to connect to database...")
            conn = self.get_connection()
            cursor = conn.cursor()

            # Drop the articles table if it exists to ensure clean structure
            cursor.execute("DROP TABLE IF EXISTS articles")
            logger.info("Dropped existing articles table")

            # Create articles table with exactly the specified columns
            cursor.execute("""
                CREATE TABLE articles (
                    id SERIAL PRIMARY KEY,
                    url TEXT UNIQUE NOT NULL,
                    title TEXT,
                    content TEXT,
                    authors JSONB,
                    published_date TIMESTAMP,
                    scraped_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()
            logger.info("Database setup completed with clean schema")

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
                conn.close()

    def store_article(self, article_data: Dict) -> bool:
        """Store an article in the database"""
        conn = None
        cursor = None
        try:
            # Skip articles with content less than 80 characters
            if not article_data.get('content') or len(article_data['content']) < 80:
                logger.info(
                    f"Skipping article with insufficient content: {article_data.get('title', 'Untitled')}")
                return False

            conn = self.get_connection()
            cursor = conn.cursor()

            # Insert article data - only using the specified columns
            cursor.execute("""
                INSERT INTO articles (
                    url, title, content, authors, published_date, scraped_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (url) 
                DO UPDATE SET
                    title = EXCLUDED.title,
                    content = EXCLUDED.content,
                    authors = EXCLUDED.authors,
                    published_date = EXCLUDED.published_date,
                    scraped_at = EXCLUDED.scraped_at
            """, (
                article_data['url'],
                article_data['title'],
                article_data['content'],
                Json(article_data['authors']
                     ) if article_data['authors'] else None,
                article_data['published_date'],
                article_data['scraped_at']
            ))

            conn.commit()
            logger.info(f"Stored article: {article_data['title']}")
            return True
        except Exception as e:
            logger.error(
                f"Error storing article {article_data.get('url')}: {e}")
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def check_url_in_database(self, url: str) -> bool:
        """Check if an article URL exists in the database"""
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Check if URL exists
            cursor.execute(
                "SELECT 1 FROM articles WHERE url = %s LIMIT 1", (url,))
            exists = cursor.fetchone() is not None

            return exists
        except Exception as e:
            logger.error(f"Error checking URL {url} in database: {e}")
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
