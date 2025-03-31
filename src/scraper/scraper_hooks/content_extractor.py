"""
Content Extractor: Extracts article content from URLs with multiple fallback methods.

Exported Functions:
- extract_article_content(article_url: str, referrer: str = None) -> Optional[Dict[str, Any]]: Extracts content from an article URL

Related Files:
- src/scraper/scraper_hooks/utils.py: Provides utility functions for HTTP requests
- src/scraper/scraper_hooks/url_extractor.py: Provides URLs for this module to process
"""
import newspaper
from typing import Dict, Optional, Any
import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse
from bs4 import BeautifulSoup

# Import local modules
from .utils import make_request, get_random_user_agent, get_realistic_headers, random_delay, get_referrer

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Check if Playwright is available for fallback extraction
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logging.warning(
        "Playwright not installed. JavaScript-heavy sites may not be properly scraped.")

# A dictionary to track domains with old articles
domains_with_old_articles = {}  # domain -> count of old articles


def _configure_newspaper():
    """Configure newspaper with optimal settings"""
    config = newspaper.Config()
    config.browser_user_agent = get_random_user_agent()
    config.request_timeout = 10
    config.memoize_articles = False  # Disable caching to get fresh content
    config.fetch_images = False  # Skip image fetching for better performance
    return config


def _extract_with_playwright(article_url: str, user_agent: str) -> Optional[str]:
    """Extract article content using Playwright as a fallback method"""
    if not PLAYWRIGHT_AVAILABLE:
        return None

    content = None

    try:
        logger.info(f"Trying Playwright for {article_url}")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=user_agent)
            page = context.new_page()

            # Navigate to the URL
            page.goto(article_url, wait_until="domcontentloaded")
            # Wait for JS to execute
            page.wait_for_timeout(3000)

            # Try to find the article content
            content_selectors = [
                'article', 'main', '.post-content', '.article-content',
                '.entry-content', '.content', '[itemprop="articleBody"]'
            ]

            content = ""
            for selector in content_selectors:
                try:
                    element = page.query_selector(selector)
                    if element:
                        # Get all paragraphs inside this element
                        paragraphs = page.eval_all_handles(
                            f"Array.from(document.querySelector('{selector}').querySelectorAll('p'))")

                        paragraph_texts = []
                        for p in paragraphs:
                            text = p.evaluate("p => p.textContent.trim()")
                            # Skip short paragraphs
                            if text and len(text) > 20:
                                paragraph_texts.append(text)
                            p.dispose()

                        # Join paragraphs with double newlines
                        content = '\n\n'.join(paragraph_texts)
                        if content and len(content) > 200:
                            break
                except Exception:
                    continue

            browser.close()

            if content and len(content) > 200:
                logger.info(
                    f"Successfully extracted content using Playwright for {article_url}")

    except Exception as e:
        logger.error(f"Error using Playwright fallback: {e}")

    return content


def _extract_with_soup(response_text: str) -> Optional[str]:
    """Extract article content using BeautifulSoup as a fallback method"""
    try:
        soup = BeautifulSoup(response_text, 'html.parser')

        # Try to find the main content container
        main_content = None

        # Look for common article content containers
        for container_selector in ['article', 'main', '.post-content', '.article-content', '.entry-content', '.content']:
            if container_selector.startswith('.'):
                # Class selector
                elements = soup.find_all(class_=container_selector[1:])
            else:
                # Tag selector
                elements = soup.find_all(container_selector)

            for el in elements:
                # Reasonable length for article content
                if len(el.get_text(strip=True)) > 200:
                    main_content = el
                    break

            if main_content:
                break

        # If we found a content container, extract text from paragraphs
        if main_content:
            # Extract paragraphs from the main content
            paragraphs = main_content.find_all('p')

            # Join paragraphs with double newlines for readability
            content = '\n\n'.join([p.get_text(strip=True) for p in paragraphs
                                   # Skip short paragraphs
                                   if len(p.get_text(strip=True)) > 20])

            # If we found substantial content, return it
            if content and len(content) > 200:
                return content

    except Exception as e:
        logger.error(f"Error using BeautifulSoup fallback: {e}")

    return None


def extract_article_content(article_url: str, referrer: str = None) -> Optional[Dict[str, Any]]:
    """
    Extract content from an article URL

    Args:
        article_url: URL of the article to extract
        referrer: Optional referrer URL (if None, a random one will be used)

    Returns:
        Dictionary containing article details or None if extraction fails
    """
    try:
        logger.info(f"Extracting content from {article_url}")

        # Get domain from URL to track old articles
        domain = urlparse(article_url).netloc

        # Skip if we've already found 3 old articles from this domain
        if domain in domains_with_old_articles and domains_with_old_articles[domain] >= 3:
            logger.info(
                f"Skipping domain {domain} because too many old articles were found")
            return None

        # Use realistic referrer
        if not referrer:
            referrer = get_referrer()

        # Configure newspaper with random user agent
        user_agent = get_random_user_agent()
        newspaper.Config().browser_user_agent = user_agent
        newspaper.Config().fetch_images = False  # Skip image fetching for performance

        article = newspaper.Article(article_url)

        # Instead of using article.download(), use our custom request method
        headers = get_realistic_headers(article_url)
        headers["Referer"] = referrer

        # Add a random delay to mimic human behavior before downloading
        random_delay()

        # Use our custom method for downloading
        response = make_request(article_url, headers=headers)
        if response:
            article.download(input_html=response.text)
        else:
            article.download()

        # Add another random delay before parsing (as if a human is reading)
        random_delay(2.0, 7.0)

        article.parse()
        article.nlp()  # Natural language processing for keywords and summary

        # Check if the article is older than 3 days
        three_days_ago = datetime.now() - timedelta(days=3)

        if article.publish_date and article.publish_date < three_days_ago:
            # Increment the count of old articles for this domain
            if domain in domains_with_old_articles:
                domains_with_old_articles[domain] += 1
            else:
                domains_with_old_articles[domain] = 1

            logger.info(
                f"Found old article from {domain} (count: {domains_with_old_articles[domain]})")

            # If we've found 3 old articles, log the info
            if domains_with_old_articles[domain] >= 3:
                logger.info(
                    f"Will stop fetching from {domain} due to old articles")

        # Create article data with additional browser-like metadata
        article_data = {
            'url': article_url,
            'title': article.title,
            'content': article.text,
            'authors': article.authors,
            'published_date': article.publish_date.isoformat() if article.publish_date else None,
            'scraped_at': datetime.now().isoformat()
        }

        # Fallback for when newspaper3k fails to extract content properly
        if not article.text or len(article.text) < 100:
            logger.warning(
                f"Article extraction may have failed for {article_url}. Using fallback methods")

            # Try BeautifulSoup fallback
            if response:
                soup_content = _extract_with_soup(response.text)
                if soup_content:
                    article_data['content'] = soup_content
                    logger.info(
                        f"Successfully extracted content using BeautifulSoup fallback for {article_url}")

            # If BeautifulSoup fallback didn't work, try Playwright
            if (not article_data['content'] or len(article_data['content']) < 200):
                playwright_content = _extract_with_playwright(
                    article_url, user_agent)
                if playwright_content:
                    article_data['content'] = playwright_content

        logger.info(f"Successfully extracted content from {article_url}")
        return article_data

    except Exception as e:
        logger.error(f"Error extracting content from {article_url}: {e}")
        return None
