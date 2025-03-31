"""
URL Extractor: Extracts article URLs from websites using multiple techniques.

Exported Functions:
- extract_article_urls(website_url: str, limit: int = 10) -> List[str]: Extracts article URLs from a website's homepage

Related Files:
- src/scraper/scraper_hooks/utils.py: Provides utility functions for HTTP requests and headers
- src/scraper/scraper_hooks/url_validator.py: Helps validate article URLs
- src/scraper/scraper_hooks/content_extractor.py: Used to extract content from URLs found by this module
"""
import newspaper
from typing import List, Set, Optional
import logging
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import re

# Import local modules
from .utils import make_request, get_random_user_agent, random_delay
from .url_validator import is_valid_article_url

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Check if Playwright is available
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logging.warning(
        "Playwright not installed. JavaScript-heavy sites may not be properly scraped.")


def _extract_urls_from_rss_feeds(website_url: str, base_url: str, feed_urls: List[str]) -> Set[str]:
    """
    Extract article URLs from RSS feeds

    Args:
        website_url: The main website URL
        base_url: The base domain URL
        feed_urls: List of RSS feed URLs to process

    Returns:
        Set of article URLs extracted from RSS feeds
    """
    rss_article_urls = set()

    for feed_url in feed_urls:
        try:
            logger.info(f"Processing RSS feed: {feed_url}")
            feed_response = make_request(feed_url)

            if not feed_response or feed_response.status_code != 200:
                continue

            # Parse the feed (supports both XML and Atom formats)
            feed_soup = BeautifulSoup(feed_response.text, 'xml')

            # Extract links from items (RSS) or entries (Atom)
            for item in feed_soup.find_all(['item', 'entry']):
                # Try different ways RSS feeds might provide links
                link = None

                # Option 1: <link> element with URL as text content
                link_tag = item.find('link')
                if link_tag and link_tag.string:
                    link = link_tag.string.strip()

                # Option 2: <link> element with href attribute (Atom)
                elif link_tag and link_tag.get('href'):
                    link = link_tag.get('href').strip()

                # Option 3: <guid> element that might contain the URL
                elif item.find('guid'):
                    guid = item.find('guid').string.strip()
                    if guid.startswith('http'):
                        link = guid

                # If we found a link, validate and add it
                if link:
                    full_url = urljoin(website_url, link)
                    if is_valid_article_url(full_url, base_url):
                        rss_article_urls.add(full_url)

            logger.info(
                f"Found {len(rss_article_urls)} article URLs from RSS feed {feed_url}")

        except Exception as e:
            logger.warning(f"Error processing RSS feed {feed_url}: {e}")

    return rss_article_urls


def _extract_urls_with_playwright(website_url: str, base_url: str) -> Set[str]:
    """
    Extract article URLs using Playwright for JavaScript-rendered websites

    Args:
        website_url: The website URL to extract from
        base_url: The base domain URL for validation

    Returns:
        Set of article URLs extracted using Playwright
    """
    if not PLAYWRIGHT_AVAILABLE:
        logger.warning(
            "Playwright not available. Skipping JavaScript extraction.")
        return set()

    playwright_urls = set()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=get_random_user_agent(),
                viewport={'width': 1280, 'height': 720}
            )

            page = context.new_page()
            page.set_default_timeout(20000)  # 20 seconds timeout

            logger.info(f"Loading {website_url} with Playwright")
            page.goto(website_url, wait_until="domcontentloaded")

            # Wait a moment for dynamic content to load
            page.wait_for_timeout(2000)

            # Scroll down to trigger lazy loading
            page.evaluate("""
                window.scrollTo(0, document.body.scrollHeight/2);
                setTimeout(() => { window.scrollTo(0, document.body.scrollHeight); }, 1000);
            """)

            # Wait for any additional content to load
            page.wait_for_timeout(2000)

            # Extract all links
            links = page.eval_all_handles(
                "Array.from(document.querySelectorAll('a[href]'))")

            for link_handle in links:
                try:
                    url = link_handle.evaluate("link => link.href")
                    if url and is_valid_article_url(url, base_url):
                        playwright_urls.add(url)
                except Exception:
                    pass
                finally:
                    link_handle.dispose()

            browser.close()

            logger.info(
                f"Found {len(playwright_urls)} article URLs using Playwright")

    except Exception as e:
        logger.error(f"Error using Playwright: {e}")

    return playwright_urls


def extract_article_urls(website_url: str, limit: int = 10) -> List[str]:
    """
    Extract article URLs from a website's homepage using multiple techniques

    Args:
        website_url: URL of the website homepage
        limit: Maximum number of URLs to extract

    Returns:
        List of article URLs
    """
    all_urls = set()  # Use a set to avoid duplicates

    try:
        logger.info(f"Extracting article URLs from {website_url}")

        # Use our custom request method for the initial fetch
        response = make_request(website_url)
        if not response:
            logger.error(f"Failed to fetch {website_url}")
            return []

        # Parse domain information
        parsed_url = urlparse(website_url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

        # Method 1: Use newspaper's built-in article extraction
        try:
            # Configure newspaper with random user agent
            newspaper.Config().browser_user_agent = get_random_user_agent()
            newspaper.Config().fetch_images = False  # Skip image fetching for performance

            # Build the site from the URL
            site = newspaper.build(website_url, memoize_articles=False)

            # Find RSS feeds and extract articles from them first
            feed_urls = site.feed_urls()
            if feed_urls:
                logger.info(f"Found {len(feed_urls)} RSS feeds")
                rss_urls = _extract_urls_from_rss_feeds(
                    website_url, base_url, feed_urls)
                all_urls.update(rss_urls)
                logger.info(f"Found {len(rss_urls)} URLs from RSS feeds")

            # If we have sufficient URLs from RSS feeds, we might skip other methods
            if len(all_urls) >= limit:
                logger.info(
                    f"Found sufficient URLs from RSS feeds: {len(all_urls)}")
                return list(all_urls)[:limit]

            # Get article URLs from newspaper
            newspaper_urls = [article.url for article in site.articles]
            logger.info(f"Found {len(newspaper_urls)} URLs using newspaper")

            # Add valid URLs to our collection
            for url in newspaper_urls:
                if is_valid_article_url(url, base_url):
                    all_urls.add(url)
        except Exception as e:
            logger.error(f"Error using newspaper extraction: {e}")

        # Method 2: Use BeautifulSoup for additional HTML analysis
        try:
            soup = BeautifulSoup(response.text, 'html.parser')

            # 2a. Look for semantic HTML5 elements that typically contain articles
            semantic_elements = soup.find_all(['article', 'section', 'main'])
            for element in semantic_elements:
                links = element.find_all('a', href=True)
                for link in links:
                    href = link.get('href')
                    if href:
                        full_url = urljoin(website_url, href)
                        if is_valid_article_url(full_url, base_url):
                            all_urls.add(full_url)

            # 2b. Check for links with certain text patterns
            article_link_texts = [
                'read more', 'full article', 'continue reading', 'read article']
            for link in soup.find_all('a', href=True):
                link_text = link.text.lower().strip()
                if any(pattern in link_text for pattern in article_link_texts):
                    href = link.get('href')
                    full_url = urljoin(website_url, href)
                    if is_valid_article_url(full_url, base_url):
                        all_urls.add(full_url)

            # 2c. Look for heading elements which often link to articles
            for heading in soup.find_all(['h1', 'h2', 'h3']):
                links = heading.find_all('a', href=True)
                for link in links:
                    href = link.get('href')
                    if href:
                        full_url = urljoin(website_url, href)
                        if is_valid_article_url(full_url, base_url):
                            all_urls.add(full_url)

            # Find all links within other article containers
            container_patterns = [
                'article', 'post', 'story', 'entry', 'news-item', 'content',
                'main-content', 'container', 'news', 'blog', 'featured'
            ]

            for pattern in container_patterns:
                containers = soup.find_all(
                    class_=lambda c: c and pattern.lower() in c.lower())
                containers.extend(soup.find_all(
                    id=lambda i: i and pattern.lower() in i.lower()))

                for container in containers:
                    container_links = container.find_all('a', href=True)
                    for link in container_links:
                        href = link.get('href')
                        if href:
                            full_url = urljoin(website_url, href)
                            if is_valid_article_url(full_url, base_url):
                                all_urls.add(full_url)

            logger.info(
                f"Found {len(all_urls)} total URLs after HTML analysis")

        except Exception as e:
            logger.error(f"Error using BeautifulSoup extraction: {e}")

        # Method 3: Use Playwright for JavaScript-heavy sites if we have few URLs
        if len(all_urls) < 5 and PLAYWRIGHT_AVAILABLE:
            logger.info(
                "Few URLs found. Trying Playwright for JavaScript-rendered sites")
            playwright_urls = _extract_urls_with_playwright(
                website_url, base_url)
            all_urls.update(playwright_urls)

        # Convert set to list and limit the number of URLs
        urls_list = list(all_urls)[:limit]

        logger.info(
            f"Extracted {len(urls_list)} article URLs from {website_url}")
        return urls_list

    except Exception as e:
        logger.error(f"Error extracting URLs from {website_url}: {e}")
        return []
