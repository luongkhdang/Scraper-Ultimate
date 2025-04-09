# StealthyFetcher Integration as Fallback for SpecialStrategyExtractor

## Overview

This document outlines a strategy for integrating the StealthyFetcher as a fallback mechanism for the SpecialStrategyExtractor. The goal is to provide a robust, multi-layered approach to web scraping that can handle increasingly sophisticated anti-bot protection systems.

## Current Architecture Analysis

The current `SpecialStrategyExtractor` implements various anti-bot evasion techniques:

1. **Multiple retry attempts** with adaptive delays
2. **Tor IP rotation** to bypass IP-based blocking
3. **Browser fingerprint randomization** to avoid detection
4. **Human-like scrolling and interaction** behaviors
5. **Consent dialog handling** and overlay removal

Despite these measures, some sites with advanced protection may still detect and block our scraper. This is where StealthyFetcher can serve as a powerful fallback option.

## StealthyFetcher Capabilities

StealthyFetcher offers several unique advantages over our current implementation:

1. **Camoufox Integration**: Uses a modified Firefox browser specifically designed for anti-bot evasion
2. **Advanced Fingerprinting Control**: More comprehensive browser fingerprint manipulation
3. **Human Behavior Simulation**: Mouse movement humanization and realistic interaction patterns
4. **Built-in Referrer Spoofing**: Google search referrer simulation for more natural traffic patterns
5. **Resource Control**: Selective loading of resources (images, fonts, etc.) for performance and reduced detection
6. **WebRTC/WebGL Control**: Precise control over technologies that can leak information
7. **GeoIP Integration**: Adapts browser language and timezone to proxy location

## Integration Approach

### 1. Minimal Dependency Addition

Import StealthyFetcher with proper error handling:

```python
try:
    from scrapling.fetchers import StealthyFetcher
    STEALTHY_FETCHER_AVAILABLE = True
except ImportError:
    STEALTHY_FETCHER_AVAILABLE = False
    logging.warning("StealthyFetcher not available. Fallback capability will be limited.")
```

### 2. Configuration Options

Add configuration parameters in the `SpecialStrategyExtractor` constructor:

```python
self.use_fallback = self.config.get("use_fallback", True)
self.fallback_config = self.config.get("fallback_config", {})
```

Default fallback configuration:

```python
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
```

### 3. Fallback Mechanism

Modify the extract method to attempt StealthyFetcher when all regular attempts fail:

```python
# Add this at the end of the extract method, after all attempts failed
if self.use_fallback and STEALTHY_FETCHER_AVAILABLE:
    logger.info(f"All standard attempts failed. Trying fallback with StealthyFetcher for {url}")
    fallback_result = await self._extract_with_stealthy_fallback(url, merged_config)
    if fallback_result.get("success", False):
        return fallback_result

# Return failure if all attempts (including fallback) fail
return {
    "success": False,
    "error": f"Failed after {self.max_retries + 1} attempts and fallback",
    "url": url
}
```

### 4. Fallback Implementation

Add a method to handle the StealthyFetcher extraction:

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
    try:
        # Combine default fallback config with user-provided options
        fallback_config = {**self.default_fallback_config, **self.fallback_config}

        # Add user agent if specified
        if "user_agent" in config:
            fallback_config["useragent"] = config["user_agent"]

        # Add proxy if Tor is configured and available
        if config.get("use_tor", False) and self.tor_available:
            proxy_info = tor_integration.get_tor_proxy_info()
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

        if not response or not response.html:
            logger.warning(f"StealthyFetcher returned empty response for {url}")
            return {"success": False, "error": "Empty response from fallback", "url": url}

        # Extract content from response using same selector strategy as primary method
        title = response.css_first("title::text")

        text_content = ""
        for selector in self.content_selectors:  # Reuse selectors from main extraction method
            elements = response.css(selector)
            if elements:
                for element in elements:
                    content = element.text()
                    if content and len(content) > 100:
                        text_content += content + "\n\n"

                if len(text_content) > 500:
                    break

        # If no content found with selectors, get body content
        if not text_content:
            body = response.css_first("body")
            if body:
                text_content = body.text()

        # Get metadata just like in primary extraction
        metadata = {}
        for meta in response.css("meta"):
            name = meta.attrib.get("name") or meta.attrib.get("property")
            content = meta.attrib.get("content")
            if name and content:
                metadata[name] = content

        # Record successful extraction in history
        self.detection_history['successful_extractions'] += 1

        return {
            "success": True,
            "content": {
                "title": title,
                "content": text_content.strip(),
                "metadata": metadata,
                "url": response.url,
                "timestamp": datetime.now().isoformat(),
                "source": "stealthy_fallback"  # Mark the source as fallback
            },
            "url": response.url
        }

    except Exception as e:
        logger.error(f"Error in StealthyFetcher fallback: {e}")
        return {"success": False, "error": f"Fallback extraction failed: {str(e)}", "url": url}
```

## Advantages of this Approach

1. **Layered Defense**: Two different scraping technologies with different protection-bypass approaches increase success rates
2. **Selective Activation**: Fallback only activates when needed, saving resources
3. **Minimal Changes**: Integration requires minimal code changes to the existing system
4. **Configurable**: All aspects of the fallback can be controlled through configuration
5. **Graceful Degradation**: Falls back to primary method if StealthyFetcher is not available

## Key StealthyFetcher Features to Leverage

| Feature                         | How to Use                                  | Benefit                            |
| ------------------------------- | ------------------------------------------- | ---------------------------------- |
| **Modified Firefox (Camoufox)** | Use as fallback for Chrome/Playwright       | Different browser fingerprint      |
| **Humanize Mouse**              | `humanize=True`                             | More realistic user simulation     |
| **Google Search Referrer**      | `google_search=True`                        | Appears as organic traffic         |
| **Resource Control**            | `block_images=True, disable_resources=True` | Faster, more efficient scraping    |
| **WebRTC Blocking**             | `block_webrtc=True`                         | Prevents IP leakage                |
| **GeoIP Integration**           | `geoip=True` with proxy                     | Consistent geolocation fingerprint |
| **Network Idle Wait**           | `network_idle=True`                         | Ensures all content is loaded      |
| **Custom Automation**           | `page_action=custom_function`               | Site-specific interaction patterns |

## Implementation Considerations

1. **Error Handling**: Robust error handling for both primary and fallback methods
2. **Performance Impact**: StealthyFetcher may be slower due to more comprehensive anti-detection measures
3. **Package Dependencies**: Need to ensure scrapling package is available or handle its absence
4. **Consistency**: Ensure content extraction logic is consistent between both methods
5. **Logging**: Detailed logging to track which method succeeded and why

## Usage Example

```python
extractor = SpecialStrategyExtractor({
    "max_retries": 3,
    "use_fallback": True,
    "fallback_config": {
        "headless": True,
        "block_images": True,
        "humanize": 1.5,  # 1.5 seconds max for cursor movement
        "os_randomize": True
    }
})

result = await extractor.extract("https://example.com")
if result["success"]:
    content = result["content"]
    # Process content...
```

## Future Enhancements

1. **Domain-Specific Strategies**: Configure different fallback strategies for different domains
2. **Hybrid Approach**: Use elements from both technologies simultaneously
3. **Success Rate Analysis**: Track and analyze which method works best for which sites
4. **Auto-Switching**: Automatically choose the best method based on historical performance
5. **Custom Addons**: Consider using specialized Firefox addons for particular protection mechanisms

## Conclusion

Integrating StealthyFetcher as a fallback mechanism provides a robust solution for handling sites with advanced anti-bot protection. By leveraging the unique capabilities of both systems, we can significantly improve scraping success rates while maintaining the existing architecture's strengths.
