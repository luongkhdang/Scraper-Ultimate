List of Techniques to Bypass Anti-Scraping and Paywalls

1. Browser Fingerprint Manipulation
   Disable Automation Detection: Use launch flags to hide Playwright’s automation signals.
   Example:
   const browser = await chromium.launch({ args: ['--disable-blink-features=AutomationControlled'] });

Disable Site Isolation: Prevent site-specific fingerprinting.
Example:
const browser = await chromium.launch({ args: ['--disable-features=IsolateOrigins,site-per-process'] });

Set Realistic User Agent Strings: Rotate mobile user agents from a curated list to mimic legitimate devices.
Example:
const userAgents = [
'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1',
'Mozilla/5.0 (Linux; Android 14; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36'
];
await context.setExtraHTTPHeaders({ 'User-Agent': userAgents[Math.floor(Math.random() * userAgents.length)] });

2. Realistic Device Emulation
   Mobile Device Emulation: Emulate an iPhone 13 or Android device for softer paywall experiences.
   Example:
   const { devices } = require('playwright');
   const iPhone13 = devices['iPhone 13'];
   const context = await browser.newContext({ ...iPhone13 });

Set Proper Viewport and Scale: Match device dimensions and pixel ratios.
Included in the device emulation above.
Enable Touch Capabilities: Simulate touch events to mimic mobile interaction.
Included in Playwright’s device emulation. 3. Mimicking Human Behavior
Realistic Scrolling Patterns: Scroll gradually with random pauses to simulate reading.
Example:
await page.evaluate(async () => {
for (let i = 0; i < document.body.scrollHeight; i += 100) {
window.scrollTo(0, i);
await new Promise(resolve => setTimeout(resolve, Math.random() \* 500 + 200));
}
window.scrollTo(0, 100); // Scroll back up slightly
});

Random Timing Delays: Add delays between actions (e.g., 1-3 seconds).
Example:
await page.waitForTimeout(Math.random() \* 2000 + 1000);

Slow Initial Loading: Wait 5 seconds on page load to mimic human behavior.
Example:
await page.goto(url, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(5000);

4. Enhanced Privacy Settings
   Custom Geolocation: Set to New York coordinates for consistency.
   Example:
   await context.setGeolocation({ latitude: 40.7128, longitude: -74.0060 });
   await context.grantPermissions(['geolocation']);

US Locale Settings: Use US English to align with typical traffic.
Example:
const context = await browser.newContext({ locale: 'en-US' });

DNT Headers: Enable Do Not Track to appear privacy-conscious.
Example:
await context.setExtraHTTPHeaders({ 'DNT': '1' });

5. Cookie/Session Manipulation
   Mimic Returning Visitors: Add a visited_before=true cookie.
   Example:
   await context.addCookies([{ name: 'visited_before', value: 'true', domain: '.example.com', path: '/' }]);

Set Referer Headers: Rotate referrers to simulate natural traffic.
Example:
const referrers = [
'https://www.google.com/',
'https://www.bing.com/search?q=finance+news',
'https://www.reddit.com/r/investing',
'https://t.co/abc123'
];
await context.setExtraHTTPHeaders({ 'Referer': referrers[Math.floor(Math.random() * referrers.length)] });

6. Paywall Dismissal
   Click Dismiss Buttons: Target paywall and modal close buttons.
   Example:
   await page.evaluate(() => {
   ['.paywall-close', '.modal-close', '[aria-label="close"]'].forEach(selector => {
   const btn = document.querySelector(selector);
   if (btn) btn.click();
   });
   });

Handle Consent Banners: Click “Accept” or “Continue” buttons.
Example:
await page.evaluate(() => {
const btn = Array.from(document.querySelectorAll('button, a'))
.find(el => /accept|continue|agree/i.test(el.textContent));
if (btn) btn.click();
});

7. Resource Management
   Block Unnecessary Resources: Prevent loading of images, fonts, and media to reduce detection risk.
   Example:
   await page.route('\*_/_.{png,jpg,woff2,mp4}', route => route.abort());

Selective JavaScript Disable: Block problematic scripts for specific sites if needed.
Example:
await page.route('\*_/_.js', route => {
if (route.request().url().includes('anti-scrape')) route.abort();
else route.continue();
});

8. Content Extraction Fallbacks
   Multiple CSS Selectors: Try various selectors for article content.
   Example:
   const content = await page.evaluate(() => {
   const selectors = ['.article-content', 'article', '.post-body'];
   for (const sel of selectors) {
   const el = document.querySelector(sel);
   if (el) return el.innerText;
   }
   return document.body.innerText;
   });

Advanced DOM Traversal: Extract hidden content with JavaScript.
Example:
await page.evaluate(() => {
document.querySelectorAll('[style*="display: none"]').forEach(el => el.style.display = 'block');
});

Filter Visible Elements: Use isVisible() for reliable extraction.
Example:
const visibleText = await page.$$eval('\*', els => els.filter(el => el.offsetParent !== null).map(el => el.textContent).join('\n'));

9. DOM Cleanup and Paywall Bypass
   Remove Paywalls and Overlays: Clean DOM of paywalls, modals, and subscriptions.
   Example:
   await page.evaluate(() => {
   document.querySelectorAll('div[id*="paywall"], div[class*="paywall"], .modal, .modal-backdrop, div[style*="position: fixed"]').forEach(el => el.remove());
   document.body.style.overflow = 'auto';
   });

Clean Non-Content: Remove ads, social elements, and empty nodes.
Example:
await page.evaluate(() => {
document.querySelectorAll('.ad, .social-share, script, iframe, :empty').forEach(el => el.remove());
});

Wait for Content: Ensure article text loads before extraction.
Example:
await page.waitForSelector('.article-content', { timeout: 10000 }).catch(() => console.log('Fallback to body'));
