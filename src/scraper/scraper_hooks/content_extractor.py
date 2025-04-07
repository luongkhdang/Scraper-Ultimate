"""
Content Extractor: Extracts article content from URLs with multiple fallback methods.

IMPORTANT NOTE: 
AI AGENT SHOULD NEVER USE DUMMY (FOR EXAMPLE, DUMMYTORINTEGRATION). AI AGENT WHICH USE DUMMY 
SHOULD BE ASHAMED BECAUSE THEY HAVE FAILED THEIR JOB AND ARE CONSIDERD USELESS.

Exported Functions:
- extract_article_content(article_url: str, referrer: str = None) -> Optional[Dict[str, Any]]: Extracts content from an article URL

Related Files:
- src/scraper/scraper_hooks/utils.py: Provides utility functions for HTTP requests
- src/scraper/scraper_hooks/url_extractor.py: Provides URLs for this module to process
- src/scraper/scraper_hooks/strategies/special_strategy.py: Special strategy for handling blocked domains
"""
import newspaper
from typing import Dict, Optional, Any, Tuple, List
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
import re
import time
import asyncio
import concurrent.futures

# Import local modules
from .utils import make_request, get_random_user_agent, get_realistic_headers, random_delay, get_referrer

# Import special strategy for blocked domains
try:
    from .strategies.special_strategy import SpecialStrategyExtractor
    SPECIAL_STRATEGY_AVAILABLE = True
except ImportError:
    SPECIAL_STRATEGY_AVAILABLE = False
    logging.warning(
        "Special strategy not available. Blocked domains will be skipped.")

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
    "reuter.com"
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


def _configure_newspaper():
    """Configure newspaper with optimal settings"""
    config = newspaper.Config()
    config.browser_user_agent = get_random_user_agent()
    config.request_timeout = 10
    config.memoize_articles = False  # Disable caching to get fresh content
    config.fetch_images = False  # Skip image fetching for better performance
    return config


def _extract_with_playwright(article_url: str, user_agent: str) -> Optional[Tuple[str, str]]:
    """
    Extract article content using Playwright as a fallback method with advanced paywall bypassing and DOM cleanup

    Args:
        article_url: The URL to extract content from
        user_agent: The user agent to use for the request

    Returns:
        Tuple of (extracted content, final URL after redirects) or None if extraction fails
    """
    if not PLAYWRIGHT_AVAILABLE:
        return None

    content = None
    final_url = article_url  # Initialize with original URL
    retry_delays = [5000, 10000]  # Progressive delays in milliseconds

    # Parse domain for special handling
    domain = urlparse(article_url).netloc
    is_biztoc = "biztoc.com" in domain.lower()
    is_google_news = "news.google.com" in domain.lower()

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
                                    f"Blocked domain detected after BizToc redirect: {original_url}")
                                browser.close()

                                # Try using special strategy for this blocked domain if available
                                if SPECIAL_STRATEGY_AVAILABLE:
                                    logger.info(
                                        f"Attempting to use special strategy for blocked domain from BizToc: {original_url}")
                                    try:
                                        # Determine if we're in an event loop
                                        try:
                                            asyncio.get_running_loop()
                                            in_event_loop = True
                                        except RuntimeError:
                                            in_event_loop = False

                                        # Initialize the extractor
                                        extractor = SpecialStrategyExtractor()

                                        # Handle running within or outside an event loop
                                        special_result = None
                                        if in_event_loop:
                                            logger.info(
                                                "Running in existing event loop, using thread executor")
                                            with concurrent.futures.ThreadPoolExecutor() as executor:
                                                future = executor.submit(lambda: asyncio.run(
                                                    extractor.extract(original_url, {"user_agent": user_agent})))
                                                try:
                                                    special_result = future.result(
                                                        timeout=60)
                                                except concurrent.futures.TimeoutError:
                                                    logger.error(
                                                        "Special strategy timed out after 60 seconds")
                                                except Exception as e:
                                                    logger.error(
                                                        f"Error in special strategy thread: {e}")
                                        else:
                                            logger.info(
                                                "No event loop detected, using asyncio.run directly")
                                            special_result = asyncio.run(
                                                extractor.extract(original_url, {"user_agent": user_agent}))

                                        # Process result dictionary
                                        if special_result and special_result.get("success", False):
                                            # Extract content and final URL from result dictionary
                                            content = special_result.get(
                                                "content", "")
                                            special_final_url = special_result.get(
                                                "url", original_url)

                                            article_data = {
                                                'url': special_final_url,
                                                'title': urlparse(special_final_url).netloc,
                                                'content': content,
                                                'authors': [],
                                                'published_date': None,
                                                'scraped_at': datetime.now(timezone.utc).isoformat(),
                                                'original_domain': urlparse(article_url).netloc.lower(),
                                                'final_domain': urlparse(special_final_url).netloc.lower()
                                            }

                                            if not _is_content_too_short(content):
                                                logger.info(
                                                    f"Successfully extracted content from blocked domain via BizToc using special strategy: {original_url}")
                                                return article_data
                                    except Exception as e:
                                        logger.error(
                                            f"Error using special strategy for blocked domain from BizToc {original_url}: {e}")

                                return None

                            # Update the article URL to the original source
                            final_url = original_url
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
                # Special handling for Google News URLs - improved redirect detection
                elif is_google_news:
                    logger.info(
                        "Google News URL detected in Playwright, handling redirects")

                    try:
                        # First, navigate to the Google News URL
                        logger.info(
                            f"Navigating to Google News URL: {article_url}")
                        page.goto(article_url, timeout=30000,
                                  wait_until='domcontentloaded')

                        # Google News typically auto-redirects to the target article
                        # Implement adaptive waiting with polling instead of fixed timeout
                        max_wait_time = 15000  # Maximum wait time in ms
                        poll_interval = 500    # Check every 500ms
                        start_time = time.time()
                        initial_url = page.url
                        redirected_url = initial_url
                        redirect_detected = False

                        logger.info(
                            f"Starting redirect detection polling for Google News. Initial URL: {initial_url}")

                        # Poll for URL changes with a maximum wait time
                        while time.time() - start_time < max_wait_time/1000:
                            current_url = page.url

                            # If URL changed, we detected a redirect
                            if current_url != initial_url:
                                redirected_url = current_url
                                redirect_detected = True
                                redirect_time = time.time() - start_time
                                logger.info(
                                    f"Redirect detected after {redirect_time:.2f}s: {redirected_url}")

                                # Wait a bit more to ensure we get the final URL (some sites do multi-stage redirects)
                                page.wait_for_timeout(1000)

                                # Check one more time for any additional redirects
                                final_redirected_url = page.url
                                if final_redirected_url != redirected_url:
                                    logger.info(
                                        f"Additional redirect detected: {final_redirected_url}")
                                    redirected_url = final_redirected_url
                                break

                            # Wait before checking again
                            page.wait_for_timeout(poll_interval)

                        # If no redirect detected, try alternative approaches
                        if not redirect_detected:
                            logger.warning(
                                f"No automatic redirect detected for Google News URL after {max_wait_time/1000}s waiting")

                            # Try to find and click on article links
                            try:
                                # Common selectors for Google News article links
                                link_selectors = [
                                    'a h3', 'h3 a', 'a.DY5T1d', 'a.VDXfz',
                                    'article a', '.article a', 'div[role="article"] a'
                                ]

                                # Try each selector
                                for selector in link_selectors:
                                    try:
                                        # First ensure the page is stable before trying to query elements
                                        page.wait_for_load_state(
                                            'domcontentloaded', timeout=5000)

                                        # Add a small delay to ensure the page is interactive
                                        page.wait_for_timeout(500)

                                        # Check if we can query elements safely
                                        elements = page.query_selector_all(
                                            selector)

                                        if elements and len(elements) > 0:
                                            logger.info(
                                                f"Found potential article link with selector '{selector}', attempting to click")

                                            # Store the current URL before clicking
                                            pre_click_url = page.url

                                            # We'll use evaluate to click to avoid context issues
                                            # This is more stable than directly clicking the element
                                            page.evaluate(f"""() => {{
                                                const elements = document.querySelectorAll('{selector}');
                                                if (elements && elements.length > 0) {{
                                                    elements[0].click();
                                                    return true;
                                                }}
                                                return false;
                                            }}""")

                                            # Create a promise to watch for navigation
                                            logger.info(
                                                "Waiting for navigation after click...")

                                            # Use wait_for_url_change instead of wait_for_load_state
                                            # This is more reliable for detecting redirects
                                            try:
                                                # Wait for URL to change from the initial URL with a reasonable timeout
                                                with page.expect_navigation(wait_until='domcontentloaded', timeout=10000) as navigation_info:
                                                    pass

                                                # Check if navigation occurred
                                                current_url = page.url
                                                if current_url != pre_click_url:
                                                    redirected_url = current_url
                                                    redirect_detected = True
                                                    logger.info(
                                                        f"Successfully navigated to article via click: {redirected_url}")
                                                    break
                                            except Exception as navigation_error:
                                                logger.warning(
                                                    f"Navigation error after click: {navigation_error}")

                                                # Check if URL changed despite error
                                                current_url = page.url
                                                if current_url != pre_click_url:
                                                    redirected_url = current_url
                                                    redirect_detected = True
                                                    logger.info(
                                                        f"URL changed despite navigation error: {redirected_url}")
                                                    break
                                    except Exception as selector_error:
                                        logger.debug(
                                            f"Error with selector '{selector}': {selector_error}")
                                        # Continue trying other selectors
                                        continue

                                if not redirect_detected:
                                    # Try one more approach - look for the main article link that might be prominent
                                    try:
                                        page.wait_for_load_state(
                                            'domcontentloaded', timeout=5000)
                                        page.wait_for_timeout(500)

                                        # Try to find the most prominent link - usually the first large one
                                        # This might work when specific selectors fail
                                        result = page.evaluate("""() => {
                                            // Look for the largest link that might be an article
                                            const links = Array.from(document.querySelectorAll('a')).filter(a => {
                                                // Filter for links that have substantial content and seem like article links
                                                const hasText = a.innerText && a.innerText.length > 30;
                                                const hasImage = a.querySelector('img');
                                                const isLarge = a.offsetWidth > 200 || a.offsetHeight > 100;
                                                return (hasText || hasImage) && isLarge;
                                            });
                                            
                                            // Sort by size (approximated by offsetWidth * offsetHeight)
                                            links.sort((a, b) => {
                                                const aSize = a.offsetWidth * a.offsetHeight;
                                                const bSize = b.offsetWidth * b.offsetHeight;
                                                return bSize - aSize;  // Descending order
                                            });
                                            
                                            // Click the largest link if available
                                            if (links.length > 0) {
                                                links[0].click();
                                                return true;
                                            }
                                            return false;
                                        }""")

                                        if result:
                                            logger.info(
                                                "Clicked on the most prominent link")

                                            # Wait for navigation
                                            try:
                                                with page.expect_navigation(wait_until='domcontentloaded', timeout=10000) as navigation_info:
                                                    pass

                                                # Check if URL changed
                                                current_url = page.url
                                                if current_url != initial_url:
                                                    redirected_url = current_url
                                                    redirect_detected = True
                                                    logger.info(
                                                        f"Successfully navigated to article via prominent link: {redirected_url}")
                                            except Exception as navigation_error:
                                                logger.warning(
                                                    f"Navigation error after clicking prominent link: {navigation_error}")

                                                # Still check if URL changed
                                                current_url = page.url
                                                if current_url != initial_url:
                                                    redirected_url = current_url
                                                    redirect_detected = True
                                                    logger.info(
                                                        f"URL changed despite navigation error: {redirected_url}")
                                    except Exception as prominent_error:
                                        logger.warning(
                                            f"Error trying to find prominent link: {prominent_error}")

                                    if not redirect_detected:
                                        logger.warning(
                                            "Failed to find clickable article links")
                            except Exception as click_error:
                                logger.warning(
                                    f"Error during manual article navigation: {click_error}")

                                # Check if the URL changed despite the error
                                try:
                                    current_url = page.url
                                    if current_url != initial_url:
                                        redirected_url = current_url
                                        redirect_detected = True
                                        logger.info(
                                            f"URL changed despite click error: {redirected_url}")
                                except Exception:
                                    # If we can't even check the URL, the page is likely in a bad state
                                    pass

                        # Update final_url if a redirect was detected
                        if redirect_detected:
                            logger.info(
                                f"Google News redirected to: {redirected_url}")
                            final_url = redirected_url

                            # Check if the redirected URL is in blocked domains
                            if _is_blocked_domain(redirected_url):
                                logger.info(
                                    f"Blocked domain detected after Google News redirect: {redirected_url}")
                                browser.close()

                                # Try using special strategy for this blocked domain if available
                                if SPECIAL_STRATEGY_AVAILABLE:
                                    logger.info(
                                        f"Attempting to use special strategy for blocked domain from Google News: {redirected_url}")
                                    try:
                                        # Determine if we're in an event loop
                                        try:
                                            asyncio.get_running_loop()
                                            in_event_loop = True
                                        except RuntimeError:
                                            in_event_loop = False

                                        # Initialize the extractor
                                        extractor = SpecialStrategyExtractor()

                                        # Handle running within or outside an event loop
                                        special_result = None
                                        if in_event_loop:
                                            logger.info(
                                                "Running in existing event loop, using thread executor")
                                            with concurrent.futures.ThreadPoolExecutor() as executor:
                                                future = executor.submit(lambda: asyncio.run(
                                                    extractor.extract(redirected_url, {"user_agent": user_agent})))
                                                try:
                                                    special_result = future.result(
                                                        timeout=60)
                                                except concurrent.futures.TimeoutError:
                                                    logger.error(
                                                        "Special strategy timed out after 60 seconds")
                                                except Exception as e:
                                                    logger.error(
                                                        f"Error in special strategy thread: {e}")
                                        else:
                                            logger.info(
                                                "No event loop detected, using asyncio.run directly")
                                            special_result = asyncio.run(
                                                extractor.extract(redirected_url, {"user_agent": user_agent}))

                                        # Process result dictionary
                                        if special_result and special_result.get("success", False):
                                            # Extract content and final URL from result dictionary
                                            content = special_result.get(
                                                "content", "")
                                            special_final_url = special_result.get(
                                                "url", redirected_url)

                                            article_data = {
                                                'url': special_final_url,
                                                'title': urlparse(special_final_url).netloc,
                                                'content': content,
                                                'authors': [],
                                                'published_date': None,
                                                'scraped_at': datetime.now(timezone.utc).isoformat(),
                                                'original_domain': urlparse(article_url).netloc.lower(),
                                                'final_domain': urlparse(special_final_url).netloc.lower()
                                            }

                                            if not _is_content_too_short(content):
                                                logger.info(
                                                    f"Successfully extracted content from blocked domain via Google News using special strategy: {redirected_url}")
                                                return article_data
                                    except Exception as e:
                                        logger.error(
                                            f"Error using special strategy for blocked domain from Google News {redirected_url}: {e}")

                                    return None
                            else:
                                logger.warning(
                                    "Google News redirect detection failed, will attempt content extraction from the original page")
                    except Exception as e:
                        logger.error(
                            f"Error handling Google News URL in Playwright: {e}")
                else:
                    # Standard navigation for non-BizToc and non-Google News URLs
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

                # Handle redirects for all URLs (get current URL after all navigation)
                current_url = page.url
                if current_url != article_url:
                    # Only log if not already handled by special cases above
                    if not (is_biztoc or is_google_news):
                        logger.info(
                            f"URL redirected from {article_url} to {current_url}")
                    final_url = current_url

                    # Check if redirected URL is in blocked domains (only for non-special case URLs)
                    if not is_biztoc and not is_google_news and _is_blocked_domain(current_url):
                        logger.info(
                            f"Blocked domain detected after redirect: {current_url}")
                        browser.close()

                        # Try using special strategy for this blocked domain if available
                        if SPECIAL_STRATEGY_AVAILABLE:
                            logger.info(
                                f"Attempting to use special strategy for blocked domain after redirect: {current_url}")
                            try:
                                # Determine if we're in an event loop
                                try:
                                    asyncio.get_running_loop()
                                    in_event_loop = True
                                except RuntimeError:
                                    in_event_loop = False

                                # Initialize the extractor
                                extractor = SpecialStrategyExtractor()

                                # Handle running within or outside an event loop
                                special_result = None
                                if in_event_loop:
                                    logger.info(
                                        "Running in existing event loop, using thread executor")
                                    with concurrent.futures.ThreadPoolExecutor() as executor:
                                        future = executor.submit(lambda: asyncio.run(
                                            extractor.extract(current_url, {"user_agent": user_agent})))
                                        try:
                                            special_result = future.result(
                                                timeout=60)
                                        except concurrent.futures.TimeoutError:
                                            logger.error(
                                                "Special strategy timed out after 60 seconds")
                                        except Exception as e:
                                            logger.error(
                                                f"Error in special strategy thread: {e}")
                                else:
                                    logger.info(
                                        "No event loop detected, using asyncio.run directly")
                                    special_result = asyncio.run(
                                        extractor.extract(current_url, {"user_agent": user_agent}))

                                # Process result dictionary
                                if special_result and special_result.get("success", False):
                                    # Extract content and final URL from result dictionary
                                    content = special_result.get("content", "")
                                    special_final_url = special_result.get(
                                        "url", current_url)

                                    article_data = {
                                        'url': special_final_url,
                                        'title': urlparse(special_final_url).netloc,
                                        'content': content,
                                        'authors': [],
                                        'published_date': None,
                                        'scraped_at': datetime.now(timezone.utc).isoformat(),
                                        'original_domain': urlparse(article_url).netloc.lower(),
                                        'final_domain': urlparse(special_final_url).netloc.lower()
                                    }

                                    if not _is_content_too_short(content):
                                        logger.info(
                                            f"Successfully extracted content from blocked domain after redirect using special strategy: {current_url}")
                                        return article_data
                            except Exception as e:
                                logger.error(
                                    f"Error using special strategy for blocked domain after redirect {current_url}: {e}")

                        return None

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

                # Extract content from the page
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
                    return content, final_url

                logger.info(
                    f"Attempt {attempt+1} failed to extract sufficient content")

        except Exception as e:
            logger.error(
                f"Error using Playwright fallback (attempt {attempt+1}): {e}")

        # If content was extracted or we've tried all delays, exit the loop
        if content or attempt >= len(retry_delays):
            break

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
    # Check if domain is in blocked list and if special strategy is available
    domain_blocked = _is_blocked_domain(article_url)

    # Get original domain for tracking
    original_url = article_url
    original_domain = urlparse(article_url).netloc.lower()

    # Early detection of Google News URLs
    is_google_news = "news.google.com" in original_domain

    # Use realistic referrer if not provided
    if not referrer:
        referrer = get_referrer()

    # Get random user agent for extraction
    user_agent = get_random_user_agent()

    if domain_blocked and not SPECIAL_STRATEGY_AVAILABLE:
        logger.info(
            f"Skipping blocked domain without special strategy: {article_url}")
        return None

    # For blocked domains with special strategy available, we'll try that approach
    if domain_blocked and SPECIAL_STRATEGY_AVAILABLE:
        logger.info(
            f"Using special strategy for blocked domain: {article_url}")
        try:
            # Get realistic user agent for the special strategy
            user_agent = get_random_user_agent()

            try:
                # Determine if we're in an event loop
                try:
                    asyncio.get_running_loop()
                    in_event_loop = True
                except RuntimeError:
                    in_event_loop = False

                # Initialize the extractor
                extractor = SpecialStrategyExtractor()

                # Handle running within or outside an event loop
                if in_event_loop:
                    logger.info(
                        "Running in existing event loop, using thread executor")
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(lambda: asyncio.run(
                            extractor.extract(article_url, {"user_agent": user_agent})))
                        try:
                            special_result = future.result(timeout=60)
                        except concurrent.futures.TimeoutError:
                            logger.error(
                                "Special strategy timed out after 60 seconds")
                            return None
                        except Exception as e:
                            logger.error(
                                f"Error in special strategy thread: {e}")
                            return None
                else:
                    logger.info(
                        "No event loop detected, using asyncio.run directly")
                    special_result = asyncio.run(
                        extractor.extract(article_url, {"user_agent": user_agent}))
            except Exception as e:
                logger.error(f"Error setting up async execution: {e}")
                return None

            # Process result dictionary
            if special_result and special_result.get("success", False):
                # Extract content and final URL from result dictionary
                content = special_result.get("content", "")
                final_url = special_result.get("url", article_url)

                # Create article data with the extracted content
                article_data = {
                    'url': final_url,
                    # Use domain as fallback title
                    'title': urlparse(final_url).netloc,
                    'content': content,
                    'authors': [],
                    'published_date': None,
                    'scraped_at': datetime.now(timezone.utc).isoformat(),
                    'original_domain': urlparse(article_url).netloc.lower(),
                    'final_domain': urlparse(final_url).netloc.lower()
                }

                # Check if content is sufficient
                if not _is_content_too_short(content):
                    logger.info(
                        f"Successfully extracted content from blocked domain using special strategy: {article_url}")
                    return article_data
                else:
                    logger.warning(
                        f"Content from special strategy too short for: {article_url}")
                    return None
            else:
                # Get error message if available
                error_msg = special_result.get(
                    "error", "Unknown error") if special_result else "No result returned"
                logger.warning(
                    f"Special strategy failed for blocked domain: {error_msg}")
                return None

        except Exception as e:
            logger.error(
                f"Error using special strategy for blocked domain {article_url}: {e}")
            return None

    # Special handling for Google News URLs - skip standard extraction and use Playwright directly
    if is_google_news and PLAYWRIGHT_AVAILABLE:
        logger.info(
            f"Google News URL detected, using direct Playwright extraction: {article_url}")

        # Try Playwright extraction which has enhanced Google News redirect handling
        playwright_result = _extract_with_playwright(article_url, user_agent)

        if playwright_result:
            content, final_url = playwright_result

            if content and not _is_content_too_short(content):
                # Extract final domain from the redirected URL
                final_domain = urlparse(final_url).netloc.lower(
                ) if final_url else original_domain

                # Prepare complete article data with proper domain tracking
                article_data = {
                    'url': final_url,
                    'title': "Article from " + final_domain,  # We may not have a proper title
                    'content': content,
                    'authors': [],
                    'published_date': None,
                    'scraped_at': datetime.now(timezone.utc).isoformat(),
                    'original_url': original_url,
                    'final_url': final_url,
                    'original_domain': original_domain,
                    'final_domain': final_domain
                }

                logger.info(
                    f"Successfully extracted Google News content: {original_url} -> {final_url}")
                return article_data
            else:
                logger.warning(
                    f"Failed to extract sufficient content from Google News URL: {article_url}")
                return None
        else:
            logger.warning(
                f"Playwright extraction failed for Google News URL: {article_url}")
            # Continue with standard extraction as fallback

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

            # Set initial domain tracking
            final_domain = original_domain

            # Domain for tracking old articles
            domain = original_domain

            # Configure newspaper with random user agent
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
                    f"Article extraction may have failed for {article_url}. Using Playwright fallback")

                # Try Playwright fallback
                playwright_result = _extract_with_playwright(
                    article_url, user_agent)

                if playwright_result:
                    playwright_content, final_url = playwright_result

                    if playwright_content and not _is_content_too_short(playwright_content):
                        article_data['content'] = playwright_content
                        fallback_used = True
                        logger.info(
                            f"Successfully extracted content using Playwright for {article_url}")

                        # Update URL and domain based on Playwright's handling of redirects
                        if final_url != article_url:
                            final_domain = urlparse(final_url).netloc.lower()

                            # Check if redirected URL is in blocked domains
                            if _is_blocked_domain(final_domain):
                                logger.info(
                                    f"Skipping blocked domain after Playwright redirect: {final_domain} ({final_url})")
                                return None

                            # Update all URL and domain tracking fields consistently
                            article_data['url'] = final_url
                            # Add this for compatibility with scraper_client
                            article_data['final_url'] = final_url
                            # Add this for compatibility with scraper_client
                            article_data['original_url'] = original_url
                            article_data['final_domain'] = final_domain
                            logger.info(
                                f"Playwright redirected from {original_domain} to {final_domain}")
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

            # Ensure consistent field names for domain tracking
            # These fields are expected by scraper_client.py
            if 'original_url' not in article_data:
                article_data['original_url'] = original_url
            if 'final_url' not in article_data:
                article_data['final_url'] = article_data['url']

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
