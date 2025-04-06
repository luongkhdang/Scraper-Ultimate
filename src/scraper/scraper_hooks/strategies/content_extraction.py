"""
Content Extraction Module

This module provides functions for extracting article content from web pages using
various selector strategies and fallback methods for handling different site structures.

Exported Functions:
- extract_content(page, content_selectors, min_content_chars=800, min_content_words=100) -> str: 
    Extract content from a page using provided or default selectors
- is_content_too_short(content, min_chars=800, min_words=100) -> bool:
    Check if extracted content meets minimum length requirements

Related Files:
- src/scraper/scraper_hooks/strategies/special_strategy.py: Main scraping strategy
- src/scraper/scraper_hooks/strategies/page_state_capture.py: For capturing page state 

Dependencies:
- playwright: For page manipulation and content extraction
"""

import logging
import random
from typing import List, Optional, Any

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Default content selectors for fallback
DEFAULT_CONTENT_SELECTORS = [
    'article', '.article', 'main', '.post-content', '.article-content',
    '.entry-content', '.content', '[itemprop="articleBody"]',
    '.article-body', '.story-body', '.story', '.post-body',
    '[data-testid="article-content"]', '.meteredContent',
    '.article__body', '.article-wrap', '.bigTop__article'
]

# Minimum content length constants
MIN_CONTENT_CHARS = 800
MIN_CONTENT_WORDS = 100
MIN_PARAGRAPH_CHARS = 30
MIN_SUBSTANTIAL_PARAGRAPH_CHARS = 40


def is_content_too_short(content: str, min_chars: int = MIN_CONTENT_CHARS,
                         min_words: int = MIN_CONTENT_WORDS) -> bool:
    """
    Check if content meets minimum length requirements

    Args:
        content: The extracted content string
        min_chars: Minimum required character count
        min_words: Minimum required word count

    Returns:
        bool: True if content is too short, False otherwise
    """
    if not content:
        return True

    # Check character length
    if len(content) < min_chars:
        # Secondary check with word count
        word_count = len(content.split())
        if word_count < min_words:
            logger.warning(
                f"Content too short: {len(content)} chars, {word_count} words")
            return True

    return False


async def extract_content(page, content_selectors=None, min_content_chars=MIN_CONTENT_CHARS,
                          min_content_words=MIN_CONTENT_WORDS, capture_page_state_fn=None) -> str:
    """
    Extract article content from the page

    Args:
        page: Playwright page object
        content_selectors: Optional list of CSS selectors to use for content extraction
        min_content_chars: Minimum required character count for content
        min_content_words: Minimum required word count for content
        capture_page_state_fn: Optional function to capture page state for debugging

    Returns:
        str: Extracted content or empty string if extraction failed
    """
    # Use provided selectors or fall back to default ones
    selectors = content_selectors or DEFAULT_CONTENT_SELECTORS
    content = ""

    for selector in selectors:
        try:
            elements = await page.query_selector_all(selector)

            if elements:
                for element in elements:
                    # Try getting all paragraphs inside
                    paragraphs = await element.query_selector_all('p')

                    if paragraphs and len(paragraphs) >= 3:
                        paragraph_texts = []
                        for p in paragraphs:
                            text = await p.text_content()
                            text = text.strip()
                            # Skip very short paragraphs
                            if text and len(text) > MIN_PARAGRAPH_CHARS:
                                paragraph_texts.append(text)

                        element_content = '\n\n'.join(paragraph_texts)
                        if element_content and len(element_content) > 300:
                            content = element_content
                            break
                    else:
                        # If no paragraphs, try raw text content
                        text = await element.text_content()
                        text = text.strip()
                        if text and len(text) > 300:
                            content = text
                            break
        except Exception as e:
            logger.debug(f"Error with selector {selector}: {e}")
            continue

        if content:
            break

    # If no content found, try a more aggressive fallback method
    if not content or len(content) < 300:
        try:
            # Get all paragraphs from the page
            all_paragraphs = await page.query_selector_all('p')
            paragraph_texts = []

            for p in all_paragraphs:
                try:
                    text = await p.text_content()
                    text = text.strip()
                    # Only include substantial paragraphs
                    if text and len(text) > MIN_SUBSTANTIAL_PARAGRAPH_CHARS:
                        paragraph_texts.append(text)
                except Exception:
                    continue

            # Join paragraphs
            if paragraph_texts:
                content = '\n\n'.join(paragraph_texts)
        except Exception as e:
            logger.error(f"Error in fallback content extraction: {e}")

    # If a capture function was provided, capture page state based on content
    if capture_page_state_fn:
        if not content or len(content) < min_content_chars:
            await capture_page_state_fn(page, page.url, False, 0, "content_extraction_failed")
        elif random.random() < 0.1:  # Only capture 10% of successful extractions
            await capture_page_state_fn(page, page.url, True, 0, "successful_extraction")

    return content


async def wait_for_content_selectors(page, content_selectors: List[str], timeout: int = 5000) -> bool:
    """
    Wait for any content selector to be visible on the page

    Args:
        page: Playwright page object 
        content_selectors: List of CSS selectors to try
        timeout: Maximum time to wait (ms)

    Returns:
        bool: True if any selector was found visible, False otherwise
    """
    try:
        # Only try the first few selectors to avoid excessive waiting
        for selector in content_selectors[:3]:
            try:
                await page.wait_for_selector(selector, timeout=timeout, state="visible")
                logger.info(
                    f"Found visible content using selector: {selector}")
                return True
            except:
                continue
    except Exception as e:
        logger.warning(f"Error waiting for content selectors: {e}")

    logger.warning("No content selectors found, continuing without waiting")
    return False
