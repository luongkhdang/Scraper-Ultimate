"""
Demo Script: Shows how to use the modular web scraper with the two-phase approach.

Phase 1: Extract article URLs from website homepages and RSS feeds
Phase 2: Extract content from those article URLs
"""
import logging
import json
from typing import List, Dict, Any
from pathlib import Path
from scraper_client import ScraperClient

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def save_to_json(data: Any, filename: str) -> None:
    """Save data to a JSON file"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved data to {filename}")


def demo_scraper(target_websites: List[str], output_dir: str = "output", max_urls_per_site: int = 5, max_articles: int = 3) -> None:
    """
    Demonstrates the two-phase scraping approach

    Args:
        target_websites: List of website URLs to scrape
        output_dir: Directory to save output files
        max_urls_per_site: Maximum number of article URLs to extract per website
        max_articles: Maximum number of articles to extract content from per website
    """
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(exist_ok=True)

    # Initialize the scraper client
    scraper = ScraperClient()

    # Process each target website
    for website_url in target_websites:
        logger.info(f"=== Processing website: {website_url} ===")

        # Phase 1: Extract article URLs
        article_urls = scraper.extract_article_urls(
            website_url, limit=max_urls_per_site)
        logger.info(
            f"Found {len(article_urls)} article URLs from {website_url}")

        # Save the URLs to a JSON file
        domain = website_url.replace(
            "https://", "").replace("http://", "").split("/")[0]
        urls_filename = f"{output_dir}/{domain}_urls.json"
        save_to_json(article_urls, urls_filename)

        # Phase 2: Extract content from a subset of the URLs
        articles = []
        for i, article_url in enumerate(article_urls[:max_articles]):
            logger.info(
                f"Processing article {i+1}/{min(max_articles, len(article_urls))}: {article_url}")
            article_data = scraper.extract_article_content(article_url)

            if article_data:
                articles.append(article_data)
                logger.info(
                    f"Successfully extracted content: {article_data['title']}")
            else:
                logger.warning(f"Failed to extract content from {article_url}")

        # Save the articles to a JSON file
        articles_filename = f"{output_dir}/{domain}_articles.json"
        save_to_json(articles, articles_filename)

        logger.info(f"=== Completed processing website: {website_url} ===")


if __name__ == "__main__":
    # List of websites to scrape
    websites = [
        "https://news.ycombinator.com/",
        "https://techcrunch.com/",
        "https://www.theverge.com/"
    ]

    # Run the demo
    demo_scraper(websites)
