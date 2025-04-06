"""
Browser Setup Module

This module provides functions for configuring and creating browser contexts with
stealth settings and proxies for web scraping.

Exported Functions:
- get_default_browser_args() -> List[str]: Returns default browser arguments for stealth browsing
- create_browser_context(url, user_agent=None, use_tor=False) -> Tuple: Creates a properly configured browser context
- setup_device_emulation(playwright, user_agent=None) -> Dict: Sets up device emulation based on user agent

Related Files:
- src/scraper/scraper_hooks/strategies/special_strategy.py: Main scraping strategy that uses this module
- src/scraper/scraper_hooks/strategies/tor_integration.py: Tor integration for proxy support

Dependencies:
- playwright: For browser automation
"""

import logging
from typing import Dict, Optional, Any, Tuple, List
from urllib.parse import urlparse
import random

# Import tor integration for proxy support
from . import tor_integration

# Check if Playwright is available
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logging.warning(
        "Playwright not installed. Browser context creation will not work.")

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_default_browser_args() -> List[str]:
    """
    Get default browser arguments for stealth browsing

    Returns:
        List[str]: List of browser arguments
    """
    # Reduced set of critical arguments to minimize fingerprinting
    return [
        '--disable-blink-features=AutomationControlled',
        '--disable-extensions',
        '--no-first-run',
        '--no-default-browser-check'
    ]


def setup_device_emulation(playwright, user_agent=None) -> Dict[str, Any]:
    """
    Set up device emulation based on user agent

    Args:
        playwright: Playwright instance
        user_agent: User agent string

    Returns:
        Dict: Context options for device emulation
    """
    # Context options
    context_options = {}

    # Modern realistic user agents for better stealth
    realistic_uas = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36 Edg/113.0.1774.42'
    ]

    # If no user agent is provided, select one randomly
    if not user_agent:
        user_agent = random.choice(realistic_uas)

    # Detect if mobile user agent
    is_mobile = user_agent and (
        'iPhone' in user_agent or 'Android' in user_agent)

    if is_mobile:
        # Mobile emulation
        if 'iPhone' in user_agent:
            device = playwright.devices['iPhone 13']
            context_options = {**device}
        else:
            # Android emulation
            context_options = {
                'user_agent': user_agent,
                'viewport': {'width': 412, 'height': 915},
                'device_scale_factor': 2.625,
                'is_mobile': True,
                'has_touch': True
            }
    else:
        # Desktop emulation
        context_options = {
            'user_agent': user_agent,
            'viewport': {'width': 1280, 'height': 800},
            'device_scale_factor': 1,
            'is_mobile': False,
            'has_touch': False
        }

    # Add common options
    context_options.update({
        'locale': 'en-US',
        'timezone_id': 'America/New_York',
        'permissions': ['geolocation']
    })

    return context_options


async def create_browser_context(url, user_agent=None, use_tor=False):
    """
    Create a properly configured browser context with stealth settings

    Args:
        url: Target URL for extraction
        user_agent: Optional user agent to use
        use_tor: Whether to use Tor proxy

    Returns:
        Tuple of (playwright, browser, context) objects
    """
    if not PLAYWRIGHT_AVAILABLE:
        logger.error("Playwright not available, cannot create browser context")
        return None, None, None

    try:
        playwright = await async_playwright().start()

        # Set up browser launch options
        browser_options = {
            "headless": True,
            "args": get_default_browser_args()
        }

        # Add Tor proxy if needed and available
        if use_tor and tor_integration.is_ready():
            browser_options = tor_integration.setup_tor_for_browser(
                browser_options)

        # Launch browser
        browser = await playwright.chromium.launch(**browser_options)

        # Set up device emulation based on user agent
        context_options = setup_device_emulation(playwright, user_agent)

        # Create context with options
        context = await browser.new_context(**context_options)

        # Add WebDriver detection countermeasures
        await context.add_init_script("""
            // Critical WebDriver removal
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false
            });
            
            // Remove automation flags
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
            
            // Hide automation artifacts
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' || 
                parameters.name === 'geolocation' || 
                parameters.name === 'persistent-storage' || 
                parameters.name === 'camera' || 
                parameters.name === 'microphone'
            ) 
            ? originalQuery(parameters)
            : Promise.resolve({state: Notification.permission});
        """)

        return playwright, browser, context

    except Exception as e:
        logger.error(f"Error creating browser context: {e}")
        return None, None, None


async def setup_page_defaults(page):
    """
    Set up default page settings for scraping

    Args:
        page: Playwright page object

    Returns:
        The configured page object
    """
    if not page:
        return None

    try:
        # Randomize key fingerprinting headers
        languages = ['en-US,en;q=0.9', 'en-US,en;q=0.8,es;q=0.2',
                     'en-GB,en;q=0.9', 'en-CA,en;q=0.8,fr-CA;q=0.2']
        platforms = ['Windows', 'Macintosh', 'Linux']
        referrers = [
            'https://www.google.com/search?q=news+today',
            'https://www.bing.com/search?q=latest+articles',
            'https://www.google.com/search?q=recent+events',
            'https://news.google.com/',
            'https://www.bing.com/news'
        ]

        # Set extra HTTP headers with randomization for a more realistic browser
        await page.set_extra_http_headers({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': random.choice(languages),
            'DNT': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'Referer': random.choice(referrers),
            'sec-ch-ua-platform': f'"{random.choice(platforms)}"'
        })

        # Block unnecessary resource types for better performance
        # Use resource type-based blocking instead of extension-based for better accuracy and performance
        await page.route("**/*", lambda route: _handle_route(route))

        return page

    except Exception as e:
        logger.error(f"Error setting up page defaults: {e}")
        return page


async def _handle_route(route):
    """
    Handler for route interception to block unnecessary resources

    Args:
        route: The route to evaluate

    Returns:
        None
    """
    request = route.request
    resource_type = request.resource_type

    # Block these resource types completely for better performance
    blocked_types = ["image", "media", "font", "stylesheet"]

    # Allow certain font types for essential UI rendering
    url = request.url.lower()

    # Allow these requests
    allow_request = (
        # Allow essential resources
        resource_type in ["document", "xhr", "fetch"] or
        # Allow scripts but could be refined to block specific scripts
        resource_type == "script" or
        # Special case: allow some font resources that might be critical
        (resource_type == "font" and ("fontawesome" in url or "essential" in url))
    )

    if allow_request:
        await route.continue_()
    else:
        # Block with 10% sample logging for debugging
        if random.random() < 0.1:
            logger.debug(f"Blocked {resource_type} resource: {url}")
        await route.abort()


async def create_page_for_url(url, user_agent=None, use_tor=False):
    """
    Create a page ready for scraping a specific URL

    Args:
        url: The URL to scrape
        user_agent: User agent to use
        use_tor: Whether to use Tor

    Returns:
        Tuple of (playwright, browser, context, page)
    """
    # Create the browser and context
    playwright, browser, context = await create_browser_context(url, user_agent, use_tor)

    if not all([playwright, browser, context]):
        return None, None, None, None

    try:
        # Create a new page
        page = await context.new_page()

        # Set up default page settings
        await setup_page_defaults(page)

        return playwright, browser, context, page
    except Exception as e:
        logger.error(f"Error creating page: {e}")

        # Clean up resources on failure
        try:
            if context:
                await context.close()
            if browser:
                await browser.close()
            if playwright:
                await playwright.stop()
        except Exception:
            pass

        return None, None, None, None


async def close_browser_resources(playwright=None, browser=None, context=None, page=None):
    """
    Safely close browser resources

    Args:
        playwright, browser, context, page: Resources to close

    Returns:
        bool: True if closed successfully
    """
    try:
        if page:
            await page.close()
        if context:
            await context.close()
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()
        return True
    except Exception as e:
        logger.error(f"Error closing browser resources: {e}")
        return False
