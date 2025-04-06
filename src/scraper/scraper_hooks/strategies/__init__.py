"""
Scraper Strategies Module

This module contains various scraping strategies for different content extraction scenarios.
It provides a modular approach to web scraping with specialized components for different aspects
of the scraping process.

Exported Modules:
- tor_integration: Module for Tor network integration
  - is_available() -> bool: Checks if Tor support is available
  - is_ready() -> bool: Checks if Tor is ready to use
  - setup_tor_for_browser(browser_options) -> Dict: Configures browser for Tor usage
  - rotate_tor_connection() -> bool: Rotates Tor connection for new IP

- url_handlers: Module for handling special URL types
  - handle_special_url(page, url) -> str: Handles special URL types
  - detect_biztoc_url(url) -> bool: Detects if URL is from biztoc.com
  - detect_google_news_url(url) -> bool: Detects if URL is from Google News

- consent_handler: Module for handling consent dialogs and overlays
  - handle_consent_dialogs(page) -> bool: Handles cookie consent dialogs
  - remove_overlay_elements(page) -> bool: Removes overlay elements from page

- content_extraction: Module for extracting content from web pages
  - extract_content(page, content_selectors) -> str: Extracts content from page
  - is_content_too_short(content, min_chars, min_words) -> bool: Checks content length
  - wait_for_content_selectors(page, selectors) -> bool: Waits for content to load

- page_capture: Module for capturing page state for debugging purposes
  - setup_capture_dir(base_dir) -> str: Creates capture directory
  - capture_page_state(page, url, success, attempt, reason, base_dir) -> str: Captures page state
  - capture_on_failure(page, url, content, min_chars, sample_rate, base_dir) -> bool: Captures failed extractions
  - cleanup_old_captures(base_dir, max_age_days, max_captures_per_domain) -> int: Cleans up old captures

- browser_setup: Module for browser context configuration and setup
  - get_default_browser_args() -> List[str]: Returns default browser arguments
  - create_browser_context(url, user_agent, use_tor) -> Tuple: Creates browser context
  - setup_device_emulation(playwright, user_agent) -> Dict: Sets up device emulation
  - create_page_for_url(url, user_agent, use_tor) -> Tuple: Creates page for URL
  - close_browser_resources(playwright, browser, context, page) -> bool: Closes browser resources

Exported Classes:
- SpecialStrategyExtractor: Class for extracting content from restricted websites
  - extract(url, user_agent) -> Tuple[str, str]: Main method for extraction
  
Exported Functions:
- extract_with_special_strategy(url, user_agent) -> Tuple[str, str]: Function wrapper for backward compatibility
"""

from .special_strategy import SpecialStrategyExtractor, extract_with_special_strategy
from . import tor_integration
from . import url_handlers
from . import consent_handler
from . import content_extraction
from . import page_capture
from . import browser_setup
