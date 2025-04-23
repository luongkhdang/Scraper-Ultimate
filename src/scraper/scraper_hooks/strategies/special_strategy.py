"""
Special Strategy Extractor for handling restricted and protected sites.

This module implements advanced extraction strategies for sites with anti-bot measures.
Includes adaptive retry mechanisms, randomized behaviors, and detection countermeasures.
Now includes StealthyFetcher integration as a fallback method when primary extraction fails.

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
from ..base import BaseExtractor
import os
import asyncio
import random
import logging
import json
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
import sys
import importlib
import importlib.util
import subprocess

# Check for Playwright availability first
try:
    from playwright.async_api import Error as PlaywrightError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logging.warning(
        "Playwright not available. Special strategy will be limited.")
    PlaywrightError = Exception  # Fallback definition

# Initialize StealthyFetcher and availability flags
STEALTHY_FETCHER_AVAILABLE = False
StealthyFetcher = None

# Check for StealthyFetcher availability with enhanced error handling
try:
    # Log detailed environment info for easier debugging
    # logging.info(f"Python version: {sys.version}") # Removed - purely informational
    # logging.info(f"Python executable: {sys.executable}") # Removed - purely informational
    # logging.info(
    #     f"Running in Docker: {os.environ.get('RUNNING_IN_DOCKER', 'false')}") # Removed - purely informational

    # Check if scrapling is installed
    scrapling_spec = importlib.util.find_spec("scrapling")
    if scrapling_spec is None:
        logging.error("scrapling package not found in sys.path")
        logging.info("Python paths:")
        for i, path in enumerate(sys.path):
            logging.info(f"  {i}: {path}")
    else:
        # logging.info(f"scrapling package found at: {scrapling_spec.origin}") # Removed - purely informational

        # Try to import scrapling
        try:
            import scrapling
            # logging.info(
            #     f"scrapling version: {getattr(scrapling, '__version__', 'unknown')}") # Removed - purely informational

            # Try to import the fetchers module
            try:
                import scrapling.fetchers
                # logging.info("scrapling.fetchers module imported successfully") # Removed - purely informational

                # Check what's in the fetchers module
                dir_fetchers = dir(scrapling.fetchers)
                # logging.info(f"Contents of scrapling.fetchers: {dir_fetchers}") # Removed - purely informational

                if 'StealthyFetcher' in dir_fetchers:
                    # Assign the real StealthyFetcher
                    from scrapling.fetchers import StealthyFetcher

                    # Check for the async_fetch method
                    if hasattr(StealthyFetcher, 'async_fetch'):
                        STEALTHY_FETCHER_AVAILABLE = True
                        logging.info(
                            "StealthyFetcher available for fallback extraction")
                        # Log the parameter names for async_fetch to help with debugging
                        import inspect
                        if hasattr(inspect, 'signature') and callable(StealthyFetcher.async_fetch):
                            try:
                                sig = inspect.signature(
                                    StealthyFetcher.async_fetch)
                                # logging.info(
                                #     f"StealthyFetcher.async_fetch signature: {sig}") # Removed - purely informational
                                # logging.info(
                                #     f"Parameter names: {list(sig.parameters.keys())}") # Removed - purely informational
                            except Exception as sig_error:
                                logging.error(
                                    f"Error inspecting StealthyFetcher.async_fetch signature: {sig_error}")
                    else:
                        STEALTHY_FETCHER_AVAILABLE = False
                        logging.error(
                            "StealthyFetcher exists but doesn't have async_fetch method")
                        logging.info(
                            f"Available methods: {[m for m in dir(StealthyFetcher) if not m.startswith('__')]}")
                else:
                    logging.error(
                        "StealthyFetcher class not found in scrapling.fetchers module")
                    logging.info("Available attributes in scrapling.fetchers: " +
                                 ", ".join([x for x in dir_fetchers if not x.startswith('__')]))
                    STEALTHY_FETCHER_AVAILABLE = False
            except ImportError as fetchers_error:
                logging.error(
                    f"Failed to import scrapling.fetchers: {fetchers_error}")
                STEALTHY_FETCHER_AVAILABLE = False
        except ImportError as scrapling_error:
            logging.error(f"Failed to import scrapling: {scrapling_error}")
            STEALTHY_FETCHER_AVAILABLE = False
except ImportError:
    logging.error("Import error during inspection of scrapling package")
    STEALTHY_FETCHER_AVAILABLE = False
    logging.warning(
        "StealthyFetcher not available. Fallback capability will be limited.")

# If we're in Docker, try to explicitly install scrapling if not available
if os.environ.get('RUNNING_IN_DOCKER', 'false').lower() == 'true' and not STEALTHY_FETCHER_AVAILABLE:
    try:
        logging.info(
            "Attempting to install scrapling package in Docker environment")
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', 'scrapling==0.2.99'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            logging.info(
                "Successfully installed scrapling, trying import again")
            try:
                # Try importing again after installation
                import scrapling.fetchers
                from scrapling.fetchers import StealthyFetcher
                STEALTHY_FETCHER_AVAILABLE = True
                logging.info(
                    "StealthyFetcher now available after installation")
            except ImportError as e:
                logging.error(
                    f"Still can't import StealthyFetcher after installation: {e}")
        else:
            logging.error(f"Failed to install scrapling: {result.stderr}")
    except Exception as e:
        logging.error(f"Error during scrapling installation attempt: {e}")


# List of domains that we won't even try to scrape
NOT_TO_TRY_DOMAINS = [
    "thehill.com",
    "www.bloomberg.com",
    "www.businessinsider.com",
    "www.economist.com",
    "www.ft.com",
    "www.nytimes.com",
    "www.politico.com",
    "www.wsj.com"
    "www.semafor.com",
    "blockworks.co",
    "reason.com",
    "www.huffpost.com",
    "www.scmp.com",
    "deadline.com",
    "www.hollywoodreporter.com",
    "dnyuz.com",
    "variety.com",
    "studyfinds.org",
    "financialpost.com",
    "sports.yahoo.com",
    "www.bizjournals.com",
    "unherd.com",
    "www.msnbc.com",
    "www.theregister.com",
    "www.japantimes.co.jp",
    "www.forbes.com",
    "www.the-sun.com",
    "www.mediaite.com",
    "digiday.com",
    "www.coindesk.com",
    "autos.yahoo.com",
    "www.theblock.co",
    "theweek.com",
    "www.npr.org",
    "www.cbsnews.com",
    "247wallst.com",
    "www.bbc.com",
    "www.barchart.com",
    "www.the-independent.com",
    "www.usnews.com",
    "www.sfgate.com",
    "www.drudgereport.com"
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

# Tag for fallback logging
FALLBACK_TAG = "[FALLBACK]"

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

        # Add StealthyFetcher fallback configuration
        self.use_fallback = self.config.get("use_fallback", True)
        self.fallback_config = self.config.get("fallback_config", {})

        # Default fallback configuration for StealthyFetcher
        self.default_fallback_config = {
            "headless": True,
            "block_images": True,
            "disable_resources": True,
            "google_search": True,
            "block_webrtc": True,
            "humanize": True,
            "allow_webgl": True,
            "network_idle": True,
            "timeout": 45000,  # 45 seconds
            "geoip": False,  # Enable if proxy is used
            "os_randomize": True,
            # Docker-specific optimizations - pass browser args directly instead of in a nested structure
            "additional_arguments": ["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"],
            # Block ads for better performance
            "disable_ads": True,
            # Add additional headers for a more realistic browser
            "extra_headers": {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "DNT": "1"
            }
        }

        # Check if we're running in Docker to adjust configuration
        in_docker = os.environ.get(
            'RUNNING_IN_DOCKER', 'false').lower() == 'true'
        if in_docker:
            logger.info(
                f"{FALLBACK_TAG} Docker environment detected, applying container optimizations")
            # Adjust Firefox preferences for container environment
            if "--disable-setuid-sandbox" not in self.default_fallback_config["additional_arguments"]:
                self.default_fallback_config["additional_arguments"].append(
                    "--disable-setuid-sandbox")
            # Reduce memory usage
            self.default_fallback_config["block_images"] = True
            self.default_fallback_config["disable_resources"] = True

        # Check if StealthyFetcher is available for fallback
        self.stealthy_fetcher_available = STEALTHY_FETCHER_AVAILABLE
        if self.use_fallback and not self.stealthy_fetcher_available:
            logger.warning(
                f"{FALLBACK_TAG} StealthyFetcher fallback enabled but not available")
        elif self.use_fallback:
            logger.info(
                f"{FALLBACK_TAG} StealthyFetcher fallback enabled and available")

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
        # logger.info(
        #    f"SpecialStrategyExtractor initialized with Tor available: {self.tor_available}, Page capture: {PAGE_CAPTURE_AVAILABLE}") # Removed - purely informational

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
        Update detection history in memory and save the updated cumulative history to a file.

        Args:
            detection_type: Type of detection encountered
            url: URL where detection occurred

        Returns:
            None
        """
        # Track this detection in memory for the current instance
        now = datetime.now()
        domain = url.split('//')[-1].split('/')[0]

        self.detection_history['last_detection_time'] = now
        self.detection_history['detected_sites'].add(domain)

        if detection_type == 'captcha':
            self.detection_history['captcha_encounters'] += 1
        elif detection_type in ['blocked', 'rate_limited']:
            self.detection_history['blocked_pages'] += 1

        # Load existing history, update it, and save back to file
        try:
            # Ensure the capture directory exists
            os.makedirs(self.capture_dir, exist_ok=True)
            history_file = Path(self.capture_dir) / "detection_history.json"

            # Load existing history if file exists
            if history_file.exists():
                try:
                    with open(history_file, 'r') as f:
                        existing_history = json.load(f)
                except json.JSONDecodeError:
                    logger.warning(
                        f"Could not decode existing detection history file: {history_file}. Starting fresh.")
                    existing_history = {}
                except Exception as read_error:
                    logger.error(
                        f"Error reading existing history file {history_file}: {read_error}")
                    existing_history = {}  # Proceed with empty history if read fails
            else:
                existing_history = {}

            # Initialize keys if they don't exist in the loaded history
            existing_history.setdefault('captcha_encounters', 0)
            existing_history.setdefault('blocked_pages', 0)
            existing_history.setdefault('successful_extractions', 0)
            existing_history.setdefault('detected_sites', [])

            # Update cumulative counts and site list
            # Note: We use the in-memory self.detection_history which accumulates per instance
            # If multiple instances run, this might lead to slight undercounting if they finish close together.
            # A more robust solution might involve file locking or a central DB.
            updated_history = {
                'captcha_encounters': existing_history['captcha_encounters'] + (1 if detection_type == 'captcha' else 0),
                'blocked_pages': existing_history['blocked_pages'] + (1 if detection_type in ['blocked', 'rate_limited'] else 0),
                # Need to track successes explicitly
                'successful_extractions': existing_history['successful_extractions'] + self.detection_history.get('newly_successful', 0),
                'detected_sites': sorted(list(set(existing_history['detected_sites']) | {domain})),
                'last_detection_time': str(now)
            }
            # Reset newly successful count after adding it
            self.detection_history['newly_successful'] = 0

            # Write the updated history back to the file
            with open(history_file, 'w') as f:
                json.dump(updated_history, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save detection history: {e}")

    def _get_tor_proxy_info(self):
        """
        Get Tor proxy information formatted for StealthyFetcher.

        Returns:
            dict or str: Proxy information in StealthyFetcher format or None if not available
        """
        if not self.tor_available or not tor_integration:
            return None

        try:
            # Use the actual function available in tor_integration module
            proxy_url = tor_integration.get_tor_proxy_url()
            if not proxy_url:
                logger.warning(f"{FALLBACK_TAG} No Tor proxy URL available")
                return None

            # StealthyFetcher expects either a string URL or a dict with server, username, password
            # Check if this is already a properly formatted URL
            if isinstance(proxy_url, str) and proxy_url.startswith(('http://', 'socks://', 'socks5://')):
                logger.info(f"{FALLBACK_TAG} Using Tor proxy URL: {proxy_url}")
                return proxy_url

            # If we have a non-standard format, try to adapt it
            # This is a fallback in case the proxy information format changes
            tor_host = os.environ.get('TOR_HOST', '127.0.0.1' if not getattr(
                tor_integration, 'IN_DOCKER', False) else 'tor')
            tor_port = int(os.environ.get('TOR_SOCKS_PORT', 9050))

            # Format as SOCKS5 proxy for StealthyFetcher
            formatted_proxy = f"socks5://{tor_host}:{tor_port}"
            logger.info(
                f"{FALLBACK_TAG} Formatted Tor proxy URL: {formatted_proxy}")
            return formatted_proxy

        except Exception as e:
            logger.error(
                f"{FALLBACK_TAG} Error getting Tor proxy info for StealthyFetcher: {e}")
            return None

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

                # Record successful extraction in memory
                self.detection_history['successful_extractions'] += 1
                # Track that a success happened in this instance for saving
                self.detection_history['newly_successful'] = self.detection_history.get(
                    'newly_successful', 0) + 1

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
        # If all primary attempts failed, try StealthyFetcher fallback if enabled and available
        if self.use_fallback and self.stealthy_fetcher_available:
            logger.info(
                f"All primary extraction attempts failed for {url}. Trying StealthyFetcher fallback.")
            fallback_result = await self._extract_with_stealthy_fallback(url, merged_config)
            if fallback_result.get("success", False):
                logger.info(
                    f"StealthyFetcher fallback succeeded for {url}🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴")
                return fallback_result
            else:
                logger.warning(
                    f"StealthyFetcher fallback also failed for {url}")
        elif self.use_fallback and not self.stealthy_fetcher_available:
            logger.warning(
                f"StealthyFetcher fallback requested but not available for {url}")

        # If fallback is disabled or also failed, return failure
        return {
            "success": False,
            "error": f"Failed after {self.max_retries + 1} attempts" +
            (" and fallback" if self.use_fallback and self.stealthy_fetcher_available else ""),
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

    def _is_firefox_error(self, error_str):
        """
        Check if the error is related to Firefox browser issues.

        Args:
            error_str: Error message string

        Returns:
            bool: True if this is a Firefox/browser error, False otherwise
        """
        browser_error_patterns = [
            "firefox", "browser", "launch", "executable", "timeout",
            "crashed", "killed", "memory", "allocated", "spawn",
            "failed to launch", "process", "exited"
        ]

        error_str = error_str.lower()
        return any(pattern in error_str for pattern in browser_error_patterns)

    async def _extract_with_stealthy_fallback(self, url, config):
        """
        Extract content using StealthyFetcher as a fallback method.

        Args:
            url: URL to extract from
            config: Configuration dict

        Returns:
            dict: Extraction result with success status and content
        """
        # This method requires StealthyFetcher to be available
        if not STEALTHY_FETCHER_AVAILABLE:
            logger.error(
                f"{FALLBACK_TAG} StealthyFetcher not available but was attempted to be used")
            return {"success": False, "error": "StealthyFetcher not available", "url": url}

        # Track retry attempts for browser issues
        browser_retries = 2  # Maximum browser retry attempts

        for retry in range(browser_retries + 1):
            try:
                # logger.info(
                #    f"{FALLBACK_TAG} Configuring StealthyFetcher for {url}" +
                #    (f" (retry {retry})" if retry > 0 else "")) # Removed - purely informational
                # Combine default fallback config with user-provided options
                fallback_config = {
                    **self.default_fallback_config, **self.fallback_config}

                # We're not setting user agent parameter as both 'useragent' and 'user_agent' failed
                # Let StealthyFetcher use its default user agent
                if "user_agent" in config:
                    # logger.info(
                    #    f"{FALLBACK_TAG} Using default StealthyFetcher user agent (custom user agent ignored)") # Removed - purely informational
                    pass  # Keep the behavior, remove the log

                # Add proxy if Tor is configured and available
                if config.get("use_tor", False) and self.tor_available:
                    proxy_info = self._get_tor_proxy_info()
                    if proxy_info:
                        fallback_config["proxy"] = proxy_info
                        # Enable geoIP with proxy
                        fallback_config["geoip"] = True
                        logger.info(
                            f"{FALLBACK_TAG} Configured Tor proxy for StealthyFetcher")

                # Configure custom scrolling behavior similar to our primary method
                async def custom_scroll_behavior(page):
                    # logger.info(
                    #    f"{FALLBACK_TAG} Executing custom scroll behavior") # Removed - purely informational
                    # Get page height
                    page_height = await page.evaluate("() => document.body.scrollHeight")

                    # Perform several scroll actions with natural timing
                    scroll_count = random.randint(3, 5)
                    for i in range(scroll_count):
                        scroll_pos = int(page_height * (i+1) / scroll_count)
                        await page.mouse.wheel(0, scroll_pos)
                        await page.wait_for_timeout(random.randint(500, 1500))

                        # Add random pauses for reading (just like in primary method)
                        if random.random() < 0.3:
                            await page.wait_for_timeout(random.randint(800, 2000))

                    # Scroll back up partially sometimes (same behavior as primary method)
                    if random.random() < 0.7:
                        partial_scroll_back = random.uniform(0.2, 0.6)
                        back_position = int(page_height * partial_scroll_back)
                        await page.evaluate(f"window.scrollTo({{top: {back_position}, behavior: 'smooth'}})")
                        await page.wait_for_timeout(random.randint(300, 700))

                    return page

                fallback_config["page_action"] = custom_scroll_behavior

                # Configure selectors to wait for, using same content selectors as primary method
                content_selectors = [
                    "article", "main", ".content", "#content",
                    ".article", ".post", ".entry-content"
                ]
                if random.random() > 0.5:  # Randomize which selector to wait for
                    fallback_config["wait_selector"] = random.choice(
                        content_selectors)
                    fallback_config["wait_selector_state"] = "visible"
                    logger.info(
                        f"{FALLBACK_TAG} Waiting for selector: {fallback_config['wait_selector']}")

                # Check for and remove any unsupported parameters based on the documentation
                # These are the parameters supported according to more2.md (user agent related removed)
                supported_params = [
                    "headless", "block_images", "disable_resources", "google_search",
                    "extra_headers", "block_webrtc", "page_action", "addons",
                    "humanize", "allow_webgl", "geoip", "os_randomize", "disable_ads",
                    "network_idle", "timeout", "wait", "wait_selector",
                    "wait_selector_state", "proxy", "additional_arguments"
                ]

                # Remove any unsupported parameters
                unsupported_params = [k for k in list(
                    fallback_config.keys()) if k not in supported_params]
                for param in unsupported_params:
                    logger.warning(
                        f"{FALLBACK_TAG} Removing unsupported parameter: {param}")
                    fallback_config.pop(param, None)

                # Perform the extraction with StealthyFetcher
                logger.info(
                    f"{FALLBACK_TAG} Executing StealthyFetcher fallback for {url}")

                # Check again if StealthyFetcher is available before calling it
                # This check is technically redundant now but kept for safety
                if not STEALTHY_FETCHER_AVAILABLE or StealthyFetcher is None:
                    logger.error(
                        f"{FALLBACK_TAG} StealthyFetcher is not available but was attempted to be used")
                    return {"success": False, "error": "StealthyFetcher not available", "url": url}

                # Try async_fetch method first
                try:
                    # logger.info(
                    #    f"{FALLBACK_TAG} Trying StealthyFetcher.async_fetch method") # Removed - purely informational
                    response = await StealthyFetcher.async_fetch(url, **fallback_config)
                except TypeError as type_error:
                    # If we get a TypeError about unexpected argument, log the error
                    error_str = str(type_error)
                    logger.warning(
                        f"{FALLBACK_TAG} TypeError from async_fetch: {error_str}")

                    # Check if the error is about an unexpected keyword argument
                    import re
                    param_match = re.search(
                        r"unexpected keyword argument '(\w+)'", error_str)

                    if param_match:
                        bad_param = param_match.group(1)
                        logger.warning(
                            f"{FALLBACK_TAG} Removing problematic parameter: {bad_param}")
                        fallback_config.pop(bad_param, None)

                        # Try again without the problematic parameter
                        logger.info(
                            f"{FALLBACK_TAG} Retrying StealthyFetcher.async_fetch without {bad_param}")
                        try:
                            response = await StealthyFetcher.async_fetch(url, **fallback_config)
                        except Exception as e:
                            # If still failing, try the synchronous fetch method if available
                            if hasattr(StealthyFetcher, 'fetch') and callable(StealthyFetcher.fetch):
                                logger.info(
                                    f"{FALLBACK_TAG} Trying StealthyFetcher.fetch (synchronous) as fallback")
                                # Convert to async using a thread pool
                                import concurrent.futures
                                with concurrent.futures.ThreadPoolExecutor() as pool:
                                    response = await asyncio.get_event_loop().run_in_executor(
                                        pool, lambda: StealthyFetcher.fetch(
                                            url, **fallback_config)
                                    )
                            else:
                                # Both methods failed or fetch not available
                                raise Exception(
                                    f"Both async_fetch and fetch methods failed: {e}")
                    else:
                        # Not a parameter error, re-raise
                        raise

                if not response or not hasattr(response, 'html'):
                    logger.warning(
                        f"{FALLBACK_TAG} StealthyFetcher returned empty response for {url}")
                    return {"success": False, "error": "Empty response from fallback", "url": url}

                # logger.info(
                #    f"{FALLBACK_TAG} StealthyFetcher received response, extracting content") # Removed - purely informational

                # Extract content using StealthyFetcher's parsing API
                # Note: StealthyFetcher uses different parsing methods than Playwright
                try:
                    title = response.css_first("title::text")
                    if title and hasattr(title, 'clean'):
                        title = title.clean()
                    elif title:
                        title = str(title)
                    else:
                        title = ""
                except Exception as e:
                    logger.error(
                        f"{FALLBACK_TAG} Error extracting title with StealthyFetcher: {e}")
                    title = ""

                # Use the same content selectors as the primary method for consistency
                text_content = ""
                try:
                    # Extract content using StealthyFetcher's CSS selectors
                    for selector in content_selectors:
                        elements = response.css(selector)
                        if elements:
                            for element in elements:
                                # Use StealthyFetcher's text extraction methods
                                if hasattr(element, 'get_all_text'):
                                    content = element.get_all_text(strip=True)
                                elif hasattr(element, 'text'):
                                    content = element.text()
                                else:
                                    content = str(element)

                                if content and len(content) > 100:  # Skip short content
                                    text_content += content + "\n\n"

                            # If we found substantial content, stop looking
                            if len(text_content) > 500:
                                break

                    # If no content found with specific selectors, get body content
                    if not text_content:
                        logger.info(
                            f"{FALLBACK_TAG} No content found with selectors, trying body")
                        body = response.css_first("body")
                        if body:
                            if hasattr(body, 'get_all_text'):
                                text_content = body.get_all_text(strip=True)
                            elif hasattr(body, 'text'):
                                text_content = body.text()
                            else:
                                text_content = str(body)
                except Exception as e:
                    logger.error(
                        f"{FALLBACK_TAG} Error extracting content with StealthyFetcher: {e}")

                # Get metadata
                metadata = {}
                try:
                    for meta in response.css("meta"):
                        # StealthyFetcher uses .attrib to access attributes
                        name = meta.attrib.get(
                            "name") or meta.attrib.get("property")
                        content = meta.attrib.get("content")
                        if name and content:
                            metadata[name] = content
                except Exception as e:
                    logger.error(
                        f"{FALLBACK_TAG} Error extracting metadata with StealthyFetcher: {e}")

                # Record successful extraction in history
                # No need to increment self.detection_history here, handled by saving logic
                # self.detection_history['successful_extractions'] += 1
                # Track success for saving
                self.detection_history['newly_successful'] = self.detection_history.get(
                    'newly_successful', 0) + 1
                # Trigger save (or let _update_detection_history handle it if called for errors)
                # For simplicity, we'll let the file update only on errors for now.
                # To save on success: await self._update_detection_history('success', url)

                logger.info(
                    f"{FALLBACK_TAG} Successfully extracted content with StealthyFetcher🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴: {len(text_content)} chars")

                # Format the result to match the primary extraction method
                return {
                    "success": True,
                    "content": {
                        "title": title,
                        "content": text_content.strip(),
                        "metadata": metadata,
                        "url": getattr(response, 'url', url),
                        "timestamp": datetime.now().isoformat(),
                        "source": "stealthy_fallback"  # Mark the source as fallback
                    },
                    "url": getattr(response, 'url', url)
                }

            except Exception as e:
                error_str = str(e)
                logger.error(
                    f"{FALLBACK_TAG} Error in StealthyFetcher fallback: {error_str}")

                # Check if this is a browser error that might be recovered with retry
                if retry < browser_retries and self._is_firefox_error(error_str):
                    logger.info(
                        f"{FALLBACK_TAG} Browser error detected, will retry ({retry+1}/{browser_retries})")
                    # Add a delay before retry
                    await asyncio.sleep(2)
                    continue

                return {"success": False, "error": f"Fallback extraction failed: {error_str}", "url": url}

        # We should never reach here, but just in case
        return {"success": False, "error": "Fallback extraction failed after retries", "url": url}


async def extract_with_special_strategy(url: str, user_agent: str = None) -> tuple:
    """
    Compatibility wrapper function for backward compatibility with old code.

    Args:
        url: URL to extract content from
        user_agent: User agent string to use

    Returns:
        tuple: (content, final_url) or (None, None) if extraction fails
    """
    # logger.info(f"Using compatibility wrapper for special strategy on {url}") # Removed - purely informational
    try:
        # Create config dict with user agent
        config = {"user_agent": user_agent} if user_agent else {}

        # Enable fallback by default in compatibility mode
        config["use_fallback"] = True

        # Create extractor instance
        extractor = SpecialStrategyExtractor(config)

        # Call the extract method
        result = await extractor.extract(url, config)

        # Process the result
        if result and result.get("success", False):
            content_data = result.get("content", {})

            # Handle both string content and dict content formats
            # The fallback returns a dict, while the primary returns content directly
            if isinstance(content_data, dict):
                content = content_data.get("content", "")
                source = content_data.get("source", "primary")
                logger.info(
                    f"Using content from {source} source: {len(content)} chars")
            else:
                content = content_data
                logger.info(
                    f"Using content from primary source: {len(content)} chars")

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
