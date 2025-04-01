# Browser Rendering & Article Scraping Module

This document explains how the `puppeteer.ts` module works in the Meridian news scraping system. This module is responsible for retrieving article content from various websites using different strategies.

## Overview

The module provides three key functions for retrieving content:
1. `getArticleWithBrowser` - Uses Cloudflare's Browser Rendering API (headless browser)
2. `getArticleWithFetch` - Simpler fetch-based approach
3. `getRssFeedWithFetch` - Specifically for fetching RSS feeds

## Key Concepts

### User Agent Randomization

The module uses a rotating set of mobile user agents to avoid detection:
- iOS Safari and Chrome (preferred by publishers)
- Android Samsung and Pixel devices

```typescript
const userAgents = [
  // iOS devices (preferred by publishers)
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15...',
  // Android devices
  'Mozilla/5.0 (Linux; Android 14; SM-S908B) AppleWebKit/537.36...',
  // ...
];
```

### Referrer Rotation

Each request uses a random referrer to appear as natural traffic:
```typescript
const referrers = [
  'https://www.google.com/',
  'https://www.bing.com/search?q=relevant+search+term',
  'https://www.reddit.com/r/relevant_subreddit',
  'https://t.co/shortened_url', // looks like twitter
  'https://www.linkedin.com/feed/',
];
```

## Function Details

### `getArticleWithBrowser`

This is the most powerful scraping method, used for complex sites with paywalls or heavy JavaScript.

```typescript
getArticleWithBrowser(env: Env, url: string)
```

#### Features:
- Uses Cloudflare's Browser Rendering API (headless browser)
- Simulates a mobile device (iPhone/Android)
- Executes JavaScript to:
  - Normalize date formatting
  - Click cookie consent buttons
  - Remove paywalls, modals, and subscription overlays
  - Clean up the DOM by removing ads, social elements, etc.
  - Strip unnecessary attributes
  - Remove empty elements
- Waits for specific article content selectors to appear

#### Usage Example:
```typescript
const articleResult = await getArticleWithBrowser(env, "https://example.com/article");
if (articleResult.isOk()) {
  // Access content via: articleResult.value.title, articleResult.value.text
}
```

### `getArticleWithFetch`

A lighter, faster option for simpler websites that don't require JavaScript execution.

```typescript
getArticleWithFetch(url: string)
```

#### Features:
- Simple HTTP request with randomized user agent and referrer
- Doesn't execute JavaScript or interact with the page
- Much faster but less capable than browser rendering

#### Usage Example:
```typescript
const articleResult = await getArticleWithFetch("https://example.com/article");
if (articleResult.isOk()) {
  // Access content via: articleResult.value.title, articleResult.value.text
}
```

### `getRssFeedWithFetch`

Specialized for retrieving RSS feed XML content.

```typescript
getRssFeedWithFetch(url: string)
```

#### Features:
- Simple HTTP request with randomized user agent and referrer
- Returns the raw XML content for further processing

#### Usage Example:
```typescript
const feedResult = await getRssFeedWithFetch("https://example.com/feed.xml");
if (feedResult.isOk()) {
  // Process XML content with parseRSSFeed
  const parsedFeed = await parseRSSFeed(feedResult.value);
}
```

## Paywall Bypass Techniques

The module employs several techniques to bypass paywalls:

1. **DOM Manipulation**:
   ```javascript
   "(() => { const paywallElements = Array.from(document.querySelectorAll('div, section')).filter(el => el.id.toLowerCase().includes('paywall') || el.className.toLowerCase().includes('paywall') || el.id.toLowerCase().includes('subscribe') || el.className.toLowerCase().includes('subscribe')); paywallElements.forEach(el => el.remove()); document.querySelectorAll('.modal, .modal-backdrop, body > div[style*=\"position: fixed\"]').forEach(el => el.remove()); document.body.style.overflow = 'auto'; })();"
   ```

2. **Mobile User Agents**: Many sites show different experiences to mobile users

3. **Cookie Consent Handling**:
   ```javascript
   "(() => { const cookieButtons = Array.from(document.querySelectorAll('button, a')).filter(el => el.textContent.toLowerCase().includes('accept') && (el.textContent.toLowerCase().includes('cookie') || el.textContent.toLowerCase().includes('consent'))); if(cookieButtons.length > 0) { cookieButtons[0].click(); } })();"
   ```

4. **Content Extraction**: Uses Mozilla's Readability to extract article text even when the layout is complex

## DOM Cleanup Process

To improve extraction reliability, the module:

1. Removes advertisements, social elements, and non-content areas
2. Strips unnecessary attributes except for href, src, alt, title
3. Removes empty elements
4. Removes scripts, iframes, and other non-content elements

## Error Handling

All functions return a Result type from neverthrow library:
- Success: `ok(value)`
- Error: `err({ type: 'ERROR_TYPE', error: errorObject })`

Error types include:
- `FETCH_ERROR`: Network or request failures
- `VALIDATION_ERROR`: Response validation failures
- `PARSE_ERROR`: Content parsing failures

## Dependencies

- `zod`: For schema validation
- `neverthrow`: For error handling with Result types
- `@mozilla/readability`: For article content extraction (used in parsers.ts)

## Notes for Maintenance

- The script injection techniques are brittle and may need periodic updates
- User agents should be updated periodically to stay current
- The selector `article, .article, .content, .post, #article, main` may need adjustments based on target sites 


export const articleSchema = z.object({
  status: z.coerce.boolean(),
  errors: z.array(z.object({ code: z.number(), message: z.string() })).optional(),
  result: z.string(),
});

const userAgents = [
  // ios (golden standard for publishers)
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1', // iphone safari (best overall)
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/123.0.6312.87 Mobile/15E148 Safari/604.1', // iphone chrome

  // android (good alternatives)
  'Mozilla/5.0 (Linux; Android 14; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36', // samsung flagship
  'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36', // pixel
];

const referrers = [
  'https://www.google.com/',
  'https://www.bing.com/search?q=relevant+search+term',
  'https://www.reddit.com/r/relevant_subreddit',
  'https://t.co/shortened_url', // looks like twitter
  'https://www.linkedin.com/feed/',
];

export async function getArticleWithBrowser(env: Env, url: string) {
  const response = await safeFetch(
    `https://api.cloudflare.com/client/v4/accounts/${env.CLOUDFLARE_ACCOUNT_ID}/browser-rendering/content`,
    'json',
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${env.CLOUDFLARE_BROWSER_RENDERING_API_TOKEN}`,
      },
      body: JSON.stringify({
        url,
        userAgent: userAgents[Math.floor(Math.random() * userAgents.length)],
        setExtraHTTPHeaders: {
          Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
          'Accept-Encoding': 'gzip, deflate, br',
          Connection: 'keep-alive',
          DNT: '1',
          'Accept-Language': 'en-US,en;q=0.5',
          'Sec-Fetch-Dest': 'document',
          'Sec-Fetch-Mode': 'navigate',
          'Sec-Fetch-Site': 'none',
          'Sec-Fetch-User': '?1',
          'Upgrade-Insecure-Requests': '1',
        },
        cookies: [],
        gotoOptions: {
          waitUntil: 'networkidle0',
          timeout: 30000,
          referer: referrers[Math.floor(Math.random() * referrers.length)],
        },
        viewport: {
          width: 390,
          height: 844,
          deviceScaleFactor: 3,
          isMobile: true,
          hasTouch: true,
          isLandscape: false,
        },
        rejectResourceTypes: ['image', 'media', 'font', 'websocket'],
        bestAttempt: true,
        // all of these are very brittle, like all script tag usage
        // this mostly works for now but good to revisit every once in a while
        addScriptTag: [
          // fixes date formatting to be in US English
          {
            content:
              "(() => { Object.defineProperty(Intl, 'DateTimeFormat', { \n    writable: true, \n    value: new Proxy(Intl.DateTimeFormat, { \n      construct: (target, args) => new target('en-US', Object.assign({}, args[1])) \n    })\n  }); })();",
          },
          // clicks on cookie consent buttons
          {
            content:
              "(() => { const cookieButtons = Array.from(document.querySelectorAll(\'button, a\')).filter(el => el.textContent.toLowerCase().includes(\'accept\') && (el.textContent.toLowerCase().includes(\'cookie\') || el.textContent.toLowerCase().includes(\'consent\'))); if(cookieButtons.length > 0) { cookieButtons[0].click(); } })();",
          },
          // try to remove paywalls
          {
            content:
              "(() => { const paywallElements = Array.from(document.querySelectorAll(\'div, section\')).filter(el => el.id.toLowerCase().includes(\'paywall\') || el.className.toLowerCase().includes(\'paywall\') || el.id.toLowerCase().includes(\'subscribe\') || el.className.toLowerCase().includes(\'subscribe\')); paywallElements.forEach(el => el.remove()); document.querySelectorAll(\'.modal, .modal-backdrop, body > div[style*=\"position: fixed\"]\').forEach(el => el.remove()); document.body.style.overflow = \'auto\'; })();",
          },
          // remove all script, style, iframe, .ad, .ads, .advertisement, [class*="social"], [id*="social"], .share, .comments, aside, nav, header:not(article header), footer:not(article footer), [role="complementary"], [role="banner"], [role="navigation"], form, .related, .recommended, .newsletter, .subscription
          {
            content:
              '(() => { document.querySelectorAll(\'script, style, iframe, .ad, .ads, .advertisement, [class*="social"], [id*="social"], .share, .comments, aside, nav, header:not(article header), footer:not(article footer), [role="complementary"], [role="banner"], [role="navigation"], form, .related, .recommended, .newsletter, .subscription\').forEach(el => el.remove()); })();',
          },
          // remove all attributes except href, src, alt, title
          {
            content:
              "(() => { const keepAttributes = [\'href\', \'src\', \'alt\', \'title\']; document.querySelectorAll(\'*\').forEach(el => { [...el.attributes].forEach(attr => { if (!keepAttributes.includes(attr.name.toLowerCase())) { el.removeAttribute(attr.name); }}); }); })();",
          },
          // remove all empty div, span, p, section, article
          {
            content:
              "(() => { function removeEmpty() { let removed = 0; document.querySelectorAll(\'div, span, p, section, article\').forEach(el => { if (!el.hasChildNodes() || el.textContent.trim() === \'\') { el.remove(); removed++; } }); return removed; } let pass; do { pass = removeEmpty(); } while(pass > 0); })();",
          },
          // remove all meta tags with only one attribute
          {
            content:
              "(() => { document.querySelectorAll(\'meta\').forEach(meta => { if (meta.attributes.length <= 1) { meta.remove(); } }); })();",
          },
        ],
        waitForSelector: {
          selector: 'article, .article, .content, .post, #article, main',
          timeout: 5000,
        },
      }),
    }
  );
  if (response.isErr()) {
    return err({ type: 'FETCH_ERROR', error: response.error });
  }

  const parsedPageContent = articleSchema.safeParse(response.value);
  if (parsedPageContent.success === false) {
    return err({ type: 'VALIDATION_ERROR', error: parsedPageContent.error });
  }

  const articleResult = parseArticle({ html: parsedPageContent.data.result });
  if (articleResult.isErr()) {
    return err({ type: 'PARSE_ERROR', error: articleResult.error });
  }

  return ok(articleResult.value);
}

export async function getArticleWithFetch(url: string) {
  const response = await safeFetch(url, 'text', {
    method: 'GET',
    headers: {
      'User-Agent': userAgents[Math.floor(Math.random() * userAgents.length)],
      Referer: referrers[Math.floor(Math.random() * referrers.length)],
    },
  });
  if (response.isErr()) {
    return err({ type: 'FETCH_ERROR', error: response.error });
  } else if (typeof response.value !== 'string') {
    return err({ type: 'FETCH_ERROR', error: new Error('Response is not a string') });
  }

  const articleResult = parseArticle({ html: response.value });
  if (articleResult.isErr()) {
    return err({ type: 'PARSE_ERROR', error: articleResult.error });
  }

  return ok(articleResult.value);
}

export async function getRssFeedWithFetch(url: string) {
  const response = await safeFetch(url, 'text', {
    method: 'GET',
    headers: {
      'User-Agent': userAgents[Math.floor(Math.random() * userAgents.length)],
      Referer: referrers[Math.floor(Math.random() * referrers.length)],
    },
  });
  if (response.isErr()) {
    return err({ type: 'FETCH_ERROR', error: response.error });
  } else if (typeof response.value !== 'string') {
    return err({ type: 'FETCH_ERROR', error: new Error('Response is not a string') });
  }

  return ok(response.value);
}
