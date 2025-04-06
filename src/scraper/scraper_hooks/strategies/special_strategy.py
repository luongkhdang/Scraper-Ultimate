"""
Special Strategy Extractor for handling restricted and protected sites.

This module implements advanced extraction strategies for sites with anti-bot measures.
Includes adaptive retry mechanisms, randomized behaviors, and detection countermeasures.

IMPORTANT NOTE: 
AI AGENT SHOULD NEVER USE DUMMY (FOR EXAMPLE, DUMMYTORINTEGRATION). AI AGENT WHICH USE DUMMY 
SHOULD BE ASHAMED BECAUSE THEY HAVE FAILED THEIR JOB AND ARE CONSIDERD USELESS.

Exports:
    - SpecialStrategyExtractor: Main extractor class for protected sites
    - extract_with_special_strategy: Compatibility function for backward compatibility

Related files:
    - browser_setup.py: Browser configuration and fingerprinting controls
    - consent_handler.py: Cookie consent dialog handling
    - tor_integration.py: Tor circuit rotation support
    - page_capture.py: Debug capture functionality (currently disabled)
"""
import os
import asyncio
import random
import logging
import json
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

# Check for Playwright availability first
try:
    from playwright.async_api import Error as PlaywrightError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logging.warning(
        "Playwright not available. Special strategy will be limited.")
    PlaywrightError = Exception  # Fallback definition

from ..base import BaseExtractor

# List of domains that we won't even try to scrape
NOT_TO_TRY_DOMAINS = [
    "thehill.com",
    "wsj.com",
    "nytimes.com"
]

# Import tor integration with robust error handling
try:
    from . import tor_integration
    # Check if Tor integration is available
    TOR_INTEGRATION_AVAILABLE = tor_integration.is_available()
    logging.info(f"Tor integration available: {TOR_INTEGRATION_AVAILABLE}")
except ImportError as e:
    logging.error(f"Error importing tor_integration: {e}")
    TOR_INTEGRATION_AVAILABLE = False
    # Make the core functions available even if module import fails
    # We must not use dummy implementations as noted in the module header
    tor_integration = None

# Import browser setup with error handling
try:
    from .browser_setup import create_page_for_url
except ImportError as e:
    logging.error(f"Error importing browser_setup: {e}")

    async def create_page_for_url(*args, **kwargs):
        logging.error("Browser setup not available")
        return None, None, None, None

# Import consent handler with error handling
try:
    from .consent_handler import handle_consent_dialogs, remove_overlay_elements
except ImportError as e:
    logging.error(f"Error importing consent_handler: {e}")
    async def handle_consent_dialogs(*args, **kwargs): return False
    async def remove_overlay_elements(*args, **kwargs): return False

# Import page capture module - we'll check if it's disabled
try:
    from . import page_capture
    # Check if page capture is disabled
    PAGE_CAPTURE_AVAILABLE = not getattr(
        page_capture, 'CAPTURE_DISABLED', True)
    if not PAGE_CAPTURE_AVAILABLE:
        logging.info("Page capture module is disabled")
except ImportError as e:
    logging.error(f"Error importing page_capture: {e}")
    PAGE_CAPTURE_AVAILABLE = False

logger = logging.getLogger(__name__)

# Ensure the logger shows more information
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')


def is_domain_blocked(url):
    """
    Check if a URL's domain is in the NOT_TO_TRY_DOMAINS list

    Args:
        url: URL to check

    Returns:
        bool: True if domain is in NOT_TO_TRY_DOMAINS, False otherwise
    """
    try:
        domain = urlparse(url).netloc.lower()
        # Check if any of the blocked domains are in the URL's domain
        for blocked_domain in NOT_TO_TRY_DOMAINS:
            if blocked_domain in domain:
                logger.info(
                    f"Domain {domain} is in NOT_TO_TRY_DOMAINS list - skipping")
                return True
        return False
    except Exception as e:
        logger.error(f"Error checking domain blacklist: {e}")
        # Better to err on the side of caution
        return True


class SpecialStrategyExtractor(BaseExtractor):
    """
    Special Strategy Extractor for restrictive sites with anti-bot measures.

    This extractor uses advanced techniques such as:
    - Fingerprint consistency
    - Randomized behaviors
    - Adaptive retry mechanisms
    - Tor IP rotation
    - Advanced detection evasion methods
    """

    def __init__(self, config=None):
        """Initialize the special strategy extractor with config settings."""
        super().__init__(config)
        self.config = config or {}
        self.max_retries = self.config.get("max_retries", 3)
        self.capture_dir = self.config.get("capture_dir", "captures")

        # Check Tor availability with detailed logging
        self.tor_available = False
        try:
            # Only check tor availability if the module was imported successfully
            if tor_integration:
                self.tor_available = tor_integration.is_available() and tor_integration.is_ready()
                logger.info(f"Tor availability checked: {self.tor_available}")
                if not self.tor_available:
                    logger.warning(
                        "Tor is not available or not ready. Special strategy will use direct connections.")
        except Exception as e:
            logger.error(f"Error checking Tor availability: {e}")

        # Setup directory for capturing debugging information
        # Only create directory if page capture is available
        if PAGE_CAPTURE_AVAILABLE:
            os.makedirs(self.capture_dir, exist_ok=True)

        # Fingerprint consistency values - same across session, varies between sessions
        self.session_fingerprint = {
            'hardware_concurrency': random.randint(2, 8),
            'device_memory': random.choice([2, 4, 8]),
            'screen_resolution': f"{random.randint(1280, 1920)}x{random.randint(720, 1080)}",
            'color_depth': random.choice([24, 30, 32]),
            'platform': random.choice(['Win32', 'MacIntel', 'Linux x86_64']),
            'timezone_offset': random.randint(-720, 720)
        }

        # Detection history to adapt behavior
        self.detection_history = {
            'captcha_encounters': 0,
            'blocked_pages': 0,
            'successful_extractions': 0,
            'detected_sites': set(),
            'last_detection_time': None
        }

        # Log initialization completion
        logger.info(
            f"SpecialStrategyExtractor initialized with Tor available: {self.tor_available}, Page capture: {PAGE_CAPTURE_AVAILABLE}")

    async def _apply_consistent_fingerprint(self, page):
        """
        Apply consistent fingerprint values to the page to avoid detection.

        Args:
            page: Playwright page object

        Returns:
            None
        """
        # Get the values from the session fingerprint
        cores = self.session_fingerprint['hardware_concurrency']
        memory = self.session_fingerprint['device_memory']
        resolution = self.session_fingerprint['screen_resolution']
        color_depth = self.session_fingerprint['color_depth']
        platform = self.session_fingerprint['platform']
        tz_offset = self.session_fingerprint['timezone_offset']

        width, height = map(int, resolution.split('x'))

        # Apply to the page using JavaScript
        await page.evaluate(f"""() => {{
            // Override hardware properties
            Object.defineProperty(navigator, 'hardwareConcurrency', {{
                get: () => {cores}
            }});
            
            Object.defineProperty(navigator, 'deviceMemory', {{
                get: () => {memory}
            }});
            
            Object.defineProperty(navigator, 'platform', {{
                get: () => '{platform}'
            }});
            
            // Override screen properties
            Object.defineProperty(screen, 'width', {{
                get: () => {width}
            }});
            
            Object.defineProperty(screen, 'height', {{
                get: () => {height}
            }});
            
            Object.defineProperty(screen, 'availWidth', {{
                get: () => {width}
            }});
            
            Object.defineProperty(screen, 'availHeight', {{
                get: () => {height - 40}
            }});
            
            Object.defineProperty(screen, 'colorDepth', {{
                get: () => {color_depth}
            }});
            
            Object.defineProperty(screen, 'pixelDepth', {{
                get: () => {color_depth}
            }});
            
            // Override timezone
            Date.prototype.getTimezoneOffset = function() {{
                return {tz_offset};
            }};
        }}""")

    async def _is_protection_detected(self, page, url):
        """
        Check if the current page shows protection measures.

        Args:
            page: Playwright page object
            url: Current URL being processed

        Returns:
            tuple: (bool, str) - Detection status and type
        """
        # Common patterns for protection detection
        detection_patterns = {
            'captcha': ['captcha', 'robot', 'human verification', 'security check'],
            'blocked': ['access denied', 'forbidden', 'blocked', '403', 'security error'],
            'rate_limited': ['rate limit', 'too many requests', '429']
        }

        try:
            # Get page content
            page_content = await page.content()
            page_content = page_content.lower()
            page_title = await page.title()
            current_url = page.url

            # Check for redirects to security pages
            for security_term in ['security', 'captcha', 'verify', 'check']:
                if security_term in current_url.lower() and security_term not in url.lower():
                    logger.warning(
                        f"Redirected to security page: {current_url}")
                    self._update_detection_history('captcha', url)
                    return True, 'captcha'

            # Check for protection patterns in content
            for detection_type, patterns in detection_patterns.items():
                for pattern in patterns:
                    if pattern in page_content or pattern in page_title.lower():
                        logger.warning(f"Detected {detection_type} protection")
                        self._update_detection_history(detection_type, url)
                        return True, detection_type

            # Check for empty content or very short content (unusual)
            if len(page_content.strip()) < 500:
                logger.warning("Suspiciously short content detected")
                self._update_detection_history('blocked', url)
                return True, 'blocked'

            return False, None

        except Exception as e:
            logger.error(f"Error checking protection: {e}")
            return False, None

    def _update_detection_history(self, detection_type, url):
        """
        Update detection history to adapt behavior for future requests.

        Args:
            detection_type: Type of detection encountered
            url: URL where detection occurred

        Returns:
            None
        """
        # Track this detection
        now = datetime.now()
        domain = url.split('//')[-1].split('/')[0]

        self.detection_history['last_detection_time'] = now
        self.detection_history['detected_sites'].add(domain)

        if detection_type == 'captcha':
            self.detection_history['captcha_encounters'] += 1
        elif detection_type in ['blocked', 'rate_limited']:
            self.detection_history['blocked_pages'] += 1

        # Save detection history for analysis
        try:
            history_file = Path(self.capture_dir) / "detection_history.json"

            # Convert data to serializable format
            serializable_history = {
                'captcha_encounters': self.detection_history['captcha_encounters'],
                'blocked_pages': self.detection_history['blocked_pages'],
                'successful_extractions': self.detection_history['successful_extractions'],
                'detected_sites': list(self.detection_history['detected_sites']),
                'last_detection_time': str(now) if now else None
            }

            with open(history_file, 'w') as f:
                json.dump(serializable_history, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save detection history: {e}")

    def _calculate_adaptive_delay(self, url, attempt):
        """
        Calculate adaptive delay based on detection history and current attempt.

        Args:
            url: Current URL
            attempt: Current attempt number

        Returns:
            float: Delay in seconds to use before next action
        """
        base_delay = 2.0
        domain = url.split('//')[-1].split('/')[0]

        # Increase delay if this domain has been detected before
        if domain in self.detection_history['detected_sites']:
            base_delay *= 1.5

        # Increase delay based on overall detection history
        if self.detection_history['captcha_encounters'] > 5:
            base_delay *= 1.3

        if self.detection_history['blocked_pages'] > 3:
            base_delay *= 1.2

        # Increase delay based on attempt number with randomization
        attempt_multiplier = 1.0 + (attempt * 0.5)

        # Add randomization (+/- 20%)
        randomization = random.uniform(0.8, 1.2)

        final_delay = base_delay * attempt_multiplier * randomization

        # Cap maximum delay
        return min(final_delay, 15.0)

    async def extract(self, url, config=None):
        """
        Extract content from a URL using the special strategy.

        Args:
            url: URL to extract content from
            config: Optional configuration overrides

        Returns:
            dict: Extracted content or error information
        """
        # Check if domain is in NOT_TO_TRY_DOMAINS list
        if is_domain_blocked(url):
            logger.info(f"Skipping extraction for blocked domain: {url}")
            return {
                "success": False,
                "error": "Domain is in NOT_TO_TRY_DOMAINS list",
                "url": url
            }

        merged_config = {**self.config, **(config or {})}
        use_tor = merged_config.get("use_tor", False) and self.tor_available

        playwright = browser = context = page = None
        detected = False
        detection_type = None
        content = None

        for attempt in range(self.max_retries + 1):
            try:
                # Calculate adaptive delay before retry
                if attempt > 0:
                    delay = self._calculate_adaptive_delay(url, attempt)
                    logger.info(
                        f"Attempt {attempt}: Using adaptive delay of {delay:.2f}s")
                    await asyncio.sleep(delay)

                # If protection was detected in previous attempt, consider rotating Tor
                if detected and use_tor and self.tor_available and attempt > 0:
                    # Random delay before rotation to appear more natural
                    pre_rotation_delay = random.uniform(2.7, 3.5)
                    if detection_type == 'captcha':
                        # Longer delay if a CAPTCHA was detected
                        pre_rotation_delay += random.uniform(1.5, 2.8)

                    logger.info(
                        f"Preparing for Tor rotation (waiting {pre_rotation_delay:.2f}s)")
                    await asyncio.sleep(pre_rotation_delay)

                    # Rotate Tor connection
                    logger.info("Rotating Tor IP address")
                    await tor_integration.rotate_tor_connection()

                    # Wait after rotation
                    post_rotation_wait = random.uniform(1.0, 2.5)
                    logger.info(
                        f"Waiting after Tor rotation ({post_rotation_wait:.2f}s)")
                    await asyncio.sleep(post_rotation_wait)

                # Close previous resources if any
                if page:
                    await page.close()
                if context:
                    await context.close()
                if browser:
                    await browser.close()
                if playwright:
                    await playwright.stop()

                # Create a new browser page
                playwright, browser, context, page = await create_page_for_url(
                    url, use_tor=use_tor
                )

                if not page:
                    logger.error(f"Failed to create page on attempt {attempt}")
                    continue

                # Apply consistent fingerprint
                await self._apply_consistent_fingerprint(page)

                # Navigate to the URL with timeout
                await page.goto(url, timeout=30000)

                # Check if protection is detected
                detected, detection_type = await self._is_protection_detected(page, url)
                if detected:
                    logger.warning(
                        f"Protection detected ({detection_type}) on attempt {attempt}")

                    # Capture screenshot for analysis - only if page capture is available
                    if PAGE_CAPTURE_AVAILABLE:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        reason = f"protection_{detection_type}"
                        await page_capture.capture_page_state(
                            page, url, False, attempt, reason, self.capture_dir
                        )
                    continue

                # Handle consent dialogs
                await handle_consent_dialogs(page)

                # Remove overlay elements
                await remove_overlay_elements(page)

                # Allow content to load with random delay
                load_delay = random.uniform(1.0, 2.5)
                await page.wait_for_timeout(int(load_delay * 1000))

                # Simulate human-like scrolling
                await self._simulate_scrolling(page)

                # Extract content
                content = await self._extract_content(page)

                # Record successful extraction
                self.detection_history['successful_extractions'] += 1

                # Capture successful page state for analysis if page capture is available
                if PAGE_CAPTURE_AVAILABLE:
                    await page_capture.capture_page_state(
                        page, url, True, attempt, "success", self.capture_dir
                    )

                # Success - return the content
                return {"success": True, "content": content, "url": url}

            except PlaywrightError as e:
                logger.error(f"Playwright error on attempt {attempt}: {e}")
                # Check for specific error patterns that indicate detection
                error_str = str(e).lower()
                if any(term in error_str for term in ['timeout', 'navigation', 'blocked']):
                    detected = True
                    detection_type = 'timeout'
                    self._update_detection_history('blocked', url)

                    # Capture error state if page capture is available and page still exists
                    if PAGE_CAPTURE_AVAILABLE and page and not page.is_closed():
                        await page_capture.capture_page_state(
                            page, url, False, attempt, "playwright_error", self.capture_dir
                        )

            except Exception as e:
                logger.error(f"Error on attempt {attempt}: {e}")

                # Capture error state if page capture is available and page still exists
                if PAGE_CAPTURE_AVAILABLE and page and not page.is_closed():
                    try:
                        await page_capture.capture_page_state(
                            page, url, False, attempt, "unknown_error", self.capture_dir
                        )
                    except Exception as capture_error:
                        logger.error(
                            f"Error capturing page state: {capture_error}")

            finally:
                # Clean up resources for this attempt
                try:
                    if page and not page.is_closed():
                        await page.close()
                    if context:
                        await context.close()
                    if browser:
                        await browser.close()
                    if playwright:
                        await playwright.stop()
                except Exception as e:
                    logger.error(f"Error cleaning up resources: {e}")

        # All attempts failed
        return {
            "success": False,
            "error": f"Failed after {self.max_retries + 1} attempts",
            "url": url
        }

    async def _simulate_scrolling(self, page):
        """
        Simulate human-like scrolling behavior.

        Args:
            page: Playwright page object

        Returns:
            None
        """
        try:
            # Get page height
            page_height = await page.evaluate("document.body.scrollHeight")
            viewport_height = await page.evaluate("window.innerHeight")

            # Determine a random number of scroll actions
            scroll_count = random.randint(3, 6)

            for i in range(scroll_count):
                # Calculate a random scroll position with non-linear distribution
                # This makes scrolling feel more natural by having varying scroll distances
                scroll_percent = random.betavariate(
                    2, 1) if i < scroll_count - 1 else 1
                scroll_position = int(page_height * scroll_percent)

                # Scroll to position with smooth behavior
                await page.evaluate(f"window.scrollTo({{top: {scroll_position}, behavior: 'smooth'}})")

                # Randomize scroll delay to appear more human-like
                scroll_delay = random.uniform(400, 800)
                await asyncio.sleep(scroll_delay / 1000)

                # Add slight pauses at interesting content (simulating reading)
                if random.random() < 0.3:
                    reading_pause = random.uniform(800, 2000)
                    await asyncio.sleep(reading_pause / 1000)

            # Scroll back up partially (most users don't read to the very bottom)
            if random.random() < 0.7:
                partial_scroll_back = random.uniform(0.2, 0.6)
                back_position = int(page_height * partial_scroll_back)
                await page.evaluate(f"window.scrollTo({{top: {back_position}, behavior: 'smooth'}})")
                await asyncio.sleep(random.uniform(300, 700) / 1000)

        except Exception as e:
            logger.error(f"Error during scrolling simulation: {e}")

    async def _extract_content(self, page):
        """
        Extract the actual content from the page.

        Args:
            page: Playwright page object

        Returns:
            dict: Extracted content
        """
        # Implementation depends on content type
        # This is a simplified example - extend based on needs
        try:
            title = await page.title()

            # Extract main content
            # Strategy: Look for main content containers
            content_selectors = [
                "article", "main", ".content", "#content",
                ".article", ".post", ".entry-content"
            ]

            text_content = ""
            for selector in content_selectors:
                elements = await page.query_selector_all(selector)
                if elements:
                    for element in elements:
                        # Get text content
                        content = await element.text_content()
                        if content and len(content) > 100:  # Skip short content
                            text_content += content + "\n\n"

                    # If we found substantial content, stop looking
                    if len(text_content) > 500:
                        break

            # If no content found with specific selectors, get body content
            if not text_content:
                body = await page.query_selector("body")
                if body:
                    text_content = await body.text_content()

            # Get page metadata
            metadata = await page.evaluate("""() => {
                const metadata = {};
                const metaTags = document.querySelectorAll('meta');
                metaTags.forEach(tag => {
                    const name = tag.getAttribute('name') || tag.getAttribute('property');
                    const content = tag.getAttribute('content');
                    if (name && content) {
                        metadata[name] = content;
                    }
                });
                return metadata;
            }""")

            return {
                "title": title,
                "content": text_content.strip(),
                "metadata": metadata,
                "url": page.url,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error extracting content: {e}")
            return {"error": str(e)}

    async def clean_up(self):
        """Clean up any resources."""
        # Nothing to do here as resources are cleaned within extract()
        pass


async def extract_with_special_strategy(url: str, user_agent: str = None) -> tuple:
    """
    Compatibility wrapper function for backward compatibility with old code.

    Args:
        url: URL to extract content from
        user_agent: User agent string to use

    Returns:
        tuple: (content, final_url) or (None, None) if extraction fails
    """
    logger.info(f"Using compatibility wrapper for special strategy on {url}")
    try:
        # Create config dict with user agent
        config = {"user_agent": user_agent} if user_agent else {}

        # Create extractor instance
        extractor = SpecialStrategyExtractor()

        # Call the extract method
        result = await extractor.extract(url, config)

        # Process the result
        if result and result.get("success", False):
            # The content is a string directly, not a nested dict
            content = result.get("content", "")
            final_url = result.get("url", url)
            return (content, final_url)
        else:
            error_msg = result.get(
                "error", "Unknown error") if result else "No result"
            logger.warning(
                f"Special strategy extraction failed in compatibility wrapper: {error_msg}")
            return (None, None)
    except Exception as e:
        logger.error(f"Error in special strategy compatibility wrapper: {e}")
        return (None, None)
