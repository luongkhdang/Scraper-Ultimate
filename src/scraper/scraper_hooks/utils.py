"""
Scraper Utilities: Common utility functions for the web scraper.

Exported Functions:
- get_random_user_agent() -> str: Returns a random user agent string from a predefined list
- get_realistic_headers(url: str = None, referrer: str = None) -> Dict[str, str]: Generates realistic HTTP headers
- random_delay(min_seconds: float = 1.0, max_seconds: float = 5.0) -> None: Adds a random delay to mimic human behavior
- make_request(url: str, headers: Dict[str, str] = None, max_retries: int = 3) -> Optional[requests.Response]: Makes HTTP request with retry logic

Related Files:
- src/scraper/scraper_hooks/url_extractor.py: Uses these utilities for extracting article URLs
- src/scraper/scraper_hooks/content_extractor.py: Uses these utilities for extracting article content
"""
import random
import time
import logging
import requests
from typing import Dict, Optional, List

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_user_agents() -> List[str]:
    """Load a list of realistic user agents"""
    return [
        # Chrome
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
        # Firefox
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:95.0) Gecko/20100101 Firefox/95.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:95.0) Gecko/20100101 Firefox/95.0",
        # Safari
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
        # Edge
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36 Edg/96.0.1054.62",
        # Mobile
        "Mozilla/5.0 (iPhone; CPU iPhone OS 15_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Android 12; Mobile; rv:95.0) Gecko/95.0 Firefox/95.0",
        "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.104 Mobile Safari/537.36"
    ]


# Load user agents once at module level
USER_AGENTS = load_user_agents()

# Common referrers
REFERRERS = [
    "https://www.google.com/",
    "https://www.bing.com/",
    "https://www.yahoo.com/",
    "https://duckduckgo.com/",
    "https://www.reddit.com/",
    "https://twitter.com/",
    "https://www.facebook.com/",
    "https://news.ycombinator.com/"
]


def get_random_user_agent() -> str:
    """Get a random user agent from the list"""
    return random.choice(USER_AGENTS)


def get_referrer(url: str = None) -> str:
    """Get a realistic referrer URL"""
    if url:
        # Sometimes use the target domain as referrer to simulate internal navigation
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
        all_referrers = REFERRERS + [domain]
    else:
        all_referrers = REFERRERS

    return random.choice(all_referrers)


def get_realistic_headers(url: str = None, referrer: str = None) -> Dict[str, str]:
    """Generate realistic HTTP headers"""
    user_agent = get_random_user_agent()
    if not referrer:
        referrer = get_referrer(url)

    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
        "TE": "Trailers",
    }

    # Add referrer sometimes (80% of the time)
    if random.random() < 0.8:
        headers["Referer"] = referrer

    # Add DNT (Do Not Track) header sometimes
    if random.random() < 0.4:
        headers["DNT"] = "1"

    # Add other realistic headers occasionally
    if random.random() < 0.3:
        headers["Sec-Fetch-Dest"] = "document"
        headers["Sec-Fetch-Mode"] = "navigate"
        if url and referrer:
            from urllib.parse import urlparse
            headers["Sec-Fetch-Site"] = "same-origin" if urlparse(
                url).netloc == urlparse(referrer).netloc else "cross-site"
        else:
            headers["Sec-Fetch-Site"] = "cross-site"
        headers["Sec-Fetch-User"] = "?1"

    return headers


def random_delay(min_seconds: float = 1.0, max_seconds: float = 5.0) -> None:
    """Add a random delay to mimic human browsing behavior"""
    delay = random.uniform(min_seconds, max_seconds)
    logger.debug(f"Adding random delay of {delay:.2f} seconds")
    time.sleep(delay)


def make_request(url: str, headers: Dict[str, str] = None, max_retries: int = 3) -> Optional[requests.Response]:
    """Make a request with retry logic and rotation of user agents"""
    retries = 0

    if headers is None:
        headers = get_realistic_headers(url)

    while retries < max_retries:
        # Add a random delay before each request
        random_delay(0.5, 3.0)

        try:
            logger.info("Making direct connection request")
            response = requests.get(
                url,
                headers=headers,
                timeout=10,
                allow_redirects=True
            )

            # Log if we were redirected
            if len(response.history) > 0:
                logger.info(
                    f"Request was redirected: {' -> '.join([r.url for r in response.history])}")

            if response.status_code == 200:
                return response
            elif response.status_code in [403, 429]:
                # If we get blocked, wait longer before retrying
                logger.warning(
                    f"Received status code {response.status_code} - possibly rate limited")
                time.sleep(random.uniform(5.0, 10.0))
            else:
                logger.warning(
                    f"Received status code {response.status_code}")

        except requests.exceptions.ConnectTimeout:
            logger.warning(f"Connection timeout")
        except requests.exceptions.ReadTimeout:
            logger.warning(f"Read timeout")
        except Exception as e:
            logger.warning(f"Request failed: {e}")

        retries += 1
        # Increase delay with each retry attempt
        time.sleep(1 + retries)

        # Change the user agent on retry for better stealth
        headers = get_realistic_headers(url)

    logger.error(f"Failed to fetch {url} after {max_retries} retries")
    return None
