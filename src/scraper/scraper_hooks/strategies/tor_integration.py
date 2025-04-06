"""
Tor Integration Module for Browser-Based Scraping

This module provides Tor proxy integration for browser-based scraping strategies,
enabling IP rotation and anonymous web browsing for accessing restricted content.

Exported Functions:
- setup_tor_for_browser(browser_options) -> dict: Configures browser options for Tor use
- should_use_tor(domain) -> bool: Determines if Tor should be used for a given domain
- rotate_tor_connection() -> bool: Requests a new Tor circuit (rotates IP)
- is_available() -> bool: Checks if Tor integration is available
- is_ready() -> bool: Checks if Tor is available and running

Related Files:
- src/scraper/tor/tor_client.py: Core Tor client functionality
- src/scraper/scraper_hooks/strategies/special_strategy.py: Special strategy that uses Tor integration

Dependencies:
- src/scraper/tor/tor_client.py: Provides core Tor functionality
"""

import asyncio
import random
import socket
from urllib.parse import urlparse
import os

# Docker environment detection
IN_DOCKER = os.environ.get('RUNNING_IN_DOCKER', 'false').lower(
) == 'true' or os.path.exists('/.dockerenv')

# Import Tor functionality from dedicated module with robust error handling
try:
    from ...tor.tor_client import (
        is_tor_available,
        is_tor_running,
        rotate_tor_ip,
        get_tor_proxy_url
    )

    # Test Tor availability immediately
    tor_available = is_tor_available()

    if tor_available:
        # Check if Tor is actually running
        tor_running = is_tor_running()

        # Get Tor proxy URL
        proxy_url = get_tor_proxy_url()

    TOR_SUPPORT = tor_available
except ImportError:
    TOR_SUPPORT = False
    # Define stub functions to avoid errors

    def is_tor_available():
        return False

    def is_tor_running():
        return False

    def rotate_tor_ip():
        return False

    def get_tor_proxy_url():
        return None
except Exception:
    TOR_SUPPORT = False
    # Define stub functions with the same interface
    def is_tor_available(): return False
    def is_tor_running(): return False
    def rotate_tor_ip(): return False
    def get_tor_proxy_url(): return None

# Domains that require or benefit from Tor access
TOR_REQUIRED_DOMAINS = [
    "bloomberg.com",
    "wsj.com",
    "ft.com",
    "nytimes.com",
    "economist.com",
    "businessinsider.com",
]


def is_available():
    """
    Check if Tor integration is available

    Returns:
        bool: True if Tor is available, False otherwise
    """
    available = TOR_SUPPORT and is_tor_available()
    return available


def is_ready():
    """
    Check if Tor is available and running

    Returns:
        bool: True if Tor is available and running, False otherwise
    """
    ready = is_available() and is_tor_running()

    # Manual connection check as a fallback if tor_client says it's ready
    if ready:
        try:
            # Use the TOR_HOST from environment or default
            tor_host = os.environ.get(
                'TOR_HOST', '127.0.0.1' if not IN_DOCKER else 'tor')
            tor_port = int(os.environ.get('TOR_SOCKS_PORT', 9050))

            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)  # Increased timeout for Docker networking
            s.connect((tor_host, tor_port))
            s.close()
            return True
        except Exception:
            return False

    return ready


def should_use_tor(domain):
    """
    Determine if Tor should be used for a given domain

    Args:
        domain: Domain name to check

    Returns:
        bool: True if Tor should be used for this domain
    """
    if not is_available():
        return False

    domain = domain.lower() if isinstance(domain, str) else ''

    # Check if domain is in our list of sites that need Tor
    for tor_domain in TOR_REQUIRED_DOMAINS:
        if tor_domain in domain:
            return True

    return False


async def rotate_tor_connection(delay=3.0):
    """
    Request a new Tor circuit (rotate IP)

    Args:
        delay: Delay in seconds to wait after rotation for new circuit establishment

    Returns:
        bool: True if rotation was successful, False otherwise
    """
    if not is_ready():
        return False

    try:
        rotation_success = rotate_tor_ip()

        if rotation_success:
            # Add slight randomization to rotation timing
            actual_delay = random.uniform(max(1.0, delay - 0.5), delay + 0.5)
            await asyncio.sleep(actual_delay)
            return True
        else:
            return False
    except Exception:
        return False


def setup_tor_for_browser(browser_options, use_tor=True):
    """
    Configure browser options to use Tor

    Args:
        browser_options: Dictionary of browser launch options
        use_tor: Whether to use Tor (will be ignored if Tor is not available)

    Returns:
        dict: Updated browser options with Tor proxy configuration
    """
    if not use_tor or not is_ready():
        return browser_options

    try:
        tor_proxy_url = get_tor_proxy_url()

        if tor_proxy_url:
            if "proxy" not in browser_options:
                browser_options["proxy"] = {}

            browser_options["proxy"].update({
                "server": tor_proxy_url,
                "bypass": "localhost"
            })
    except Exception:
        pass

    return browser_options
