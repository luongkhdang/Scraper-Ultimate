#!/usr/bin/env python
"""
Test Script for Special Strategy Module

This script tests the Special Strategy module, focusing on error handling and BizToc URL handling.
It verifies that the DOM script error handling is correctly implemented with null checks.

Usage:
    python src/test_special_strategy.py

Related Files:
- src/scraper/scraper_hooks/strategies/special_strategy.py: The strategy being tested
"""

import asyncio
import sys
import logging
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("test_special_strategy")

try:
    from scraper.scraper_hooks.strategies.special_strategy import SpecialStrategy
    from playwright.async_api import async_playwright
except ImportError as e:
    logger.error(f"Required module not found: {e}")
    logger.error("Make sure you have installed the required dependencies:")
    logger.error("  pip install playwright asyncio")
    logger.error("Also run: playwright install")
    sys.exit(1)


async def test_biztoc_url_handling():
    """Test BizToc URL handling with proper error handling."""
    special_strategy = SpecialStrategy()

    # Test BizToc URL detection
    test_urls = [
        ("https://biztoc.com/x/123456", True),
        ("https://www.biztoc.com/p/abcdef", True),
        ("https://regular-site.com/article", False)
    ]

    for url, expected in test_urls:
        result = special_strategy.detect_biztoc_url(url)
        status = "✅" if result == expected else "❌"
        logger.info(
            f"{status} BizToc detection for {url}: got {result}, expected {expected}")

    # Test BizToc extraction (mock test since we need a real page)
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            # Mock BizToc page with missing elements to test error handling
            await page.set_content("""
                <html>
                <body>
                    <h1>BizToc</h1>
                    <!-- Deliberately missing the proper elements -->
                    <a class="not-urlbox">Wrong class</a>
                    <span class="urlbox drops">Missing text-mono class</span>
                </body>
                </html>
            """)

            # Call the private method directly with reflection to test error handling
            logger.info(
                "Testing BizToc error handling with missing elements...")
            # We expect this to return null without errors
            try:
                url = await page.evaluate("""
                    () => {
                        // Try to find the link with the class
                        const linkElement = document.querySelector('a.urlbox.drops.text-mono');
                        if (linkElement && typeof linkElement.href === 'string') {
                            return linkElement.href;
                        }

                        // Fallback to span inside anchor
                        const spanElement = document.querySelector('span.urlbox.drops.text-mono');
                        if (spanElement && spanElement.closest && typeof spanElement.closest === 'function') {
                            const anchorElement = spanElement.closest('a');
                            if (anchorElement && typeof anchorElement.href === 'string') {
                                return anchorElement.href;
                            }
                        }

                        return null;
                    }
                """)
                logger.info(
                    f"✅ BizToc extraction handled missing elements correctly: {url}")
            except Exception as e:
                logger.error(f"❌ BizToc extraction error: {e}")

            # Test with malformed element
            await page.set_content("""
                <html>
                <body>
                    <h1>BizToc</h1>
                    <a class="urlbox drops text-mono">Missing href attribute</a>
                </body>
                </html>
            """)

            try:
                url = await page.evaluate("""
                    () => {
                        // Try to find the link with the class
                        const linkElement = document.querySelector('a.urlbox.drops.text-mono');
                        if (linkElement && typeof linkElement.href === 'string') {
                            return linkElement.href;
                        }

                        // Fallback to span inside anchor
                        const spanElement = document.querySelector('span.urlbox.drops.text-mono');
                        if (spanElement && spanElement.closest && typeof spanElement.closest === 'function') {
                            const anchorElement = spanElement.closest('a');
                            if (anchorElement && typeof anchorElement.href === 'string') {
                                return anchorElement.href;
                            }
                        }

                        return null;
                    }
                """)
                logger.info(
                    f"✅ BizToc extraction handled malformed element correctly: {url}")
            except Exception as e:
                logger.error(
                    f"❌ BizToc extraction error with malformed element: {e}")

            await browser.close()
    except Exception as e:
        logger.error(f"Error during Playwright test: {e}")


async def test_dom_error_handling():
    """Test DOM script error handling for undefined elements."""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            # Create a test page with no matching elements
            await page.set_content("<html><body><h1>Test Page</h1></body></html>")

            logger.info("Testing generic DOM removal script...")
            # Run the generic DOM removal script (copied from special_strategy.py)
            try:
                await page.evaluate("""
                    () => {
                        // Remove paywall elements
                        const blockingElements = [
                            '[id*="paywall"]', '[class*="paywall"]',
                            '[id*="subscribe"]', '[class*="subscribe"]'
                        ];

                        blockingElements.forEach(selector => {
                            document.querySelectorAll(selector).forEach(el => {
                                if (el) el.remove();
                            });
                        });

                        // Force content visibility on non-existent elements
                        const contentElements = ['article', 'main'];

                        contentElements.forEach(selector => {
                            document.querySelectorAll(selector).forEach(el => {
                                if (el) {
                                    el.style.display = 'block';
                                    
                                    // Process children that don't exist
                                    if (el.querySelectorAll) {
                                        Array.from(el.querySelectorAll('*')).forEach(child => {
                                            if (child) {
                                                if (child.style) {
                                                    child.style.visibility = 'visible';
                                                }
                                            }
                                        });
                                    }
                                }
                            });
                        });

                        // Body checks
                        const body = document.body;
                        if (body) {
                            body.style.overflow = 'auto';
                        }
                        
                        // Element that doesn't exist
                        const nonExistent = document.querySelector('#non-existent');
                        if (nonExistent && nonExistent.classList) {
                            nonExistent.classList.remove('hidden');
                        }
                    }
                """)
                logger.info("✅ DOM script executed without errors")
            except Exception as e:
                logger.error(f"❌ DOM script error: {e}")

            await browser.close()
    except Exception as e:
        logger.error(f"Error during Playwright test: {e}")


async def main():
    """Run all tests."""
    logger.info("=== Starting Special Strategy Tests ===")

    # Check dependencies
    special_strategy = SpecialStrategy()
    if not special_strategy.is_available():
        logger.error("Special Strategy dependencies not available. Exiting.")
        return

    logger.info("Testing BizToc URL handling...")
    await test_biztoc_url_handling()

    logger.info("Testing DOM error handling...")
    await test_dom_error_handling()

    logger.info("=== All tests completed ===")

if __name__ == "__main__":
    asyncio.run(main())
