"""
Tor Module: Provides functionality for using Tor network with web scraping.

This module enables IP rotation and anonymous browsing through the Tor network
for scraping sites with paywalls and advanced bot detection.
"""

from .tor_client import (
    is_tor_running,
    rotate_tor_ip,
    get_tor_proxy_url,
    is_tor_available,
    TorClient
)

__all__ = [
    'is_tor_running',
    'rotate_tor_ip',
    'get_tor_proxy_url',
    'is_tor_available',
    'TorClient'
]
