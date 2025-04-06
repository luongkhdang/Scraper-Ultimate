"""
Consent Dialog Handler Module

This module provides functions for handling cookie consent dialogs, GDPR notices,
and other popup overlays that may block content on websites.

Exported Functions:
- handle_consent_dialogs(page) -> bool: Detect and handle common consent dialogs
- remove_overlay_elements(page) -> bool: Remove generic overlay elements

Related Files:
- src/scraper/scraper_hooks/strategies/special_strategy.py: Main scraping strategy

Dependencies:
- playwright: For page manipulation and dialog handling
"""

import logging
import random
import asyncio

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Common consent button selectors to try
CONSENT_SELECTORS = [
    '#onetrust-accept-btn-handler',
    '.accept-cookies-button',
    'button[aria-label="Accept cookies"]',
    'button[aria-label="Accept all cookies"]',
    'button:has-text("Accept")',
    'button:has-text("Accept all")',
    'button:has-text("I agree")',
    'button:has-text("OK")',
    '.js-cookie-consent-agree',
    '#didomi-notice-agree-button',
    '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
    '.fc-button.fc-primary-button',
    '.fc-cta-consent',
    'button[aria-label="Close"]',
    '.modal .close-button'
]

# Generic overlay selectors to target for removal
OVERLAY_SELECTORS = [
    '.modal', '.overlay', '.paywall', '.popup', '.gdpr',
    '.cookie-notice', '.consent-modal', '#cookie-banner',
    '[class*="paywall"]', '[class*="modal"]', '[class*="overlay"]'
]


async def handle_consent_dialogs(page):
    """
    Handle common consent dialogs and cookie banners

    Args:
        page: Playwright page object

    Returns:
        bool: True if any dialog was handled
    """
    # Try clicking on common consent buttons
    for selector in CONSENT_SELECTORS:
        try:
            # Check if the element is visible
            is_visible = await page.evaluate(f"""
                () => {{
                    const element = document.querySelector('{selector}');
                    if (!element) return false;

                    const style = window.getComputedStyle(element);
                    return style.display !== 'none' &&
                           style.visibility !== 'hidden' &&
                           style.opacity !== '0';
                }}
            """)

            if is_visible:
                # Get the button element
                button = await page.query_selector(selector)
                if button:
                    # Add a small random delay before interaction (like a human would)
                    think_time = random.uniform(0.7, 2.1)
                    await asyncio.sleep(think_time)

                    # Get bounding box to determine position
                    box = await button.bounding_box()
                    if box:
                        # Click with slight position randomization near center
                        # This simulates more human-like clicking behavior
                        x = box['x'] + box['width'] * \
                            (0.4 + random.random() * 0.2)
                        y = box['y'] + box['height'] * \
                            (0.4 + random.random() * 0.2)

                        # First move the mouse like a human would
                        await page.mouse.move(x, y, {"steps": random.randint(3, 7)})

                        # Small pause before clicking (human behavior)
                        await asyncio.sleep(random.uniform(0.05, 0.15))

                        # Click the consent button
                        await page.mouse.click(x, y)

                        # Randomized wait time after clicking
                        await page.wait_for_timeout(random.randint(1000, 2000))
                    else:
                        # Fallback to standard click if we can't get bounding box
                        await button.click(delay=random.randint(50, 150))
                        await page.wait_for_timeout(random.randint(1000, 2000))
                else:
                    # Fallback to simple selector click
                    await page.click(selector, delay=random.randint(50, 150))
                    await page.wait_for_timeout(random.randint(1000, 2000))

                logger.info(f"Clicked consent button: {selector}")
                return True
        except Exception as e:
            logger.debug(
                f"Error handling consent selector {selector}: {e}")
            continue

    # If no buttons were found/clicked, try removing overlays
    try:
        removed = await remove_overlay_elements(page)
        return removed
    except Exception as e:
        logger.debug(f"Error removing overlay elements: {e}")
        return False


async def remove_overlay_elements(page):
    """
    Generic approach to remove overlay elements that might block content

    Args:
        page: Playwright page object

    Returns:
        bool: True if elements were likely removed, False otherwise
    """
    try:
        result = await page.evaluate("""
            () => {
                let removed = false;
                const overlaySelectors = [
                    '.modal', '.overlay', '.paywall', '.popup', '.gdpr',
                    '.cookie-notice', '.consent-modal', '#cookie-banner',
                    '[class*="paywall"]', '[class*="modal"]', '[class*="overlay"]'
                ];

                overlaySelectors.forEach(selector => {
                    document.querySelectorAll(selector).forEach(el => {
                        if (el && el.offsetParent &&
                            typeof window.getComputedStyle === 'function') {
                            const style = window.getComputedStyle(el);
                            if (style && style.position === 'fixed') {
                                el.remove();
                                removed = true;
                            }
                        }
                    });
                });

                // Also unlock scrolling on body
                const body = document.body;
                if (body) {
                    body.style.overflow = 'auto';
                    body.style.position = 'static';
                    if (body.style.overflow === 'auto') {
                        removed = true;
                    }
                }
                
                return removed;
            }
        """)

        return result
    except Exception as e:
        logger.debug(f"Error in generic overlay removal: {e}")
        return False


async def is_consent_dialog_present(page):
    """
    Check if a consent dialog appears to be present on the page

    Args:
        page: Playwright page object

    Returns:
        bool: True if a consent dialog is likely present
    """
    try:
        return await page.evaluate("""
            () => {
                // Check for common consent elements
                const consentSelectors = [
                    '#onetrust-banner-sdk',
                    '#gdpr-consent-tool-wrapper',
                    '#cookie-notice',
                    '.cookie-banner',
                    '.consent-banner',
                    '.privacy-policy-tooltip',
                    '[aria-label*="cookie"]',
                    '[aria-label*="consent"]',
                    '[class*="cookie"]',
                    '[class*="consent"]',
                    '[class*="gdpr"]',
                    '[id*="cookie"]',
                    '[id*="consent"]',
                    '[id*="gdpr"]'
                ];
                
                for (const selector of consentSelectors) {
                    const elements = document.querySelectorAll(selector);
                    for (const el of elements) {
                        if (el && el.offsetParent) {
                            const style = window.getComputedStyle(el);
                            if (style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0') {
                                return true;
                            }
                        }
                    }
                }
                
                return false;
            }
        """)
    except Exception as e:
        logger.debug(f"Error checking for consent dialog: {e}")
        return False
