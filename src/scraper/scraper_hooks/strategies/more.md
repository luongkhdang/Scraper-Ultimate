# StealthyFetcher Integration Implementation Plan

This document outlines specific implementation steps needed to integrate StealthyFetcher as a fallback mechanism in `special_strategy.py` when the primary extraction method fails.

## Step 0: Clarify StealthyFetcher API Understanding

Before implementation, we need to clarify several aspects about StealthyFetcher:

1. **API Return Value**:

   - StealthyFetcher returns a Response-like object with various parsing methods
   - It provides CSS selector methods like `.css_first()`, `.css()`
   - Element objects have methods like `.clean()`, `.text()`, `.re_first()` for text extraction
   - Attributes are accessed via `.attrib` dictionary (e.g., `element.attrib['src']`)
   - The parsing API is more similar to Parsel/Scrapy than to Playwright's DOM methods

2. **Parameter Names**:

   - Custom user agent parameter is `useragent` (not `user_agent`)
   - Most parameter names follow lowercase_underscore convention
   - Parameter names must match exactly as documented

3. **Browser Engine**:

   - Uses Playwright as the underlying engine
   - Specifically configured with a modified Firefox browser (Camoufox)
   - Not a separate engine but a specialized configuration

4. **Content Extraction API**:

   - Use `.css_first(selector)` for single elements
   - Use `.css(selector)` for multiple elements
   - Text extraction: `.clean()` for cleaned text, `.text()` for raw text
   - Regex extraction: `.re_first(pattern)` for first match
   - Full attribute access via `.attrib` dictionary

5. **Dependency on scrapling**:

   - Requires installation of the `scrapling` package
   - Not a standalone implementation
   - Need proper error handling for when package is missing

6. **Addon Handling**:

   - Requires paths to extracted addons (unpacked directories)
   - Not XPI files, but extracted addon directories
   - Addons are installed at browser launch time

7. **Page Action Function**:
   - Crucial for complex sites
   - Must return the page object
   - Executed after network idle but before selector waits
   - Function signature must match expected type (async for async_fetch)

## Step 1: Add Dependencies and Imports

Add required import with proper error handling:

```python
# At the top of special_strategy.py, with other imports
try:
    from scrapling.fetchers import StealthyFetcher
    STEALTHY_FETCHER_AVAILABLE = True
except ImportError:
    STEALTHY_FETCHER_AVAILABLE = False
    logging.warning(
        "StealthyFetcher not available. Fallback capability will be limited.")
```

## Step 2: Add Configuration Options

Modify the `SpecialStrategyExtractor.__init__` method to add fallback configuration:

```python
def __init__(self, config=None):
    # Existing initialization code...

    # Add fallback configuration
    self.use_fallback = self.config.get("use_fallback", True)
    self.fallback_config = self.config.get("fallback_config", {})

    # Default fallback configuration
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
        "os_randomize": True
    }

    # Check if StealthyFetcher is available
    self.stealthy_fetcher_available = STEALTHY_FETCHER_AVAILABLE
    if self.use_fallback and not self.stealthy_fetcher_available:
        logger.warning("StealthyFetcher fallback enabled but not available")
```

## Step 3: Add Helper Method to Get Tor Proxy Info

### Analysis of Existing Tor Integration

Upon reviewing the tor_integration.py module, we found:

1. **Available Functions**:

   - `is_available()`: Checks if Tor integration is available
   - `is_ready()`: Checks if Tor is available and running
   - `rotate_tor_connection(delay=3.0)`: Rotates Tor circuit for new IP
   - `setup_tor_for_browser(browser_options, use_tor=True)`: Configures browser options for Tor

2. **Missing Functions**:

   - The previously suggested `get_proxy_details()` method does not exist
   - Instead, there's a `get_tor_proxy_url()` function available

3. **Internal Implementation**:

   - The module imports more specific functions from `...tor.tor_client`
   - These include `is_tor_available()`, `is_tor_running()`, `rotate_tor_ip()`, and `get_tor_proxy_url()`

4. **Environmental Awareness**:
   - The module detects Docker environments
   - It handles different host configurations based on environment

### Corrected Implementation

Add a method to extract proxy information for StealthyFetcher from Tor that works with the existing tor_integration module:

```python
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
            logger.warning("No Tor proxy URL available")
            return None

        # StealthyFetcher expects either a string URL or a dict with server, username, password
        # Check if this is already a properly formatted URL
        if isinstance(proxy_url, str) and proxy_url.startswith(('http://', 'socks://', 'socks5://')):
            logger.info(f"Using Tor proxy URL: {proxy_url}")
            return proxy_url

        # If we have a non-standard format, try to adapt it
        # This is a fallback in case the proxy information format changes
        tor_host = os.environ.get('TOR_HOST', '127.0.0.1' if not getattr(tor_integration, 'IN_DOCKER', False) else 'tor')
        tor_port = int(os.environ.get('TOR_SOCKS_PORT', 9050))

        # Format as SOCKS5 proxy for StealthyFetcher
        formatted_proxy = f"socks5://{tor_host}:{tor_port}"
        logger.info(f"Formatted Tor proxy URL: {formatted_proxy}")
        return formatted_proxy

    except Exception as e:
        logger.error(f"Error getting Tor proxy info for StealthyFetcher: {e}")
        return None
```

### Differences From Original Implementation:

1. **Direct Function Usage**:

   - Uses `get_tor_proxy_url()` from tor_integration instead of the non-existent `get_proxy_details()`

2. **Environmental Awareness**:

   - Adopts the same environment variable usage as in tor_integration.py
   - Handles Docker environments through the IN_DOCKER flag

3. **Enhanced Logging**:

   - Adds more detailed logging to track proxy configuration

4. **Simplified Format Handling**:

   - Focuses on the SOCKS5 format which is most compatible with Tor
   - Retains direct URL usage when available

5. **Integration with tor_integration Module**:
   - Directly uses functions available in tor_integration
   - Falls back to environment variables as a last resort, matching the approach in tor_integration

This corrected implementation ensures proper integration with the existing Tor functionality while providing the proxy information in a format suitable for StealthyFetcher.

## Step 4: Implement Fallback Extraction Method

Add the method to handle StealthyFetcher extraction:

```python
async def _extract_with_stealthy_fallback(self, url, config):
    """
    Extract content using StealthyFetcher as a fallback method.

    Args:
        url: URL to extract from
        config: Configuration dict

    Returns:
        dict: Extraction result with success status and content
    """
    if not STEALTHY_FETCHER_AVAILABLE:
        return {"success": False, "error": "StealthyFetcher not available", "url": url}

    try:
        # Combine default fallback config with user-provided options
        fallback_config = {**self.default_fallback_config, **self.fallback_config}

        # Add user agent if specified - note the parameter name is "useragent"
        if "user_agent" in config:
            fallback_config["useragent"] = config["user_agent"]

        # Add proxy if Tor is configured and available
        if config.get("use_tor", False) and self.tor_available:
            proxy_info = self._get_tor_proxy_info()
            if proxy_info:
                fallback_config["proxy"] = proxy_info
                fallback_config["geoip"] = True  # Enable geoIP with proxy

        # Configure custom scrolling behavior
        async def custom_scroll_behavior(page):
            # Get page height
            page_height = await page.evaluate("() => document.body.scrollHeight")

            # Perform several scroll actions with natural timing
            scroll_count = random.randint(3, 5)
            for i in range(scroll_count):
                scroll_pos = int(page_height * (i+1) / scroll_count)
                await page.mouse.wheel(0, scroll_pos)
                await page.wait_for_timeout(random.randint(500, 1500))
            return page

        fallback_config["page_action"] = custom_scroll_behavior

        # Configure selectors to wait for, based on common content containers
        content_selectors = ["article", "main", ".content", "#content", ".article"]
        if random.random() > 0.5:  # Randomize which selector to wait for
            fallback_config["wait_selector"] = random.choice(content_selectors)
            fallback_config["wait_selector_state"] = "visible"

        # Perform the extraction with StealthyFetcher
        logger.info(f"Executing StealthyFetcher fallback for {url}")
        response = await StealthyFetcher.async_fetch(url, **fallback_config)

        if not response or not hasattr(response, 'html'):
            logger.warning(f"StealthyFetcher returned empty response for {url}")
            return {"success": False, "error": "Empty response from fallback", "url": url}

        # Extract content using StealthyFetcher's parsing API
        # Note: StealthyFetcher uses different parsing methods than Playwright
        try:
            title = response.css_first("title::text")
            if title and hasattr(title, 'clean'):
                title = title.clean()
        except Exception as e:
            logger.error(f"Error extracting title with StealthyFetcher: {e}")
            title = ""

        # Use the same content selectors as the primary method
        content_selectors = [
            "article", "main", ".content", "#content",
            ".article", ".post", ".entry-content"
        ]

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
                            continue

                        if content and len(content) > 100:  # Skip short content
                            text_content += content + "\n\n"

                    # If we found substantial content, stop looking
                    if len(text_content) > 500:
                        break

            # If no content found with specific selectors, get body content
            if not text_content:
                body = response.css_first("body")
                if body:
                    if hasattr(body, 'get_all_text'):
                        text_content = body.get_all_text(strip=True)
                    elif hasattr(body, 'text'):
                        text_content = body.text()
        except Exception as e:
            logger.error(f"Error extracting content with StealthyFetcher: {e}")

        # Get metadata
        metadata = {}
        try:
            for meta in response.css("meta"):
                # StealthyFetcher uses .attrib to access attributes
                name = meta.attrib.get("name") or meta.attrib.get("property")
                content = meta.attrib.get("content")
                if name and content:
                    metadata[name] = content
        except Exception as e:
            logger.error(f"Error extracting metadata with StealthyFetcher: {e}")

        # Record successful extraction in history
        self.detection_history['successful_extractions'] += 1

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
        logger.error(f"Error in StealthyFetcher fallback: {e}")
        return {"success": False, "error": f"Fallback extraction failed: {str(e)}", "url": url}
```

## Step 5: Modify the Main Extract Method

Update the main `extract` method to use the fallback when primary extraction fails:

```python
async def extract(self, url, config=None):
    # Existing code for checking domain blocklist...

    # Existing code for retries...

    # At the end of the method, where it currently returns failure:
    # Replace this:
    # return {
    #     "success": False,
    #     "error": f"Failed after {self.max_retries + 1} attempts",
    #     "url": url
    # }

    # With this:
    # All attempts failed, try fallback if enabled
    if self.use_fallback and STEALTHY_FETCHER_AVAILABLE:
        logger.info(f"All primary extraction attempts failed for {url}. Trying StealthyFetcher fallback.")
        fallback_result = await self._extract_with_stealthy_fallback(url, merged_config)
        if fallback_result.get("success", False):
            logger.info(f"StealthyFetcher fallback succeeded for {url}")
            return fallback_result
        else:
            logger.warning(f"StealthyFetcher fallback also failed for {url}")

    # If fallback is disabled or also failed
    return {
        "success": False,
        "error": f"Failed after {self.max_retries + 1} attempts and fallback",
        "url": url
    }
```

## Step 6: Update the Compatibility Function

Update the compatibility wrapper function:

```python
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
            if isinstance(content_data, dict):
                content = content_data.get("content", "")
            else:
                content = content_data

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
```

## Step 7: Add Proper Error Handling and Logging

Enhance logging throughout to provide visibility into the fallback process:

```python
# Add to the top of the file with other constants
FALLBACK_TAG = "[FALLBACK]"

# In _extract_with_stealthy_fallback method
logger.info(f"{FALLBACK_TAG} Configuring StealthyFetcher for {url}")
# More logging throughout the method...

# Add structured logging format to track which extraction method was used
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("scraper.log")
    ]
)
```

## Step 8: Add Documentation and Comments

Update the module docstring to include information about the fallback capability:

```python
"""
Special Strategy Extractor for handling restricted and protected sites.

This module implements advanced extraction strategies for sites with anti-bot measures.
Includes adaptive retry mechanisms, randomized behaviors, and detection countermeasures.
Now includes StealthyFetcher fallback for sites where the primary method fails.

...existing docstring content...

Exports:
    - SpecialStrategyExtractor: Main extractor class for protected sites with fallback
    - extract_with_special_strategy: Compatibility function for backward compatibility

Related files:
    ...existing related files...
"""
```

## Step 9: Add Installation Requirements

Create or update a requirements file to include the scrapling package:

```
# requirements.txt (or add to existing file)
scrapling>=1.0.0  # Adjust version as needed
```

## Step 10: Test the Implementation

Create a testing script to validate the fallback mechanism:

```python
# test_fallback.py
import asyncio
import logging
from src.scraper.scraper_hooks.strategies.special_strategy import SpecialStrategyExtractor

logging.basicConfig(level=logging.INFO)

async def test_fallback():
    # Test with a site known to be difficult for the primary method
    url = "https://example-with-protection.com"
    extractor = SpecialStrategyExtractor({
        "max_retries": 1,  # Reduce retries for faster testing
        "use_fallback": True,
        "fallback_config": {
            "headless": True,
            "block_images": True,
            "humanize": 1.5
        }
    })

    result = await extractor.extract(url)
    print(f"Success: {result.get('success', False)}")
    if result.get('success', False):
        content = result.get('content', {})
        if isinstance(content, dict):
            print(f"Source: {content.get('source', 'primary')}")
            print(f"Title: {content.get('title', '')}")
            print(f"Content length: {len(content.get('content', ''))}")
        else:
            print(f"Content length: {len(content)}")
    else:
        print(f"Error: {result.get('error', 'Unknown')}")

if __name__ == "__main__":
    asyncio.run(test_fallback())
```

## Implementation Notes and Best Practices

1. **Graceful Degradation**: The implementation gracefully handles the absence of StealthyFetcher
2. **Parameter Compatibility**: Pay close attention to parameter naming (e.g., `useragent` not `user_agent`)
3. **Content Extraction**: Handle differences in the content extraction API
4. **Error Handling**: Extensive try/except blocks to prevent cascading failures
5. **Performance Considerations**: StealthyFetcher with all stealth features may be slower than primary method
6. **Proxy Handling**: Ensure proper translation of proxy information between systems
7. **Response Processing**: Handle potential differences in the response structure
8. **Logging Strategy**: Use distinct logging tags to identify fallback operations

By following this implementation plan, we can successfully integrate StealthyFetcher as a fallback mechanism in our existing scraping system, providing a more robust solution for handling protected websites.
