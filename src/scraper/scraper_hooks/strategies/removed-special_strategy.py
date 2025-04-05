"""
Special Strategy: Extracts content from blocked or restricted domains using Playwright with enhanced techniques.

Exported Functions:
- extract_with_special_strategy(article_url: str, user_agent: str) -> Optional[Tuple[str, str]]: 
  Extracts content from blocked domains using Playwright with special techniques

Related Files:
- src/scraper/scraper_hooks/content_extractor.py: Uses this module as a strategy for blocked domains
- src/scraper/scraper_hooks/utils.py: Provides utility functions used by this module
"""

from typing import Dict, Optional, Any, Tuple, List
import logging
from urllib.parse import urlparse
import time
import random
import os
import datetime
import asyncio
from pathlib import Path
import tempfile
import concurrent.futures

# Check if Playwright is available
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logging.warning(
        "Playwright not installed. Special strategy will not work.")

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Site-specific strategies for known paywalled domains
SITE_STRATEGIES = {
    "nytimes.com": {
        "description": "New York Times paywall bypass",
        "cookies": [
            {"name": "nyt-gdpr", "value": "1", "path": "/"},
            {"name": "nyt-a", "value": "0", "path": "/"},
            {"name": "nyt-purr", "value": "cfhhn",
                "path": "/"},  # Helps with paywall
            # Mobile version can be easier to access
            {"name": "nyt-m", "value": "1", "path": "/"}
        ],
        "headers": {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1",
            "Referer": "https://www.google.com/search?q=site:nytimes.com"
        },
        "selectors_to_remove": [
            "#gateway-content", "#app > div > div:not([class])",
            "[data-testid='inline-message']", ".css-gx5sib",
            "#site-content > div.css-1l28vmd", ".css-1bd8bfl",
            ".css-mcm29f", "#app > div.css-1wvak7", ".css-3fbowa"
        ],
        "dom_script": """
            // Remove all metering/gateway elements
            document.querySelectorAll('[id*="gateway"], [id*="message"], [class*="paywall"], [class*="popup"], [class*="overlay"]')
                .forEach(el => el.remove());
            
            // Force content areas to be visible and expand their height
            document.querySelectorAll('[id*="content"], [class*="content"], article, [class*="article"]')
                .forEach(el => {
                    el.style.display = 'block';
                    el.style.visibility = 'visible';
                    el.style.maxHeight = 'none';
                    el.style.height = 'auto';
                    el.style.overflow = 'visible';
                });
                
            // NYT specific - make article content visible by toggling classes
            const article = document.querySelector('article') || document.querySelector('[data-testid="article-container"]');
            if (article) {
                // Force article to be visible and all its children
                const makeVisible = (element) => {
                    element.style.display = 'block';
                    element.style.visibility = 'visible';
                    element.style.opacity = '1';
                    Array.from(element.children).forEach(child => makeVisible(child));
                };
                makeVisible(article);
            }
        """,
        "content_selectors": [
            "[name='articleBody']", "[data-testid='article-content']",
            "article[data-testid]", ".article", "article", ".meteredContent",
            ".StoryBodyCompanionColumn", ".story-body", ".StoryBody-content",
            "[class*='articleBody']"
        ],
        "wait_time": 5000  # Longer wait for NYT content to load
    },
    "wsj.com": {
        "description": "Wall Street Journal paywall bypass",
        "cookies": [
            {"name": "gdprApplies", "value": "false", "path": "/"},
            {"name": "usr_prof_v2", "value": "eyJpYyI6MX0=",
                "path": "/"}  # Bypass cookie
        ],
        "headers": {
            "User-Agent": "Mozilla/5.0 (Linux; Android 12; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.61 Mobile Safari/537.36",
            "Referer": "https://www.google.com/",
            "Sec-Ch-Ua": "\"Google Chrome\";v=\"101\", \" Not;A Brand\";v=\"99\"",
            "Sec-Ch-Ua-Mobile": "?1",
            "Sec-Ch-Ua-Platform": "\"Android\""
        },
        "dom_script": """
            // Click the direct link button if available (to get full text in some cases)
            const directLinks = Array.from(document.querySelectorAll('a'))
                .filter(a => a.textContent.includes('Direct Link') || a.textContent.includes('Read Now'));
            if (directLinks.length) directLinks[0].click();
            
            // Remove the main WSJ paywall overlays
            const paywalls = document.querySelectorAll('.wsj-snippet-login, .snippet-promotion, #cx-snippet-overlay, .wsj-ad, .paywall, .wsj-sign-in-container, .media-object-paywall');
            paywalls.forEach(el => el.remove());
            
            // Unlock overflow
            document.body.style.overflow = 'auto';
            document.body.style.position = 'static';
            
            // WSJ specific - reveal hidden paragraphs
            setTimeout(() => {
                // Make all paragraphs visible
                document.querySelectorAll('p[data-type="paragraph"]').forEach(p => {
                    p.style.display = 'block';
                    p.style.visibility = 'visible';
                    p.style.opacity = '1';
                });
                
                // Remove blur effects on text
                document.querySelectorAll('.blur, [style*="blur"], [style*="opacity"]').forEach(el => {
                    el.style.filter = 'none';
                    el.style.webkitFilter = 'none';
                    el.style.opacity = '1';
                });
            }, 1000);
        """,
        "content_selectors": [
            "[data-module-zone='article_body']", ".article-content",
            "[itemprop='articleBody']", ".wsj-snippet-body",
            ".article__body", ".article-wrap", "[data-type='article']",
            ".bigTop__article", ".article-content"
        ],
        "wait_time": 5000  # Longer wait for WSJ content to load
    },
    "bloomberg.com": {
        "description": "Bloomberg paywall bypass",
        "cookies": [
            {"name": "trc_cookie_storage", "value": "taboola", "path": "/"}
        ],
        "dom_script": """
            // Bloomberg often lazy-loads content, so we need to wait and scroll
            setTimeout(() => {
                // Bloomberg specific: wait for the dynamic content to load
                const bodySection = document.querySelector('.body-content');
                if (bodySection) bodySection.style.display = 'block';
                
                // Remove common Bloomberg paywalls and overlays
                const elementsToRemove = [
                    '[class*="paywall"]', '.navi-sticky-container', 
                    '.ticker-banner', '.leaderboard-container'
                ];
                elementsToRemove.forEach(selector => {
                    document.querySelectorAll(selector).forEach(el => el.remove());
                });
            }, 1000);
        """,
        "content_selectors": [
            ".body-content", ".body-copy", ".body-copy-v2",
            ".paywall-inline-todo"
        ]
    },
    "ft.com": {
        "description": "Financial Times paywall bypass",
        "headers": {
            "Referer": "https://www.google.com/",
            "Accept": "text/html,application/xhtml+xml,application/xml"
        },
        "dom_script": """
            // FT specific cleanup
            document.querySelectorAll('.o-banner, #site-navigation, .n-messaging-banner').forEach(el => el.remove());
            
            // Sometimes content is hidden with height:0 or maxHeight:0
            document.querySelectorAll('[style*="height: 0"], [style*="max-height: 0"]').forEach(el => {
                el.style.height = 'auto';
                el.style.maxHeight = 'none';
            });
        """,
        "content_selectors": [
            ".article__content-body", ".article-body",
            "[data-trackable='article-body']"
        ]
    },
    "businessinsider.com": {
        "description": "Business Insider paywall bypass",
        "cookies": [
            {"name": "consentUUID",
                "value": "8c740b89-f7bf-4541-97d5-94c5b55a5a07", "path": "/"},
            {"name": "subs_bypass", "value": "true", "path": "/"},
            {"name": "bi_li", "value": "true", "path": "/"},  # Logged in cookie
            # View premium content
            {"name": "bi_vpw", "value": "true", "path": "/"}
        ],
        "headers": {
            "Referer": "https://www.google.com/search?q=business+insider+article",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-User": "?1",
            "Sec-Ch-Ua": "\"Google Chrome\";v=\"113\", \"Chromium\";v=\"113\"",
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": "\"Windows\""
        },
        "dom_script": """
            // Business Insider specific cleanup
            setTimeout(() => {
                // Remove paywall and subscription elements
                document.querySelectorAll('.tp-modal, .tp-backdrop, .tp-container, .tp-container-inner, .piano-container, #piano-inline-content-wrapper, [class*="paywall"], [id*="paywall"]').forEach(el => el.remove());
                
                // Remove other distracting elements
                document.querySelectorAll('.ad-wrapper, [class*="-ad-"], [id*="ad-"], .newsletter-signup, .inline-newsletter, #l-persistent-banner').forEach(el => el.remove());
                
                // Unlock any scroll/body locks
                document.body.style.overflow = 'auto';
                document.body.style.position = 'static';
                document.documentElement.style.overflow = 'auto';
                
                // Make article content visible
                document.querySelectorAll('.content-lock-content, .locked-content, [class*="premium"]').forEach(el => {
                    el.style.display = 'block';
                    el.style.visibility = 'visible';
                    el.style.opacity = '1';
                });
                
                // Handle special BI structure seen in screenshot
                document.querySelectorAll('.bigTop__article, article[data-module-zone="article_body"]').forEach(el => {
                    el.style.display = 'block';
                });
            }, 1000);
        """,
        "content_selectors": [
            "article[data-module-zone='article_body']",
            ".bigTop__article",
            ".article-body-text",
            ".content-lock-content",
            "[data-piano-inline-content-wrapper]",
            "#l-content",
            ".article-body-container",
            ".article-body",
            ".post-content"
        ],
        "wait_time": 4000
    }
}

# List of diverse referrers for simulating various traffic sources
REFERRERS = [
    # Search engines with realistic queries
    "https://www.google.com/search?q={domain}+news",
    "https://www.google.com/search?q=latest+news+{domain}",
    "https://www.bing.com/search?q={domain}+article",
    "https://duckduckgo.com/?q={domain}+recent+developments",
    # Social media
    "https://www.reddit.com/r/news",
    "https://www.reddit.com/r/worldnews",
    "https://twitter.com/search?q={domain}",
    "https://www.linkedin.com/feed/",
    # News aggregators
    "https://news.google.com/",
    "https://feedly.com/i/latest",
    "https://flipboard.com/",
    # Direct traffic (no referrer)
    ""
]

# Function to handle slow request loading


async def slow_request_handler(route):
    """Handle requests with random delays to simulate a slower connection"""
    try:
        # Only delay specific resource types to avoid excessive slowdowns
        resource_type = route.request.resource_type.lower()

        # Don't delay the main document to avoid navigation timeouts
        if resource_type == 'document':
            await route.continue_()
            return

        # Different delay strategies for different resource types
        if resource_type in ['xhr', 'fetch']:
            # API calls - shorter delay (0.5-1 seconds)
            delay = random.uniform(500, 1000) / 1000.0
        elif resource_type in ['script', 'stylesheet']:
            # Secondary resources - minimal delay (0.1-0.3 seconds)
            delay = random.uniform(100, 300) / 1000.0
        else:
            # Other resources - no delay
            delay = 0

        # Apply the delay
        if delay > 0:
            await asyncio.sleep(delay)

        # Continue with the request after delay
        await route.continue_()
    except Exception as e:
        # If any error occurs, make sure to continue the request to avoid hanging
        logger.warning(f"Error in slow_request_handler: {e}")
        try:
            await route.continue_()
        except:
            # If continue fails, try to abort to prevent hanging
            try:
                await route.abort()
            except:
                pass


def get_random_referrer(domain: str) -> str:
    """Get a random referrer with domain placeholder replaced if present"""
    referrer = random.choice(REFERRERS)
    if "{domain}" in referrer:
        # Extract domain without subdomain or TLD for more natural searching
        parts = domain.split('.')
        if len(parts) > 2:
            main_domain = parts[-2]  # e.g., 'nytimes' from 'www.nytimes.com'
        else:
            main_domain = parts[0]  # e.g., 'bbc' from 'bbc.co.uk'

        referrer = referrer.replace("{domain}", main_domain)

    return referrer


def extract_with_special_strategy(article_url: str, user_agent: str) -> Optional[Tuple[str, str]]:
    """
    Extract article content using enhanced Playwright techniques designed for blocked domains.

    Args:
        article_url: The URL to extract content from
        user_agent: The user agent to use for the request

    Returns:
        Tuple of (extracted content, final URL after redirects) or None if extraction fails
    """
    if not PLAYWRIGHT_AVAILABLE:
        logger.error(
            "Playwright is not available. Cannot use special strategy.")
        return None

    # Initialize SpecialStrategyExtractor class
    extractor = SpecialStrategyExtractor()

    # This is a simplified wrapper around the async extract method
    # The actual asyncio.run handling is now done in content_extractor.py
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(extractor.extract(article_url, user_agent))
    except Exception as e:
        logger.error(f"Error in extract_with_special_strategy: {e}")
        return None
    finally:
        loop.close()


class SpecialStrategyExtractor:
    """Class to handle special strategy extraction with advanced techniques"""

    def __init__(self):
        """Initialize the extractor with configuration options"""
        pass

    async def extract(self, article_url: str, user_agent: str) -> Optional[Tuple[str, str]]:
        """
        Main extraction method for retrieving content from paywalled/restricted sites

        Args:
            article_url: The URL to extract content from
            user_agent: The user agent to use for the request

        Returns:
            Tuple of (extracted content, final URL after redirects) or None if extraction fails
        """
        content = None
        final_url = article_url  # Initialize with original URL
        # Progressive delays in milliseconds
        retry_delays = [5000, 10000, 15000]

        # Parse domain for special handling
        domain = urlparse(article_url).netloc
        is_biztoc = "biztoc.com" in domain.lower()
        is_google_news = "news.google.com" in domain.lower()

        # Default configuration for all sites
        site_config = {'wait': 'domcontentloaded',
                       'timeout': 30000, 'stealth': True}  # Increase default timeout to 30 seconds

        for attempt, delay in enumerate([0] + retry_delays):
            try:
                logger.info(
                    f"Using special strategy for {article_url} - Attempt {attempt+1} with {delay}ms loading delay")

                # Rest of the extraction logic will be implemented here
                # ... (browser launching, navigation, content extraction)

                async with async_playwright() as p:
                    # Launch browser with anti-detection measures
                    browser = None
                    context = None
                    page = None
                    using_persistent_context = False

                    try:
                        # Enhanced browser launch options for bypassing restrictions
                        browser_args = [
                            '--disable-blink-features=AutomationControlled',
                            '--disable-features=IsolateOrigins,site-per-process',
                            '--disable-site-isolation-trials'
                        ]

                        # Launch with additional configurations for blocked domains
                        browser = await p.chromium.launch(
                            headless=True,
                            args=browser_args
                        )

                        # For highly protected sites like WSJ and NYT, we need to completely mask automation
                        high_security_sites = [
                            "wsj.com", "nytimes.com", "ft.com", "bloomberg.com", "businessinsider.com"]
                        is_high_security = any(
                            secure_site in domain for secure_site in high_security_sites)

                        if is_high_security:
                            logger.info(
                                f"Using enhanced stealth mode for {domain}")
                            # Use even more radical browser launch options for these sites
                            await browser.close()  # Close the previous browser

                            # More extensive anti-detection flags
                            enhanced_browser_args = [
                                '--disable-blink-features=AutomationControlled',
                                '--disable-features=IsolateOrigins,site-per-process,SitePerProcess',
                                '--disable-site-isolation-trials',
                                '--disable-web-security',
                                '--disable-features=IsolateOrigins,site-per-process',
                                '--disable-notifications',
                                '--disable-blink-features',
                                '--disable-automation',
                                '--disable-sync',
                                '--disable-background-timer-throttling',
                                '--disable-backgrounding-occluded-windows',
                                '--disable-breakpad',
                                '--disable-component-extensions-with-background-pages',
                                '--disable-dev-shm-usage',
                                '--disable-extensions',
                                '--disable-renderer-backgrounding',
                                '--disable-hang-monitor',
                                '--disable-ipc-flooding-protection',
                                '--disable-popup-blocking',
                                '--no-first-run',
                                '--no-default-browser-check'
                            ]

                            # Create a temporary directory for user data if needed
                            user_data_dir = tempfile.mkdtemp(
                                prefix="playwright_profile_")
                            logger.info(
                                f"Created temporary user data directory: {user_data_dir}")

                            # Launch with enhanced stealth mode using persistent context
                            try:
                                # Try using persistent context for better anti-detection
                                browser = await p.chromium.launch_persistent_context(
                                    user_data_dir=user_data_dir,
                                    headless=True,  # Always use headless mode to avoid XServer errors
                                    args=enhanced_browser_args
                                )
                                # We'll need to adjust later code since launch_persistent_context returns a BrowserContext, not Browser
                                context = browser  # The persistent context is already a context
                                using_persistent_context = True
                            except Exception as e:
                                logger.warning(
                                    f"Failed to launch persistent context: {e}, falling back to regular launch")
                                # Fall back to regular launch without user data dir
                                browser = await p.chromium.launch(
                                    headless=True,  # Always use headless mode to avoid XServer errors
                                    args=enhanced_browser_args
                                )
                                using_persistent_context = False

                        # Configure more realistic device emulation
                        if 'iPhone' in user_agent:
                            device = p.devices['iPhone 13']
                        else:
                            # Generic Android viewport with more realistic settings
                            device = {
                                'viewport': {'width': 412, 'height': 915},
                                'device_scale_factor': 2.625,
                                'is_mobile': True,
                                'has_touch': True
                            }

                        # Create context if not already created with persistent context
                        if not using_persistent_context:
                            # Create context with enhanced privacy settings
                            context_options = {
                                'user_agent': user_agent,
                                'locale': 'en-US',
                                'timezone_id': 'America/New_York',
                                'geolocation': {'latitude': 40.7128, 'longitude': -74.0060},
                                'permissions': ['geolocation']
                            }

                            # Add device settings if it's a mobile emulation
                            if 'iPhone' in user_agent:
                                context_options.update(device)
                            else:
                                context_options.update(device)

                            # Randomize viewport slightly to avoid exact fingerprinting
                            if is_high_security:
                                # Add tiny random variations to standard viewport sizes
                                if 'viewport' in context_options:
                                    width = context_options['viewport']['width']
                                    height = context_options['viewport']['height']
                                    # Add random variations of 1-3 pixels
                                    context_options['viewport']['width'] = width + \
                                        random.randint(1, 3)
                                    context_options['viewport']['height'] = height + \
                                        random.randint(1, 3)

                            context = await browser.new_context(**context_options)

                        # Set up page with anti-detection measures
                        page = await context.new_page()

                        # Navigate to the page with appropriate strategy for the domain
                        # ... (navigation logic, content extraction)

                        # Handle navigation and content extraction based on domain type
                        # For now, let's implement a simple direct navigation
                        try:
                            logger.info(f"Navigating to {article_url}")
                            await page.goto(article_url, timeout=site_config['timeout'],
                                            wait_until=site_config['wait'])

                            # Wait for content to load
                            await page.wait_for_timeout(5000)

                            # Execute DOM manipulation if needed based on site specific strategy
                            site_strategy = None
                            for site_domain, strategy in SITE_STRATEGIES.items():
                                if site_domain in domain:
                                    site_strategy = strategy
                                    logger.info(
                                        f"Using site-specific strategy for {site_domain}")
                                    break

                            if site_strategy:
                                # Apply site-specific strategy
                                if "dom_script" in site_strategy:
                                    logger.info(
                                        "Applying site-specific DOM script")
                                    await page.evaluate(site_strategy["dom_script"])

                                # Handle consent dialogs that might block content
                                try:
                                    await self._handle_consent_dialogs(page)
                                except Exception as e:
                                    logger.warning(
                                        f"Error handling consent dialogs: {e}")

                            # Extract content
                            content_selectors = [
                                'article', '.article', 'main', '.post-content', '.article-content',
                                '.entry-content', '.content', '[itemprop="articleBody"]',
                                '.article-body', '.story-body'
                            ]

                            # Add site-specific selectors if available
                            if site_strategy and "content_selectors" in site_strategy:
                                content_selectors = site_strategy["content_selectors"] + \
                                    content_selectors

                            # Extract content from the page
                            content = ""
                            for selector in content_selectors:
                                try:
                                    elements = await page.query_selector_all(
                                        selector)
                                    if elements:
                                        for element in elements:
                                            paragraphs = await element.query_selector_all(
                                                'p')
                                            if paragraphs and len(paragraphs) > 2:
                                                paragraph_texts = []
                                                for p in paragraphs:
                                                    text = await p.text_content()
                                                    text = text.strip()
                                                    if text and len(text) > 20:
                                                        paragraph_texts.append(
                                                            text)

                                                element_content = '\n\n'.join(
                                                    paragraph_texts)
                                                if element_content and len(element_content) > 200:
                                                    content = element_content
                                                    break
                                            else:
                                                # If no paragraphs, try direct text content
                                                text = await element.text_content()
                                                text = text.strip()
                                                if text and len(text) > 200:
                                                    content = text
                                                    break
                                except Exception as e:
                                    logger.debug(
                                        f"Error with selector {selector}: {e}")

                                if content:
                                    break

                            if content:
                                logger.info(
                                    f"Successfully extracted content from {article_url}")
                                return content, page.url

                        except Exception as e:
                            logger.error(
                                f"Error during navigation or extraction: {e}")

                    finally:
                        # Cleanup resources
                        if page:
                            try:
                                await page.close()
                            except:
                                pass

                        if context and not using_persistent_context:
                            try:
                                await context.close()
                            except:
                                pass

                        if browser and not using_persistent_context:
                            try:
                                await browser.close()
                            except:
                                pass

            except Exception as e:
                logger.error(f"Error in extraction attempt {attempt+1}: {e}")

            # If content was extracted, return it
            if content:
                return content, final_url

        # If all attempts failed, return None
        return None

    async def _handle_consent_dialogs(self, page):
        """Handle common cookie consent and GDPR dialogs that might block content."""
        # List of common consent button selectors across different sites
        consent_selectors = [
            # Accept buttons
            '#onetrust-accept-btn-handler',  # OneTrust
            '.accept-cookies-button',
            'button[aria-label="Accept cookies"]',
            'button[aria-label="Accept all cookies"]',
            'button[data-testid="GDPR-accept"]',
            'button:has-text("Accept")',
            'button:has-text("Accept all")',
            'button:has-text("I agree")',
            'button:has-text("OK")',
            'button:has-text("Allow all")',
            'button:has-text("Allow cookies")',
            '.js-cookie-consent-agree',
            '#didomi-notice-agree-button',  # Didomi
            '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',  # CookieBot
            '.css-k8o10q',  # NYTimes specific
            '.tp-modal button.tp-close',  # Many newspaper modals
            '.fc-button.fc-primary-button',  # First-party cookie dialog
            '.fc-cta-consent',

            # Close buttons for modals that might block content
            'button[aria-label="Close"]',
            'button.close-dialog',
            'button.modal-close',
            '[data-testid="popup-close"]',
            '.modal .close-button',
            '.overlay-dialog .close'
        ]

        # Check and click each selector
        for selector in consent_selectors:
            try:
                # Check if element exists and is visible
                is_visible = await page.evaluate(f"""
                    () => {{
                        const element = document.querySelector('{selector}');
                        if (!element) return false;
                        
                        const style = window.getComputedStyle(element);
                        return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
                    }}
                """)

                if is_visible:
                    logger.info(f"Found consent dialog element: {selector}")
                    await page.click(selector)
                    logger.info(f"Clicked consent button: {selector}")
                    # Wait a moment for the dialog to disappear
                    await page.wait_for_timeout(1500)
                    return True
            except Exception as e:
                logger.debug(
                    f"Error checking/clicking consent selector {selector}: {str(e)}")

        # If specific selectors didn't work, try a general approach with JavaScript
        try:
            # Try to find and click any visible buttons with text related to accepting cookies
            clicked = await page.evaluate("""
                () => {
                    // Find buttons with common acceptance text
                    const buttonTexts = ['accept', 'agree', 'allow', 'consent', 'ok', 'continue'];
                    const buttons = Array.from(document.querySelectorAll('button, .button, [role="button"], a.btn'));
                    
                    // Filter to visible buttons with matching text
                    const acceptButtons = buttons.filter(btn => {
                        if (!btn.offsetParent) return false; // Not visible
                        const text = btn.textContent.toLowerCase();
                        return buttonTexts.some(t => text.includes(t));
                    });
                    
                    // Click the first matching button if found
                    if (acceptButtons.length > 0) {
                        acceptButtons[0].click();
                        return true;
                    }
                    
                    // Try to find and click "I Accept" link
                    const acceptLinks = Array.from(document.querySelectorAll('a')).filter(a => {
                        if (!a.offsetParent) return false;
                        const text = a.textContent.toLowerCase();
                        return buttonTexts.some(t => text.includes(t));
                    });
                    
                    if (acceptLinks.length > 0) {
                        acceptLinks[0].click();
                        return true;
                    }
                    
                    return false;
                }
            """)

            if clicked:
                logger.info(
                    "Clicked a generic consent button using JavaScript approach")
                await page.wait_for_timeout(1500)
                return True
        except Exception as e:
            logger.debug(
                f"Error with generic consent button approach: {str(e)}")

        # As a last resort, try to remove overlay elements that might be blocking content
        try:
            # Remove common overlay elements
            removed = await page.evaluate("""
                () => {
                    // Common overlay selectors
                    const overlaySelectors = [
                        '.modal', '.overlay', '.paywall', '.popup', '.gdpr', 
                        '.cookie-notice', '.consent-modal', '#cookie-banner',
                        '[class*="paywall"]', '[class*="modal"]', '[class*="overlay"]',
                        '[id*="cookie"]', '[id*="consent"]', '[id*="gdpr"]'
                    ];
                    
                    let removed = false;
                    
                    // Try to remove each potential overlay
                    overlaySelectors.forEach(selector => {
                        const elements = document.querySelectorAll(selector);
                        elements.forEach(el => {
                            if (el.offsetParent && 
                                (el.style.position === 'fixed' || 
                                 window.getComputedStyle(el).position === 'fixed')) {
                                el.remove();
                                removed = true;
                            }
                        });
                    });
                    
                    // Also remove fixed position elements that might be overlays
                    const allElements = document.querySelectorAll('div, section');
                    allElements.forEach(el => {
                        const style = window.getComputedStyle(el);
                        if (el.offsetParent && 
                            style.position === 'fixed' && 
                            style.zIndex && 
                            parseInt(style.zIndex) > 100) {
                            el.remove();
                            removed = true;
                        }
                    });
                    
                    // Also unset body styles that prevent scrolling
                    document.body.style.overflow = 'auto';
                    document.body.style.position = 'static';
                    
                    return removed;
                }
            """)

            if removed:
                logger.info(
                    "Removed overlay elements that might block content")
                return True
        except Exception as e:
            logger.debug(f"Error removing overlay elements: {str(e)}")

        return False
