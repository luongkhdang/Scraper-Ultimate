# Advanced Web Scraping Strategy Guide

This guide outlines a comprehensive, universal web scraping strategy that works effectively across various websites, including those with paywalls and anti-bot measures.

## Core Principles

1. **Human-like Behavior Simulation**: Mimicking real user browsing patterns
2. **Anti-Detection Techniques**: Bypassing bot detection systems
3. **Content Extraction Optimization**: Using multiple fallback methods
4. **Error Resilience**: Graceful handling of failures

## Implementation Details

### 1. Browser Setup & Configuration

#### Enhanced Browser Launch

```python
browser_args = [
    '--disable-blink-features=AutomationControlled',
    '--disable-features=IsolateOrigins,site-per-process',
    '--disable-site-isolation-trials',
    '--disable-web-security',
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

browser = await playwright.chromium.launch(
    headless=True,
    args=browser_args
)
```

#### Persistent Context for Enhanced Stealth

For sites with stronger anti-bot measures, using a persistent context can significantly improve success rates:

```python
import tempfile

# Create a temporary user data directory
user_data_dir = tempfile.mkdtemp(prefix="playwright_profile_")

# Launch with persistent context
browser_context = await playwright.chromium.launch_persistent_context(
    user_data_dir=user_data_dir,
    headless=True,
    args=browser_args
)

# The browser_context is already a context, so we don't need to create one
page = await browser_context.new_page()

# Be sure to clean up the temporary directory when done
# import shutil
# shutil.rmtree(user_data_dir, ignore_errors=True)
```

#### Device Emulation & Fingerprint Randomization

```python
# Decide between mobile and desktop based on site characteristics
def select_device_profile(domain):
    # Sites that work better with mobile emulation
    mobile_friendly_sites = ['nytimes.com', 'theguardian.com', 'cnn.com']
    # Sites that work better with desktop emulation
    desktop_friendly_sites = ['github.com', 'stackoverflow.com']

    if any(site in domain for site in mobile_friendly_sites):
        return 'mobile'
    elif any(site in desktop_friendly_sites for site in desktop_friendly_sites):
        return 'desktop'
    else:
        # Default to mobile 70% of the time as it often works better for content sites
        return 'mobile' if random.random() < 0.7 else 'desktop'

# Apply the appropriate device profile
device_type = select_device_profile(domain)

# Slightly randomize geolocation to avoid fingerprinting
latitude = 40.7128 + (random.random() - 0.5) * 0.01  # Small random variation
longitude = -74.0060 + (random.random() - 0.5) * 0.01  # Small random variation

if device_type == 'mobile':
    # Mobile device emulation (randomly select between iPhone and Android)
    if random.random() < 0.5:  # 50% chance for iPhone
        device = playwright.devices['iPhone 13']
        context_options = {
            **device,
            'geolocation': {'latitude': latitude, 'longitude': longitude},
            'permissions': ['geolocation'],
            'locale': 'en-US',
            'timezone_id': 'America/New_York'
        }
    else:  # Android device
        # Randomize viewport slightly for Android
        viewport_width = 412 + random.randint(1, 3)
        viewport_height = 915 + random.randint(1, 3)

        context_options = {
            'user_agent': 'Mozilla/5.0 (Linux; Android 12; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.61 Mobile Safari/537.36',
            'viewport': {'width': viewport_width, 'height': viewport_height},
            'device_scale_factor': 2.625,
            'is_mobile': True,
            'has_touch': True,
            'geolocation': {'latitude': latitude, 'longitude': longitude},
            'permissions': ['geolocation'],
            'locale': 'en-US',
            'timezone_id': 'America/New_York'
        }
else:
    # Desktop device with slight randomization
    viewport_width = 1280 + random.randint(1, 10)
    viewport_height = 800 + random.randint(1, 10)

    context_options = {
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'viewport': {'width': viewport_width, 'height': viewport_height},
        'device_scale_factor': 1,
        'is_mobile': False,
        'has_touch': False,
        'geolocation': {'latitude': latitude, 'longitude': longitude},
        'permissions': ['geolocation'],
        'locale': 'en-US',
        'timezone_id': 'America/New_York'
    }

context = await browser.new_context(**context_options)
```

### 2. Request Handling & Headers

#### Realistic HTTP Headers

```python
page.set_extra_http_headers({
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'DNT': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'Referer': 'https://www.google.com/search?q=relevant+search+term'
})
```

#### Resource Management

```python
# Block unnecessary resource types for better performance
context.route('**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,otf,mp4,webm,ogg,mp3,wav}',
              lambda route: route.abort())

# Simulate slow network for APIs and scripts to appear more human
async def slow_request_handler(route):
    resource_type = route.request.resource_type.lower()

    if resource_type == 'document':
        await route.continue_()
        return

    if resource_type in ['xhr', 'fetch']:
        delay = random.uniform(500, 1000) / 1000.0
    elif resource_type in ['script', 'stylesheet']:
        delay = random.uniform(100, 300) / 1000.0
    else:
        delay = 0

    if delay > 0:
        await asyncio.sleep(delay)

    await route.continue_()

page.route('**/*', slow_request_handler)
```

### 3. Navigation & Waiting Strategies

```python
# Navigate with increased timeout for reliability
await page.goto(article_url, timeout=30000, wait_until='domcontentloaded')

# Wait for real content to be visible rather than just page load
await page.wait_for_selector('article, .article, main, .content', timeout=10000, state='visible')

# Add human-like scrolling behavior
for i in range(4):
    scroll_pos = (i + 1) * 300
    await page.evaluate(f"window.scrollTo(0, {scroll_pos})")
    await page.wait_for_timeout(500 + random.randint(100, 300))
```

### 4. Handling Special URL Types

Content aggregators like Google News and BizToc require special handling to extract the original article URL:

```python
async def handle_special_url_types(page, url):
    # Parse domain for special handling
    domain = urlparse(url).netloc.lower()
    final_url = url

    # Handle Google News URLs
    if 'news.google.com' in domain:
        try:
            logger.info("Google News URL detected, handling redirects")
            await page.goto(url, timeout=30000, wait_until='domcontentloaded')

            # Wait for redirect to happen
            await page.wait_for_timeout(5000)

            # Get the redirected URL
            redirected_url = page.url

            # Check if we were redirected
            if redirected_url != url:
                logger.info(f"Google News redirected to: {redirected_url}")
                final_url = redirected_url

                # Navigate to the redirected URL
                await page.goto(redirected_url, timeout=30000, wait_until='domcontentloaded')
        except Exception as e:
            logger.error(f"Error handling Google News URL: {e}")

    # Handle BizToc URLs
    elif 'biztoc.com' in domain:
        try:
            logger.info("BizToc URL detected, extracting original URL")
            await page.goto(url, timeout=30000, wait_until='domcontentloaded')

            # Look for the original URL element
            await page.wait_for_selector('.urlbox.drops.text-mono', timeout=10000)

            # Extract the original URL
            original_url = await page.evaluate("""
                () => {
                    // Try to find the link with the class
                    const linkElement = document.querySelector('a.urlbox.drops.text-mono');
                    if (linkElement) {
                        return linkElement.href;
                    }

                    // Fallback to span inside anchor
                    const spanElement = document.querySelector('span.urlbox.drops.text-mono');
                    if (spanElement && spanElement.closest('a')) {
                        return spanElement.closest('a').href;
                    }

                    return null;
                }
            """)

            if original_url:
                logger.info(f"Found original URL on BizToc: {original_url}")
                final_url = original_url

                # Navigate to the original article
                await page.goto(original_url, timeout=30000, wait_until='domcontentloaded')
        except Exception as e:
            logger.error(f"Error handling BizToc URL: {e}")

    return final_url
```

### 5. Automated Dialog Handling

```python
async def handle_consent_dialogs(page):
    # Common consent button selectors
    consent_selectors = [
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

    for selector in consent_selectors:
        try:
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
                await page.click(selector)
                await page.wait_for_timeout(1500)
                return True
        except Exception:
            continue

    # Generic approach for other dialogs
    await page.evaluate("""
        () => {
            const overlaySelectors = [
                '.modal', '.overlay', '.paywall', '.popup', '.gdpr',
                '.cookie-notice', '.consent-modal', '#cookie-banner',
                '[class*="paywall"]', '[class*="modal"]', '[class*="overlay"]'
            ];

            overlaySelectors.forEach(selector => {
                document.querySelectorAll(selector).forEach(el => {
                    if (el.offsetParent &&
                        (window.getComputedStyle(el).position === 'fixed')) {
                        el.remove();
                    }
                });
            });

            document.body.style.overflow = 'auto';
            document.body.style.position = 'static';
        }
    """)
```

### 6. Paywall & Overlay Removal

```python
async def remove_blocking_elements(page):
    await page.evaluate("""
        () => {
            // Remove paywall elements
            const blockingElements = [
                '[id*="paywall"]', '[class*="paywall"]',
                '[id*="subscribe"]', '[class*="subscribe"]',
                '[id*="premium"]', '[class*="premium"]',
                '[id*="gateway"]', '[class*="gateway"]',
                '.tp-modal', '.tp-backdrop', '.tp-container',
                '.piano-container', '.message-container',
                '[data-testid="inline-message"]'
            ];

            blockingElements.forEach(selector => {
                document.querySelectorAll(selector).forEach(el => el.remove());
            });

            // Force content visibility
            const contentElements = [
                'article', 'main', '.article-body', '.entry-content',
                '[data-testid="article-content"]', '[itemprop="articleBody"]',
                '.article-content', '.content-lock-content'
            ];

            contentElements.forEach(selector => {
                document.querySelectorAll(selector).forEach(el => {
                    if (el) {
                        el.style.display = 'block';
                        el.style.visibility = 'visible';
                        el.style.opacity = '1';
                        el.style.maxHeight = 'none';
                        el.style.height = 'auto';
                        el.style.overflow = 'visible';

                        // Also process children
                        Array.from(el.querySelectorAll('*')).forEach(child => {
                            child.style.display = '';
                            child.style.visibility = 'visible';
                            child.style.opacity = '1';
                        });
                    }
                });
            });

            // Remove blur effects and other restrictions
            document.querySelectorAll('.blur, [style*="blur"], [style*="opacity"]').forEach(el => {
                el.style.filter = 'none';
                el.style.webkitFilter = 'none';
                el.style.opacity = '1';
            });

            // Unlock body scrolling
            document.body.style.overflow = 'auto';
            document.body.style.position = 'static';
            document.documentElement.style.overflow = 'auto';
        }
    """);
```

### 7. Content Extraction

```python
async def extract_content(page):
    # Try these selectors in order to find the main content
    content_selectors = [
        'article', '.article', 'main', '.post-content', '.article-content',
        '.entry-content', '.content', '[itemprop="articleBody"]',
        '.article-body', '.story-body', '.story', '.post-body',
        '[data-testid="article-content"]', '.meteredContent',
        '.article__body', '.article-wrap', '.bigTop__article'
    ]

    content = ""

    for selector in content_selectors:
        try:
            elements = await page.query_selector_all(selector)

            if elements:
                for element in elements:
                    # Try getting all paragraphs inside
                    paragraphs = await element.query_selector_all('p')

                    if paragraphs and len(paragraphs) >= 3:
                        paragraph_texts = []
                        for p in paragraphs:
                            text = await p.text_content()
                            text = text.strip()
                            if text and len(text) > 30:
                                paragraph_texts.append(text)

                        element_content = '\n\n'.join(paragraph_texts)
                        if element_content and len(element_content) > 300:
                            content = element_content
                            break
                    else:
                        # If no paragraphs, try raw text content
                        text = await element.text_content()
                        text = text.strip()
                        if text and len(text) > 300:
                            content = text
                            break
        except Exception:
            continue

        if content:
            break

    # If no content found, try a more aggressive fallback method
    if not content or len(content) < 300:
        try:
            # Get all paragraphs from the page
            all_paragraphs = await page.query_selector_all('p')
            paragraph_texts = []

            for p in all_paragraphs:
                try:
                    text = await p.text_content()
                    text = text.strip()
                    # Only include substantial paragraphs
                    if text and len(text) > 40:
                        paragraph_texts.append(text)
                except Exception:
                    continue

            # Join paragraphs
            if paragraph_texts:
                content = '\n\n'.join(paragraph_texts)
        except Exception:
            pass

    return content
```

### 8. Comprehensive Error Handling with Resource Cleanup

Proper resource management is critical to prevent memory leaks and ensure stability:

```python
async def extract_with_proper_cleanup(url, user_agent):
    browser = None
    context = None
    page = None
    using_persistent_context = False
    content = None

    try:
        async with async_playwright() as p:
            # Launch browser with anti-detection measures
            browser_args = [
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                # ... additional arguments
            ]

            browser = await p.chromium.launch(headless=True, args=browser_args)

            # Create context with device emulation
            context = await browser.new_context(
                user_agent=user_agent,
                viewport={'width': 1280, 'height': 800},
                locale='en-US'
            )

            page = await context.new_page()

            # Navigation, content extraction, etc.
            # ...

            # Return the extracted content
            return content

    except Exception as e:
        logger.error(f"Error during extraction: {e}")
        return None

    finally:
        # Ensure all resources are properly cleaned up
        if page:
            try:
                await page.close()
            except Exception as e:
                logger.debug(f"Error closing page: {e}")

        if context and not using_persistent_context:
            try:
                await context.close()
            except Exception as e:
                logger.debug(f"Error closing context: {e}")

        if browser and not using_persistent_context:
            try:
                await browser.close()
            except Exception as e:
                logger.debug(f"Error closing browser: {e}")
```

### 9. Handling Event Loop Considerations

When working with async code in different environments, proper event loop management is essential:

```python
def extract_with_event_loop_handling(url, user_agent):
    """Handle extraction whether inside an existing event loop or not"""
    try:
        # Determine if we're in an event loop
        try:
            asyncio.get_running_loop()
            in_event_loop = True
        except RuntimeError:
            in_event_loop = False

        if in_event_loop:
            # We're already in an event loop, use a thread executor
            logger.info("Running in existing event loop, using thread executor")
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    lambda: asyncio.run(extract_content_async(url, user_agent))
                )

                try:
                    # Set a timeout to prevent hanging
                    result = future.result(timeout=60)
                    return result
                except concurrent.futures.TimeoutError:
                    logger.error("Extraction timed out after 60 seconds")
                    return None
                except Exception as e:
                    logger.error(f"Error in extraction thread: {e}")
                    return None
        else:
            # No event loop, we can just use asyncio.run
            logger.info("No event loop detected, using asyncio.run directly")
            return asyncio.run(extract_content_async(url, user_agent))

    except Exception as e:
        logger.error(f"Error in event loop handling: {e}")
        return None
```

### 10. Retry Mechanism

```python
async def extract_with_retries(url, max_retries=3, progressive_delays=[5000, 10000, 15000]):
    for attempt, delay in enumerate(progressive_delays[:max_retries]):
        try:
            content = await extract_with_strategy(url, delay)
            if content and len(content) > 500:
                return content
        except Exception as e:
            logger.error(f"Error in attempt {attempt+1}: {e}")
            if attempt < max_retries - 1:
                continue

    return None
```

## Best Practices for Reliable Scraping

1. **Rate Limiting**: Implement delays between requests (2-5 seconds minimum)
2. **IP Rotation**: Use proxy services to avoid IP-based blocking
3. **Header Randomization**: Vary user agents and headers between requests
4. **Error Monitoring**: Keep detailed logs of failures for debugging
5. **Scheduled Runs**: Schedule scraping during off-peak hours
6. **Respect Robots.txt**: Check `robots.txt` for scraping restrictions
7. **Content Validation**: Verify extracted content has sufficient length/structure
8. **Incremental Scraping**: Split large scraping tasks into smaller batches

## User Agent Selection Strategy

Selecting the right user agent is critical for avoiding detection:

```python
def get_appropriate_user_agent(domain):
    """Select appropriate user agent based on domain characteristics"""

    mobile_agents = [
        # iOS Safari
        'Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1',
        # Android Chrome
        'Mozilla/5.0 (Linux; Android 12; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.61 Mobile Safari/537.36',
        # Android Samsung Browser
        'Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/16.0 Chrome/92.0.4515.166 Mobile Safari/537.36'
    ]

    desktop_agents = [
        # Chrome Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.67 Safari/537.36',
        # Firefox Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:100.0) Gecko/20100101 Firefox/100.0',
        # Safari macOS
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 12_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.4 Safari/605.1.15',
        # Edge Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.67 Safari/537.36 Edg/101.0.1210.47'
    ]

    news_sites = ['nytimes.com', 'wsj.com', 'ft.com', 'bloomberg.com', 'reuters.com', 'economist.com']
    social_media = ['twitter.com', 'facebook.com', 'instagram.com', 'linkedin.com']
    tech_sites = ['github.com', 'stackoverflow.com', 'dev.to', 'medium.com']

    # Select based on site category
    if any(site in domain for site in news_sites):
        # News sites often work better with mobile agents (fewer paywalls)
        return random.choice(mobile_agents)
    elif any(site in domain for site in social_media):
        # Social media can be finicky - use the latest browsers
        if random.random() < 0.3:  # 30% chance of mobile
            return random.choice(mobile_agents)
        else:
            return random.choice(desktop_agents[:2])  # Newer Chrome/Firefox
    elif any(site in domain for site in tech_sites):
        # Tech sites work better with desktop browsers
        return random.choice(desktop_agents)
    else:
        # Default to 60/40 split between desktop and mobile
        if random.random() < 0.6:
            return random.choice(desktop_agents)
        else:
            return random.choice(mobile_agents)
```

## Ethical Considerations

1. **Terms of Service**: Check if the site permits scraping
2. **Data Usage**: Only use scraped data in accordance with site policies
3. **Server Load**: Minimize impact on target servers with rate limiting
4. **Personal Data**: Be extra cautious with personally identifiable information
5. **Attribution**: Attribute content to original sources when used

## Technical Implementation

For your actual implementation, consider using:

1. **Async Playwright or Puppeteer**: For modern JavaScript-heavy sites
2. **Request Caching**: To avoid repeated requests for the same content
3. **Content Normalization**: To standardize output regardless of source
4. **Headless Mode**: For production environments to save resources
5. **Persistence**: Store intermediate results to resume interrupted jobs

## Using Tor for IP Rotation

To avoid IP blocking while scraping at scale, Tor provides an excellent free solution for IP rotation.

### Why Use Tor for Scraping

1. **Free IP Rotation**: No cost compared to commercial proxy services
2. **Global IP Coverage**: Access to thousands of exit nodes worldwide
3. **Automatic Circuit Switching**: IPs rotate approximately every 10 minutes by default
4. **On-Demand Rotation**: Ability to force new circuits when needed

### Docker Setup for Tor with Playwright

The most reliable way to integrate Tor is using a Docker Compose setup with separate containers:

```yaml
# docker-compose.yml
version: "3.8"
services:
  tor:
    image: osminogin/tor-simple:latest
    ports:
      - "9050:9050" # SOCKS5 proxy
      - "9051:9051" # Control port for rotation
    environment:
      - TOR_CONTROL_PASSWORD=your_password_here
    volumes:
      - ./torrc:/etc/tor/torrc # Optional custom configuration

  scraper:
    build: .
    depends_on:
      - tor
    volumes:
      - ./:/app
    command: node scraper.js
```

Your Dockerfile for the scraper container:

```dockerfile
FROM node:18-slim

# Install Playwright dependencies
RUN apt-get update && apt-get install -y \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY package.json .
RUN npm install
RUN npx playwright install --with-deps chromium
COPY . .
```

### Connecting Playwright to Tor

```javascript
const { chromium } = require("playwright");

async function scrapeWithTor() {
  const browser = await chromium.launch({
    proxy: {
      server: "socks5://tor:9050", // 'tor' is the service name in docker-compose
      bypass: "localhost",
    },
    args: [
      "--disable-blink-features=AutomationControlled",
      // Add other anti-detection arguments from earlier sections
    ],
  });

  // Create context with device emulation
  const context = await browser.newContext({
    userAgent:
      "Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1",
    // Add other context options from earlier sections
  });

  const page = await context.newPage();

  try {
    // Check our current IP to verify Tor is working
    await page.goto("https://httpbin.org/ip");
    const ipData = await page.textContent("body");
    console.log("Current Tor IP:", ipData);

    // Continue with normal scraping...
    // ...
  } finally {
    await browser.close();
  }
}
```

### Forcing IP Rotation On Demand

When you need a new IP before Tor's default rotation interval (10 minutes):

```javascript
const { exec } = require("child_process");
const util = require("util");
const execPromise = util.promisify(exec);

async function rotateTorIP() {
  try {
    // Option 1: Send SIGHUP to the Tor process (Docker-specific)
    await execPromise("docker exec scraper-tor-1 killall -HUP tor");

    // Option 2: Use Tor Control Protocol for more reliable rotation
    await execPromise(`
            docker exec scraper-tor-1 /bin/sh -c '
            echo -e "AUTHENTICATE \\"your_password_here\\"\r\nSIGNAL NEWNYM\r\nQUIT" | nc 127.0.0.1 9051
            '
        `);

    // Wait for circuit to change
    await new Promise((resolve) => setTimeout(resolve, 5000));
    console.log("Tor IP rotated");
  } catch (error) {
    console.error("Error rotating Tor IP:", error);
  }
}

// Usage in scraping loop
async function scrapeMultipleSites(urls) {
  for (const url of urls) {
    try {
      await scrapeWithTor(url);

      // Force IP rotation every few requests
      if (urls.indexOf(url) % 3 === 0) {
        await rotateTorIP();
      }

      // Add random delay between requests
      await new Promise((resolve) =>
        setTimeout(resolve, 3000 + Math.random() * 5000)
      );
    } catch (error) {
      console.error(`Error scraping ${url}:`, error);
    }
  }
}
```

### Python Implementation with Playwright

For Python users, the setup is similar:

```python
import asyncio
from playwright.async_api import async_playwright
import subprocess
import time

async def rotate_tor_ip():
    try:
        # Using Docker exec to send SIGHUP
        subprocess.run([
            "docker", "exec", "scraper-tor-1", "killall", "-HUP", "tor"
        ], check=True)

        # Wait for circuit change
        time.sleep(5)
        print("Tor IP rotated")
    except Exception as e:
        print(f"Error rotating Tor IP: {e}")

async def scrape_with_tor(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            proxy={"server": "socks5://tor:9050"},
            args=["--disable-blink-features=AutomationControlled"]
        )

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1",
        )

        page = await context.new_page()

        try:
            # Verify Tor connection
            await page.goto("https://httpbin.org/ip")
            ip_data = await page.text_content("body")
            print(f"Current Tor IP: {ip_data}")

            # Your scraping logic here
            await page.goto(url, timeout=60000)
            # ...

        finally:
            await browser.close()
```

### Limitations and Considerations

1. **Speed**: Tor is generally slower than direct connections or commercial proxies due to routing through multiple nodes.
2. **Exit Node Blocking**: Some websites block known Tor exit nodes or present CAPTCHAs.
3. **Ethical Use**: Only scrape public data and respect `robots.txt` guidelines.
4. **Request Rate**: Use even more conservative delays with Tor to avoid overloading exit nodes.
5. **Reliability**: Tor connections can be less stable, so implement robust error handling and retries.

By combining Tor's IP rotation capabilities with the anti-detection techniques described earlier, you can create a powerful and cost-effective web scraping solution that minimizes the risk of IP-based blocking.

By following this comprehensive strategy, you'll be able to effectively extract content from most websites while appearing as a legitimate user and minimizing the chance of being detected as an automated scraper.
