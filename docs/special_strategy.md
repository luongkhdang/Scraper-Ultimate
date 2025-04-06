# Special Strategy Module Documentation

## Overview

The Special Strategy module provides advanced scraping techniques for extracting content from websites that implement paywalls, anti-bot measures, or other content restrictions. It uses Playwright for browser automation and can optionally use Tor for IP rotation to bypass IP-based blocking.

## Key Features

- **Browser Automation**: Uses Playwright to render JavaScript-heavy websites
- **Paywall Bypass**: Implements techniques to bypass content restrictions
- **Tor Integration**: Optional IP rotation via the Tor network
- **Content Extraction**: Reliable extraction from various article formats
- **Error Handling**: Robust null checks and error recovery mechanisms

## Defensive DOM Manipulation

The module implements comprehensive null checks and defensive programming techniques in all DOM manipulation scripts to ensure stability when processing unpredictable web content:

- All DOM element access is guarded with null checks before property access
- Methods like `classList.contains()`, `closest()`, and style manipulations include appropriate type checking
- Element collections (`querySelectorAll`) are safely iterated with checks on each element
- Fallback mechanisms for key operations ensure graceful degradation

### Example: Safe Element Removal

```javascript
// Before: Potentially unsafe
document.querySelectorAll(selector).forEach((el) => el.remove());

// After: With null checks
document.querySelectorAll(selector).forEach((el) => {
  if (el) el.remove();
});
```

## Site-Specific Strategies

The module includes specialized strategies for major publications:

- **Bloomberg**: Handles dynamic paywalls and overlays
- **Wall Street Journal**: Manages subscriber-only content
- **Financial Times**: Bypasses the metered paywall
- **New York Times**: Handles subscription notices
- **The Economist**: Manages content gates
- **BizToc**: Special handling for article references

## BizToc URL Handling

BizToc is a special case that requires additional processing:

1. When a BizToc URL is detected, the module navigates to the page
2. It extracts the original source URL with defensive error handling
3. The scraper then uses the extracted source URL for content retrieval

## Error Recovery

The module implements multiple recovery mechanisms:

- **Retry System**: Configurable retry attempts with increasing delays
- **Alternative Selectors**: Multiple selector options for content extraction
- **Fallbacks**: Progressive fallback methods for content extraction
- **Exception Handling**: All operations are wrapped in try/except blocks with appropriate logging

## Testing

A dedicated test script (`test_special_strategy.py`) validates the robustness of:

- BizToc URL handling with various edge cases
- DOM manipulation with missing or malformed elements
- General error handling when elements don't exist or have unexpected structures

## Usage

```python
from scraper.scraper_hooks.strategies.special_strategy import SpecialStrategy

# Initialize the strategy
strategy = SpecialStrategy()

# Check if dependencies are available
if strategy.is_available():
    # Extract content from a URL
    content, final_url = await strategy.extract("https://example.com/article")

    if content:
        print(f"Successfully extracted {len(content)} characters from {final_url}")
    else:
        print("Extraction failed")
```

## Related Components

- **Tor Client**: Provides IP rotation functionality
- **Docker Integration**: Configuration for Tor proxy services
- **Scraper Interface**: Defines the hook integration points
