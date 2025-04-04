"""
Content Extractor: Extracts article content from URLs with multiple fallback methods.

Exported Functions:
- extract_article_content(article_url: str, referrer: str = None) -> Optional[Dict[str, Any]]: Extracts content from an article URL

Related Files:
- src/scraper/scraper_hooks/utils.py: Provides utility functions for HTTP requests
- src/scraper/scraper_hooks/url_extractor.py: Provides URLs for this module to process
"""
import newspaper
from typing import Dict, Optional, Any, Tuple, List
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import re
import time

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

# List of blocked domains to skip
blocked_domains: List[str] = [
    "bloomberg.com",
    "wsj.com",
    "ft.com",
    "nytimes.com",
    "economist.com",
    "thehill.com",
    "businessinsider.com",
    "axion.com",
    "politico.com",
]

# Constants for content validation
MIN_CONTENT_CHARS = 800    # Minimum characters for a full article
MIN_CONTENT_WORDS = 100    # Minimum words for a full article
MIN_ELEMENT_CONTENT_CHARS = 200  # Minimum chars for a content element
MIN_PARAGRAPH_CHARS = 20   # Minimum chars for a valid paragraph
# Minimum chars for a substantial paragraph
MIN_SUBSTANTIAL_PARAGRAPH_CHARS = 50

# Content validation thresholds


class ContentThreshold:
    """Content validation thresholds for different content types"""
    FULL_ARTICLE = MIN_CONTENT_CHARS  # Full article validation
    # Content blocks (article, main, sections)
    CONTENT_ELEMENT = MIN_ELEMENT_CONTENT_CHARS
    PARAGRAPH = MIN_PARAGRAPH_CHARS  # Regular paragraphs
    SUBSTANTIAL_PARAGRAPH = MIN_SUBSTANTIAL_PARAGRAPH_CHARS  # More important paragraphs


def _make_http_request(url: str, custom_user_agent: str = None, custom_referrer: str = None, extra_headers: Dict[str, str] = None) -> Optional[Any]:
    """
    Make an HTTP request with standardized headers and error handling.

    Args:
        url: The URL to request
        custom_user_agent: Optional specific user agent to use (if None, a random one is selected)
        custom_referrer: Optional referrer URL (if None, a generic one may be used)
        extra_headers: Optional additional headers to include

    Returns:
        Response object or None if request failed
    """
    # Get realistic headers with optional custom referrer
    headers = get_realistic_headers(url, referrer=custom_referrer)

    # Add or override with custom user agent if provided
    if custom_user_agent:
        headers["User-Agent"] = custom_user_agent

    # Add any extra headers
    if extra_headers:
        headers.update(extra_headers)

    # Make the request with proper error handling
    try:
        logger.debug(f"Making HTTP request to {url}")
        return make_request(url, headers=headers)
    except Exception as e:
        logger.error(f"HTTP request failed for {url}: {e}")
        return None


def _is_blocked_domain(url_or_domain: str) -> bool:
    """
    Check if a URL or domain is in the blocked domains list

    Args:
        url_or_domain: Either a full URL or just a domain string

    Returns:
        True if the domain is blocked, False otherwise
    """
    # Extract domain if a full URL was passed
    domain = url_or_domain
    if '://' in url_or_domain:
        domain = urlparse(url_or_domain).netloc.lower()
    else:
        domain = domain.lower()

    # Check against blocked domains list
    for blocked_domain in blocked_domains:
        if blocked_domain in domain:
            logger.info(f"Blocked domain detected: {domain}")
            return True

    return False


def _follow_redirect(url: str) -> Tuple[str, str]:
    """Follow URL redirects and return the final destination URL and domain

    This is particularly useful for RSS feed links that redirect to the actual article

    Args:
        url: The URL that may contain a redirect

    Returns:
        Tuple containing (final_url, final_domain) after following all redirects
    """
    try:
        logger.info(f"Following redirects for {url}")

        # Handle special cases for known redirect patterns
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        final_domain = domain  # Initialize with original domain

        # BizToc redirects
        if "biztoc.com" in domain:
            logger.info(
                "Detected BizToc URL, looking for original article link")

            response = _make_http_request(url)

            if response and response.text:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Look for the specific class that contains the original URL as shown in the screenshot
                url_box = soup.find('a', class_='urlbox drops text-mono')
                if url_box and url_box.get('href'):
                    source_url = url_box.get('href')
                    logger.info(
                        f"Found original URL in urlbox: {source_url} ")
                    final_domain = urlparse(source_url).netloc.lower()
                    return source_url, final_domain

                # Fallback - check for href in span with the same class if 'a' tag not found
                url_box_span = soup.find(
                    'span', class_='urlbox drops text-mono')
                if url_box_span:
                    parent_link = url_box_span.find_parent('a')
                    if parent_link and parent_link.get('href'):
                        source_url = parent_link.get('href')
                        logger.info(
                            f"Found original URL in urlbox span parent: {source_url} ")
                        final_domain = urlparse(source_url).netloc.lower()
                        return source_url, final_domain

            # If we couldn't find the URL box, use the original URL
            logger.warning(
                "Couldn't find original URL on BizToc page, using original URL")

        # Google News redirects
        elif "news.google.com" in domain and "/articles/" in url:
            logger.info("Detected Google News redirect URL")
            # Google News needs special handling for redirect extraction
            custom_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

            response = _make_http_request(
                url, custom_user_agent=custom_user_agent)

            if response and response.status_code in (301, 302, 303, 307, 308):
                redirect_url = response.headers.get('Location')
                if redirect_url:
                    logger.info(f"Google News redirecting to: {redirect_url}")
                    final_domain = urlparse(redirect_url).netloc.lower()
                    return redirect_url, final_domain

            # If no redirect in headers, try to extract from content
            if response and response.text:
                soup = BeautifulSoup(response.text, 'html.parser')
                # Google News has a canonical link or redirect URL in the HTML
                redirect_link = soup.find('a', attrs={'jsname': 'tljFtd'})
                if redirect_link:
                    href = redirect_link.get('href')
                    if href:
                        if href.startswith('./'):
                            href = f"https://news.google.com{href[1:]}"
                        logger.info(
                            f"Found redirect link in Google News page: {href} ")
                        final_domain = urlparse(href).netloc.lower()
                        return href, final_domain

                # Look for other possible redirect links
                all_links = soup.find_all('a')
                for link in all_links:
                    href = link.get('href')
                    if href and ('http' in href) and ('google.com' not in href):
                        logger.info(
                            f"Found potential news source link: {href}")
                        final_domain = urlparse(href).netloc.lower()
                        return href, final_domain

        # General redirect handling for other URLs
        response = _make_http_request(url)

        # Check if we got a redirect in the response history
        if response and response.history:
            final_url = response.url
            logger.info(f"URL redirected to: {final_url}")
            final_domain = urlparse(final_url).netloc.lower()
            return final_url, final_domain

        return url, final_domain

    except Exception as e:
        logger.error(f"Error following redirects for {url}: {e}")
        # Return original URL and domain if redirection fails
        return url, urlparse(url).netloc.lower()


def _configure_newspaper():
    """Configure newspaper with optimal settings"""
    config = newspaper.Config()
    config.browser_user_agent = get_random_user_agent()
    config.request_timeout = 10
    config.memoize_articles = False  # Disable caching to get fresh content
    config.fetch_images = False  # Skip image fetching for better performance
    return config


def _extract_with_playwright(article_url: str, user_agent: str) -> Optional[str]:
    """Extract article content using Playwright as a fallback method with advanced paywall bypassing and DOM cleanup"""
    if not PLAYWRIGHT_AVAILABLE:
        return None

    content = None
    retry_delays = [5000, 10000]  # Progressive delays in milliseconds

    # Parse domain for special handling
    domain = urlparse(article_url).netloc
    is_biztoc = "biztoc.com" in domain.lower()

    # Default configuration for all sites
    site_config = {'wait': 'domcontentloaded',
                   'timeout': 10000, 'stealth': False}

    for attempt, delay in enumerate([0] + retry_delays):
        try:
            logger.info(
                f"Trying Playwright for {article_url} - Attempt {attempt+1} with {delay}ms loading delay")

            # Browser launch options
            browser_args = []

            # No need for stealth mode since we're not handling problematic sites
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=browser_args)

                # Configure mobile device emulation (iPhone or Android)
                if 'iPhone' in user_agent:
                    # iPhone SE viewport
                    device = p.devices['iPhone SE']
                else:
                    # Generic Android viewport
                    device = {
                        'viewport': {'width': 412, 'height': 915},
                        'device_scale_factor': 2.625,
                        'is_mobile': True,
                        'has_touch': True
                    }

                # Create context with device emulation
                context = browser.new_context(
                    user_agent=user_agent,
                    **device if 'iPhone' not in user_agent else {},
                    locale='en-US'
                )

                # Block unnecessary resource types for better performance
                context.route('**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,otf,mp4,webm,ogg,mp3,wav}',
                              lambda route: route.abort())

                page = context.new_page()

                # Set extra HTTP headers for a more realistic browser
                page.set_extra_http_headers({
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'DNT': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Upgrade-Insecure-Requests': '1',
                })

                # Set a referrer for better believability
                page.set_extra_http_headers(
                    {'Referer': 'https://www.google.com/'})

                # Special handling for BizToc URLs
                if is_biztoc:
                    logger.info(
                        "BizToc URL detected in Playwright, extracting original URL")

                    try:
                        # Navigate to the BizToc page first
                        page.goto(article_url, timeout=30000,
                                  wait_until='domcontentloaded')

                        # Look for the element with class "urlbox drops text-mono"
                        page.wait_for_selector(
                            '.urlbox.drops.text-mono', timeout=10000)

                        # Extract the original URL from the element
                        original_url = page.evaluate("""
                            () => {
                                // Try to find the link with the class
                                const linkElement = document.querySelector('a.urlbox.drops.text-mono');
                                if (linkElement) {
                                    return linkElement.href;
                                }
                                
                                // Fallback to span inside anchor
                                const spanElement = document.querySelector('span.urlbox.drops.text-mono');
                                if (spanElement && spanElement.closest('a')) {
                                    return spanElement.closest('a').href;
                                }
                                
                                return null;
                            }
                        """)

                        if original_url:
                            logger.info(
                                f"Found original URL on BizToc: {original_url}")

                            # Check if the redirected URL is in blocked domains before navigating
                            if _is_blocked_domain(original_url):
                                logger.info(
                                    f"Skipping blocked domain after BizToc redirect: {original_url}")
                                browser.close()
                                return None

                            # Update the article URL to the original source
                            article_url = original_url

                            # Now navigate to the original article
                            logger.info(
                                f"Navigating to original article: {article_url} ")
                            page.goto(article_url, timeout=site_config['timeout'],
                                      wait_until=site_config['wait'])
                        else:
                            logger.warning(
                                "Could not find original URL on BizToc page")
                    except Exception as e:
                        logger.error(
                            f"Error handling BizToc URL in Playwright: {e}")
                else:
                    # Standard navigation for non-BizToc URLs
                    try:
                        # Use a simpler "commit" wait strategy for initial navigation
                        logger.info(
                            f"Navigating to {article_url} with {site_config['wait']} strategy")
                        page.goto(article_url, timeout=site_config['timeout'],
                                  wait_until=site_config['wait'])
                    except Exception as e:
                        logger.warning(f"Navigation failed: {e}")
                        # If we timeout, we'll still try to extract content from whatever loaded
                        pass

                if delay > 0:
                    logger.info(
                        f"Waiting additional {delay}ms for content to load")
                    page.wait_for_timeout(delay)

                    # Gentle scrolling for problematic sites
                    for i in range(3):
                        scroll_pos = (i + 1) * 300
                        page.evaluate(f"window.scrollTo(0, {scroll_pos})")
                        page.wait_for_timeout(500)
                    page.evaluate("window.scrollTo(0, 0)")

                # Try to get article content even if the page didn't fully load
                try:
                    # Extract article content
                    content_selectors = [
                        'article', 'main', '.post-content', '.article-content',
                        '.entry-content', '.content', '[itemprop="articleBody"]',
                        '.article-body', '.story-body', '.story', '.post-body'
                    ]

                    content = ""
                    for selector in content_selectors:
                        try:
                            logger.debug(f"Trying selector: {selector}")
                            elements = page.query_selector_all(selector)

                            if elements:
                                for element in elements:
                                    # Get all paragraphs inside this element
                                    paragraphs = element.query_selector_all(
                                        'p')

                                    if not paragraphs or len(paragraphs) < 3:
                                        # If no paragraphs found, try getting direct text
                                        element_text = element.text_content().strip()
                                        if element_text and len(element_text) > 200:
                                            content = element_text
                                            break
                                    else:
                                        paragraph_texts = []
                                        for p in paragraphs:
                                            text = p.text_content().strip()
                                            # Skip short paragraphs
                                            if text and len(text) > 20:
                                                paragraph_texts.append(text)

                                        # Join paragraphs with double newlines
                                        element_content = '\n\n'.join(
                                            paragraph_texts)
                                        if element_content and len(element_content) > 200:
                                            content = element_content
                                            break
                        except Exception as e:
                            logger.debug(
                                f"Error with selector {selector}: {e}")
                            continue

                        if content:
                            break

                    # If we still don't have content, try a more aggressive approach
                    if not content or len(content) < 200:
                        logger.debug("Trying fallback extraction method")
                        # Extract all paragraphs from the page
                        all_paragraphs = page.query_selector_all('p')
                        paragraph_texts = []

                        for p in all_paragraphs:
                            try:
                                text = p.text_content().strip()
                                # Only include substantial paragraphs
                                if text and len(text) > 50:
                                    paragraph_texts.append(text)
                            except Exception:
                                continue

                        # Join paragraphs with double newlines
                        if paragraph_texts:
                            content = '\n\n'.join(paragraph_texts)

                except Exception as e:
                    logger.error(f"Error extracting content: {e}")

                browser.close()

                if content and len(content) > 200:
                    logger.info(
                        f"Successfully extracted content using Playwright for {article_url} on attempt {attempt+1}")
                    return content

                logger.info(
                    f"Attempt {attempt+1} failed to extract sufficient content")

        except Exception as e:
            logger.error(
                f"Error using Playwright fallback (attempt {attempt+1}): {e}")

        # If content was extracted or we've tried all delays, exit the loop
        if content or attempt >= len(retry_delays):
            break

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


def _is_content_too_short(content: str) -> bool:
    """
    Check if the content is too short to be a valid article

    Args:
        content: The article content string

    Returns:
        True if content is too short, False otherwise
    """
    if not content:
        return True

    # Check character count
    if len(content) < MIN_CONTENT_CHARS:
        # Also check word count as a secondary measure
        word_count = len(content.split())
        if word_count < MIN_CONTENT_WORDS:
            logger.warning(
                f"Content too short: {len(content)} chars, {word_count} words")
            return True

    return False


def extract_article_content(article_url: str, referrer: str = None) -> Optional[Dict[str, Any]]:
    """
    Extract content from an article URL

    Args:
        article_url: URL of the article to extract
        referrer: Optional referrer URL (if None, a random one will be used)

    Returns:
        Dictionary containing article details or None if extraction fails
    """
    # Check if domain is in blocked list
    if _is_blocked_domain(article_url):
        logger.info(f"Skipping blocked domain: {article_url}")
        return None

    # Maximum retries for short content detection
    max_retries = 3

    for retry_count in range(max_retries):
        try:
            if retry_count > 0:
                logger.info(
                    f"Retry #{retry_count} for {article_url} due to short content")
                # Add increasing delay between retries
                random_delay(1.0 + retry_count, 3.0 + retry_count)

            logger.info(f"Extracting content from {article_url}")

            # Get original domain for logging
            original_url = article_url
            original_domain = urlparse(article_url).netloc.lower()

            # Special handling for BizToc URLs
            is_biztoc = "biztoc.com" in original_domain

            # Follow redirects to get the real article URL if it's a redirect link
            # Check if this is likely a redirect URL
            is_redirect_url = any([
                is_biztoc,
                ("news.google.com" in original_domain),
                ("/redirect/" in article_url),
                ("/r?" in article_url),
                ("url=" in article_url)
            ])

            final_domain = original_domain
            if is_redirect_url:
                # Follow redirects to get the actual article URL
                article_url, final_domain = _follow_redirect(article_url)

                # Check if redirected URL is in blocked domains
                if _is_blocked_domain(final_domain):
                    logger.info(
                        f"Skipping blocked domain after redirect: {final_domain} ({article_url})")
                    return None

                if article_url != original_url:
                    # Update domain to the one we actually redirected to
                    logger.info(
                        f"Redirected from {original_domain} to {final_domain}")

                    # For BizToc, add a delay to ensure the target page has time to load
                    if is_biztoc:
                        logger.info(
                            "BizToc URL detected, adding delay before scraping target page")
                        # Simple delay to ensure the target page loads
                        time.sleep(2)
                else:
                    logger.warning(
                        f"Failed to follow redirect for {original_url}")

            # Get domain from final URL to track old articles
            domain = urlparse(article_url).netloc

            # Use realistic referrer
            if not referrer:
                referrer = get_referrer()

            # Configure newspaper with random user agent
            user_agent = get_random_user_agent()
            newspaper.Config().browser_user_agent = user_agent
            newspaper.Config().fetch_images = False  # Skip image fetching for performance

            article = newspaper.Article(article_url)

            # Add a random delay to mimic human behavior before downloading
            random_delay()
            # Use our standard HTTP request method with proper headers
            response = _make_http_request(
                article_url, custom_user_agent=user_agent, custom_referrer=referrer)

            if response:
                article.download(input_html=response.text)
            else:
                article.download()

            # Add another random delay before parsing (as if a human is reading)
            random_delay(2.0, 7.0)

            article.parse()
            article.nlp()  # Natural language processing for keywords and summary

            # Check if the article is older than 3 days
            three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)

            if article.publish_date:
                # Ensure publish_date has timezone info
                article_date = article.publish_date
                if article_date.tzinfo is None:
                    # Create a new datetime object with timezone info
                    article_date = datetime(
                        year=article_date.year,
                        month=article_date.month,
                        day=article_date.day,
                        hour=article_date.hour,
                        minute=article_date.minute,
                        second=article_date.second,
                        microsecond=article_date.microsecond,
                        tzinfo=timezone.utc
                    )

                if article_date < three_days_ago:
                    logger.info(
                        f"Found old article from {domain}")

            # Create article data with additional browser-like metadata
            article_data = {
                'url': article_url,
                'title': article.title,
                'content': article.text,
                'authors': article.authors,
                'published_date': article.publish_date.isoformat() if article.publish_date else None,
                'scraped_at': datetime.now(timezone.utc).isoformat(),
                'original_domain': original_domain,
                'final_domain': final_domain
            }

            # First check if the content is too short
            content_too_short = _is_content_too_short(article.text)
            fallback_used = False

            # Use fallbacks if content is too short or missing
            if content_too_short or not article.text:
                logger.warning(
                    f"Article extraction may have failed for {article_url}. Using fallback methods")

                # Try BeautifulSoup fallback
                if response:
                    soup_content = _extract_with_soup(response.text)
                    if soup_content and not _is_content_too_short(soup_content):
                        article_data['content'] = soup_content
                        logger.info(
                            f"Successfully extracted content using BeautifulSoup fallback for {article_url} ")
                        fallback_used = True
                    elif soup_content:
                        logger.warning(
                            "BeautifulSoup content too short, trying Playwright")

                # If BeautifulSoup fallback didn't work or content still too short, try Playwright
                if (not fallback_used or _is_content_too_short(article_data['content'])):
                    playwright_content = _extract_with_playwright(
                        article_url, user_agent)
                    if playwright_content and not _is_content_too_short(playwright_content):
                        article_data['content'] = playwright_content
                        fallback_used = True
                        logger.info(
                            f"Successfully extracted content using Playwright for {article_url}")
                    elif playwright_content:
                        logger.warning("Playwright content too short")

            # Check if content is still too short after all fallbacks
            if _is_content_too_short(article_data['content']):
                if retry_count < max_retries - 1:
                    logger.warning(
                        f"Content still too short after fallbacks. Will retry extraction.")
                    continue  # Try again
                else:
                    logger.error(
                        f"Failed to extract sufficient content after {max_retries} attempts: {article_url}")
                    return None

            logger.info(f"Successfully extracted content from {article_url}")
            return article_data

        except Exception as e:
            logger.error(f"Error extracting content from {article_url}: {e}")
            if retry_count < max_retries - 1:
                # Wait before retrying
                time.sleep(2 * (retry_count + 1))
                continue
            return None

    return None
