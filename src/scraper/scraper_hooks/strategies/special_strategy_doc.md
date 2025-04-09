# Enhanced Special Strategy Implementation Plan

## Overview

This document outlines a comprehensive plan to enhance the current `special_strategy.py` with the playwright-stealth library while maintaining fallback capabilities. This will create a more robust scraping strategy that better evades detection while preserving the existing functionality.

## Goals

1. Implement playwright-stealth for comprehensive bot detection evasion
2. Maintain compatibility with existing Tor integration
3. Create a modular approach that allows fallback to current strategies
4. Improve detection evasion capabilities based on techniques in `more.md`
5. Maintain code maintainability and modularity

## Implementation Plan

### Phase 1: Setup and Integration

1. **Add Dependencies**

   - Add playwright-stealth to the project's dependencies
   - Ensure compatibility with the current Playwright version

2. **Create Initial Structure**

   - Create a new file `special_strategy_two.py` based on `special_strategy.py`
   - Implement an enhanced version of `browser_setup.py` called `stealth_browser_setup.py`

3. **Integrate Basic playwright-stealth**
   - Modify context creation to use playwright-stealth
   - Test basic functionality with simple sites

### Phase 2: Enhanced Implementation

1. **Extend Current Capabilities**

   - Integrate advanced browser arguments from `more.md`
   - Implement enhanced JavaScript injection techniques
   - Add conditional browser context configuration based on site requirements

2. **Tor Integration Enhancement**

   - Ensure playwright-stealth works properly with Tor
   - Implement circuit rotation based on detection triggers
   - Add fallback mechanisms if Tor is unavailable

3. **Detection Avoidance Improvements**
   - Implement advanced timing randomization
   - Add more sophisticated user behavior simulation
   - Use persistent contexts for challenging sites

### Phase 3: Fallback Mechanism

1. **Implement Strategy Selection**

   - Create a strategy selector that can choose between stealth and standard approach
   - Add automatic fallback if stealth approach fails
   - Implement domain-specific strategy selection

2. **Error Handling and Recovery**
   - Enhance error detection for bot challenges
   - Add recovery mechanisms specific to playwright-stealth
   - Implement cross-strategy session handling

### Phase 4: Testing and Optimization

1. **Test Suite Development**

   - Create tests for key challenging sites
   - Implement comparison testing between strategies
   - Add performance benchmarking

2. **Optimization**
   - Profile and optimize browser resource usage
   - Tune stealth parameters for best results
   - Optimize for specific high-value targets

## Technical Details

### Enhanced Browser Setup

```python
async def create_stealth_browser_context(url, user_agent=None, use_tor=False):
    """
    Create an enhanced browser context using playwright-stealth

    Args:
        url: Target URL for extraction
        user_agent: Optional user agent to use
        use_tor: Whether to use Tor proxy

    Returns:
        Tuple of (playwright, browser, context, page) objects
    """
    if not PLAYWRIGHT_AVAILABLE:
        logger.error("Playwright not available, cannot create browser context")
        return None, None, None, None

    try:
        playwright = await async_playwright().start()

        # Get enhanced browser arguments from more.md
        browser_args = get_enhanced_browser_args()

        # Set up browser launch options
        browser_options = {
            "headless": True,
            "args": browser_args
        }

        # Add Tor proxy if needed and available
        if use_tor and tor_integration.is_ready():
            browser_options = tor_integration.setup_tor_for_browser(browser_options)

        # Determine if we should use persistent context for this domain
        if should_use_persistent_context(url):
            # Create a temporary user data directory
            user_data_dir = tempfile.mkdtemp(prefix="playwright_profile_")

            # Launch with persistent context
            context = await playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                **browser_options
            )

            browser = None  # No separate browser object with persistent context
        else:
            # Launch browser normally
            browser = await playwright.chromium.launch(**browser_options)

            # Set up device emulation based on user agent
            context_options = setup_enhanced_device_emulation(playwright, user_agent)

            # Create context with options
            context = await browser.new_context(**context_options)

        # Apply stealth using playwright-stealth
        await stealth_sync.stealth_async(context)

        # Additional custom evasions from more.md
        await apply_additional_evasions(context)

        # Create page
        page = await context.new_page()

        # Set up page defaults
        await setup_enhanced_page_defaults(page)

        return playwright, browser, context, page

    except Exception as e:
        logger.error(f"Error creating stealth browser context: {e}")
        return None, None, None, None
```

### Browser Launch Arguments

Enhanced browser arguments from `more.md`:

```python
def get_enhanced_browser_args():
    """
    Get enhanced browser arguments from more.md for stealth browsing

    Returns:
        List[str]: List of browser arguments
    """
    return [
        '--disable-blink-features=AutomationControlled',
        '--disable-features=IsolateOrigins,site-per-process',
        '--disable-site-isolation-trials',
        '--disable-notifications',
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
```

### Strategy Selection Logic

```python
def select_strategy(url, previous_attempt_failed=False):
    """
    Select the appropriate strategy based on URL and previous attempts

    Args:
        url: The URL to be processed
        previous_attempt_failed: Whether a previous attempt failed

    Returns:
        str: Strategy name ('stealth' or 'standard')
    """
    domain = urlparse(url).netloc.lower()

    # Always use standard strategy for these domains
    if domain in STANDARD_STRATEGY_DOMAINS:
        return 'standard'

    # If stealth previously failed, try standard
    if previous_attempt_failed:
        return 'standard'

    # Default to stealth for better evasion
    return 'stealth'
```

### Enhanced Extractor Implementation

The main extractor class will be enhanced to support both strategies:

```python
class EnhancedSpecialStrategyExtractor(BaseExtractor):
    """
    Enhanced Special Strategy Extractor with stealth capabilities

    This extractor can use both playwright-stealth and the standard approach,
    with automatic fallback between them.
    """

    def __init__(self, config=None):
        super().__init__(config)
        self.config = config or {}
        # Rest of initialization

    async def extract(self, url, config=None):
        """
        Extract content using the appropriate strategy with fallback

        Args:
            url: URL to extract content from
            config: Optional configuration overrides

        Returns:
            dict: Extracted content or error information
        """
        # Check blocked domains
        if is_domain_blocked(url):
            return {
                "success": False,
                "error": "Domain is in NOT_TO_TRY_DOMAINS list",
                "url": url
            }

        merged_config = {**self.config, **(config or {})}

        # Try stealth strategy first
        strategy = select_strategy(url)

        if strategy == 'stealth':
            result = await self._extract_with_stealth(url, merged_config)

            # If stealth failed, try standard as fallback
            if not result.get("success", False):
                logger.info(f"Stealth strategy failed, falling back to standard for {url}")
                result = await self._extract_with_standard(url, merged_config)
        else:
            # Use standard strategy directly
            result = await self._extract_with_standard(url, merged_config)

        return result

    async def _extract_with_stealth(self, url, config):
        """
        Extract using playwright-stealth strategy
        """
        # Implementation using playwright-stealth

    async def _extract_with_standard(self, url, config):
        """
        Extract using the standard strategy (original implementation)
        """
        # Original implementation from special_strategy.py
```

## Integration with Current Codebase

1. **File Organization**:

   - `special_strategy_two.py`: Enhanced strategy with playwright-stealth and fallback
   - `stealth_browser_setup.py`: Enhanced browser setup with playwright-stealth
   - Original files remain untouched for backward compatibility

2. **API Compatibility**:

   - Maintain the same API for backward compatibility
   - Add new parameters for enhanced functionality

3. **Configuration Management**:

   - Allow configuration of strategy selection
   - Provide domain-specific configuration

4. **Tor Integration**:
   - Ensure Tor works correctly with both strategies
   - Add enhanced Tor circuit handling for stealth strategy

## Testing Strategy

1. **Unit Tests**:

   - Test individual components (browser setup, evasion techniques)
   - Test strategy selection logic

2. **Integration Tests**:

   - Test with various site types
   - Test fallback mechanisms

3. **Comparison Testing**:
   - Compare results with and without stealth
   - Track detection rates

## Expected Benefits

1. **Improved Evasion**: Better avoidance of bot detection mechanisms
2. **Maintainability**: Leverage playwright-stealth's ongoing development
3. **Flexibility**: Choose best strategy per site
4. **Reliability**: Fallback to proven methods when needed

## Timeline

1. **Phase 1** (Setup): 1-2 days
2. **Phase 2** (Enhanced Implementation): 3-4 days
3. **Phase 3** (Fallback Mechanism): 2-3 days
4. **Phase 4** (Testing and Optimization): 2-3 days

Total estimated time: 8-12 days

## Potential Challenges

1. **Compatibility Issues**: playwright-stealth may have version requirements
2. **Performance Impact**: More sophisticated evasion may impact performance
3. **Tor Integration**: Ensuring proper functioning with Tor

## Conclusion

This plan provides a comprehensive approach to enhancing the current `special_strategy.py` with playwright-stealth while maintaining fallback capabilities. The implementation will create a more robust scraping strategy that better evades detection while preserving existing functionality.
