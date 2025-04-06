"""
Special URL Handlers Module

This module handles special URL types like Google News and BizToc that need custom processing
before content extraction. These URLs typically redirect or contain references to target content.

Exported Functions:
- handle_special_url(page, url) -> str: Process special URL types and return final destination URL
- detect_biztoc_url(url) -> bool: Detect if a URL is from BizToc aggregator
- detect_google_news_url(url) -> bool: Detect if a URL is from Google News

Related Files:
- src/scraper/scraper_hooks/strategies/special_strategy.py: Main special strategy that uses these handlers
- src/scraper/scraper_hooks/content_extractor.py: Content extraction pipeline

Dependencies:
- playwright: For browser automation and navigation
- urllib.parse: For URL parsing
"""

import logging
from urllib.parse import urlparse
import asyncio

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def detect_biztoc_url(url):
    """
    Detect if a URL is from BizToc content aggregator

    Args:
        url: The URL to check

    Returns:
        bool: True if this is a BizToc URL, False otherwise
    """
    domain = urlparse(url).netloc.lower()
    return 'biztoc.com' in domain


def detect_google_news_url(url):
    """
    Detect if a URL is from Google News

    Args:
        url: The URL to check

    Returns:
        bool: True if this is a Google News URL, False otherwise
    """
    domain = urlparse(url).netloc.lower()
    return 'news.google.com' in domain


async def handle_biztoc_url(page, url):
    """
    Handle BizToc URLs by extracting the original source URL

    Args:
        page: Playwright page object
        url: The BizToc URL

    Returns:
        str: The extracted original URL or the input URL if extraction fails
    """
    final_url = url

    try:
        logger.info("BizToc URL detected, extracting original URL")
        await page.goto(url, timeout=30000, wait_until='domcontentloaded')

        # Look for the original URL element
        await page.wait_for_selector('.urlbox.drops.text-mono', timeout=10000)

        # Extract the original URL
        original_url = await page.evaluate("""
            () => {
                // Try to find the link with the class
                const linkElement = document.querySelector('a.urlbox.drops.text-mono');
                if (linkElement && typeof linkElement.href === 'string') {
                    return linkElement.href;
                }

                // Fallback to span inside anchor
                const spanElement = document.querySelector('span.urlbox.drops.text-mono');
                if (spanElement && spanElement.closest && typeof spanElement.closest === 'function') {
                    const anchorElement = spanElement.closest('a');
                    if (anchorElement && typeof anchorElement.href === 'string') {
                        return anchorElement.href;
                    }
                }

                return null;
            }
        """)

        if original_url:
            logger.info(f"Found original URL on BizToc: {original_url}")
            final_url = original_url
    except Exception as e:
        logger.error(f"Error handling BizToc URL: {e}")

    return final_url


async def handle_google_news_url(page, url):
    """
    Handle Google News URLs by following redirects to original source

    Args:
        page: Playwright page object
        url: The Google News URL

    Returns:
        str: The final URL after redirect or the input URL if handling fails
    """
    final_url = url

    try:
        logger.info("Google News URL detected, handling redirects")
        await page.goto(url, timeout=30000, wait_until='domcontentloaded')

        # Wait for redirect to happen
        await page.wait_for_timeout(5000)

        # Get the redirected URL
        redirected_url = page.url

        # Check if we were redirected
        if redirected_url != url:
            logger.info(f"Google News redirected to: {redirected_url}")
            final_url = redirected_url
    except Exception as e:
        logger.error(f"Error handling Google News URL: {e}")

    return final_url


async def handle_special_url(page, url):
    """
    Main function to handle special URL types

    Args:
        page: Playwright page object
        url: The URL to process

    Returns:
        str: The final URL after processing
    """
    # Parse domain for special handling
    domain = urlparse(url).netloc.lower()
    final_url = url

    # Handle Google News URLs
    if 'news.google.com' in domain:
        final_url = await handle_google_news_url(page, url)
    # Handle BizToc URLs
    elif 'biztoc.com' in domain:
        final_url = await handle_biztoc_url(page, url)

    return final_url
