"""
RSS Feed Extractor: Extracts article URLs and content from RSS feeds.

Exported Functions:
- extract_rss_feed_urls(website_url: str) -> List[str]: Discovers RSS feed URLs from a website
- extract_urls_from_rss_feeds(website_url: str, base_url: str, feed_urls: List[str]) -> Set[str]: Extracts article URLs from RSS feeds
- extract_content_from_rss_feed(feed_url: str) -> List[Dict[str, Any]]: Extracts full content from an RSS feed

Related Files:
- src/scraper/scraper_hooks/url_extractor.py: Uses this module for finding article URLs
- src/scraper/scraper_hooks/utils.py: Provides utility functions for HTTP requests
- src/scraper/scraper_client.py: Main client that uses these functions
"""
import newspaper
import feedparser
import logging
import time
import requests
import random
import json
from typing import List, Set, Dict, Any, Optional
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, urlunparse

# Import local modules
from .utils import make_request, random_delay, get_random_user_agent
from .url_validator import is_valid_article_url

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants for retry settings
MAX_RETRIES = 8  # Increased from 5 to 8
RETRY_DELAY = 2
INITIAL_TIMEOUT = 15  # Base timeout in seconds
TIMEOUT_BACKOFF_FACTOR = 1.2  # Less aggressive backoff
MAX_DELAY = 40  # Cap maximum delay to avoid excessive waiting

# Expanded rotating user agents
USER_AGENTS = [
    # iOS devices (preferred by publishers)
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/123.0.6312.87 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPad; CPU OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    # Android devices
    'Mozilla/5.0 (Linux; Android 14; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36',
    # Desktop browsers
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
    # News reader agents
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Feedly/1.0',
    'Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Googlebot/2.1; +http://www.google.com/bot.html) Chrome/123.0.0.0 Safari/537.36'
]

# Enhanced rotating referrers
REFERRERS = [
    'https://www.google.com/',
    'https://www.google.com/search?q=news',
    'https://www.bing.com/search?q=news',
    'https://www.reddit.com/r/news',
    'https://t.co/shortened_url',  # looks like twitter
    'https://www.linkedin.com/feed/',
    'https://news.google.com/',
    'https://feedly.com/i/latest'
]

# Additional headers for requests (based on puppeteer.ts)
ADDITIONAL_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'DNT': '1',
    'Accept-Language': 'en-US,en;q=0.5',
    'Upgrade-Insecure-Requests': '1',
}

# Known problematic feed domains that need special handling
PROBLEMATIC_FEEDS = {
    'feeds.content.dowjones.io': {'method': 'direct_parse', 'parser': 'xml'},
    'economist.com': {'method': 'desktop_agent', 'parser': 'html.parser'},
    'wsj.com': {'method': 'desktop_agent', 'parser': 'html.parser'},
    'telegraph.co.uk': {'method': 'desktop_agent', 'parser': 'html.parser'},
    'theguardian.com': {'method': 'direct_parse', 'parser': 'xml'},
    'nytimes.com': {'method': 'desktop_agent', 'parser': 'html.parser'},
    'washingtonpost.com': {'method': 'direct_parse', 'parser': 'xml'},
    'benzinga.com': {'method': 'feedburner_fix', 'parser': 'xml'},
    'feeds.feedburner.com': {'method': 'feedburner_fix', 'parser': 'xml'},
    'marketwatch.com': {'method': 'desktop_agent', 'parser': 'html.parser'}
}

# More comprehensive parser options
FEED_PARSERS = ['xml', 'lxml', 'html.parser', 'html5lib']

# Special case headers for sites that block requests
SPECIAL_HEADERS = {
    'economist.com': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml, */*',
    },
    'wsj.com': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml, */*',
    }
}


def normalize_url(url: str) -> str:
    """
    Normalize URL by removing fragments, default ports, etc.

    Args:
        url: URL to normalize

    Returns:
        Normalized URL
    """
    if not url:
        return url

    try:
        # Parse URL
        parsed = urlparse(url)

        # Remove fragments
        parsed = parsed._replace(fragment='')

        # Handle common tracking parameters
        query = parsed.query
        if query:
            # List of tracking parameters to remove
            tracking_params = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term',
                               'utm_content', 'fbclid', 'gclid', 'ocid', 'ncid']

            # Parse query parameters
            params = query.split('&')
            filtered_params = []

            for param in params:
                if '=' in param:
                    name = param.split('=')[0]
                    if name.lower() not in tracking_params:
                        filtered_params.append(param)
                else:
                    filtered_params.append(param)

            # Reconstruct query
            parsed = parsed._replace(query='&'.join(filtered_params))

        # Reconstruct URL
        normalized = urlunparse(parsed)

        # Remove trailing slash if present
        if normalized.endswith('/'):
            normalized = normalized[:-1]

        return normalized

    except Exception as e:
        logger.warning(f"Error normalizing URL {url}: {e}")
        return url


def extract_rss_feed_urls(website_url: str) -> List[str]:
    """
    Discover RSS feed URLs from a website

    Args:
        website_url: The main website URL to scan for RSS feeds

    Returns:
        List of discovered RSS feed URLs
    """
    feed_urls = []

    try:
        # Select random user agent and referrer for each attempt
        user_agent = random.choice(USER_AGENTS)
        referrer = random.choice(REFERRERS)

        # Prepare headers
        headers = {
            'User-Agent': user_agent,
            'Referer': referrer,
            **ADDITIONAL_HEADERS
        }

        logger.info(f"Discovering RSS feeds from website: {website_url}")

        # Method 1: Use newspaper's built-in feed URL detection
        site = newspaper.build(
            website_url, memoize_articles=False, browser_user_agent=user_agent)
        newspaper_feeds = site.feed_urls()
        if newspaper_feeds:
            for feed_url in newspaper_feeds:
                normalized_url = normalize_url(feed_url)
                if normalized_url not in feed_urls:
                    feed_urls.append(normalized_url)
            logger.info(
                f"Found {len(newspaper_feeds)} RSS feeds using newspaper")

        # Method 2: Look for common RSS feed links in HTML
        try:
            response = requests.get(website_url, headers=headers, timeout=15)
            if response.status_code != 200:
                logger.warning(
                    f"HTTP error {response.status_code} for {website_url}")
                # Try with a different user agent
                alt_user_agent = random.choice(USER_AGENTS)
                alt_headers = {'User-Agent': alt_user_agent}
                response = requests.get(
                    website_url, headers=alt_headers, timeout=15)
        except Exception as e:
            logger.warning(f"Error requesting {website_url}: {e}")
            response = None

        if response and response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')

            # Method 2a: Look for link elements with RSS-related attributes
            rss_links = soup.find_all('link', rel=['alternate', 'feed'],
                                      type=['application/rss+xml', 'application/atom+xml'])

            for link in rss_links:
                href = link.get('href')
                if href:
                    full_url = urljoin(website_url, href)
                    normalized_url = normalize_url(full_url)
                    if normalized_url not in feed_urls:
                        feed_urls.append(normalized_url)

            # Method 2b: Look for <a> tags with RSS feed indicators
            rss_indicators = ['rss', 'feed', 'atom', 'syndication', 'xml']
            for a_tag in soup.find_all('a', href=True):
                href = a_tag.get('href', '')
                text = a_tag.get_text().lower()

                # Check if link or text suggests it's a feed
                if (any(indicator in href.lower() for indicator in rss_indicators) or
                        any(indicator in text for indicator in rss_indicators)):

                    # Check common RSS feed extensions
                    if (href.endswith(('.xml', '.rss', '.atom')) or
                        '/feed/' in href.lower() or
                            '/rss/' in href.lower()):
                        full_url = urljoin(website_url, href)
                        normalized_url = normalize_url(full_url)
                        if normalized_url not in feed_urls:
                            feed_urls.append(normalized_url)

            # Method 2c: Check known feed paths
            common_feed_paths = [
                '/feed',
                '/rss',
                '/atom',
                '/feed/rss',
                '/feed/atom',
                '/rss/feed',
                '/index.xml',
                '/rss.xml',
                '/atom.xml',
                '/feed.xml',
                '/feeds/posts/default',
                '/?feed=rss',
                '/?feed=atom'
            ]

            for path in common_feed_paths:
                feed_url = urljoin(website_url, path)
                # Check if this URL has already been found
                normalized_url = normalize_url(feed_url)
                if normalized_url not in feed_urls:
                    # Try to access the URL to verify it's a valid feed
                    try:
                        test_headers = {
                            'User-Agent': random.choice(USER_AGENTS)}
                        test_response = requests.head(
                            feed_url, headers=test_headers, timeout=5)
                        if test_response.status_code == 200:
                            content_type = test_response.headers.get(
                                'Content-Type', '')
                            if ('xml' in content_type.lower() or
                                'rss' in content_type.lower() or
                                    'atom' in content_type.lower()):
                                feed_urls.append(normalized_url)
                                logger.info(
                                    f"Found feed at common path: {feed_url}")
                    except Exception:
                        # Skip if there's an error checking this URL
                        pass

            logger.info(f"Found {len(feed_urls)} total RSS feeds")

    except Exception as e:
        logger.error(f"Error discovering RSS feeds: {e}")

    # Validate each feed by making a test request
    validated_feeds = []
    for feed_url in feed_urls:
        try:
            # Try to access the URL with a HEAD request first
            test_headers = {'User-Agent': random.choice(USER_AGENTS)}
            test_response = requests.head(
                feed_url, headers=test_headers, timeout=5)

            if test_response.status_code == 200:
                # If HEAD request succeeds, check if it's actually a feed with a small GET request
                test_response = requests.get(
                    feed_url, headers=test_headers, timeout=10)
                if test_response.status_code == 200:
                    # Try to parse as a feed
                    test_feed = feedparser.parse(test_response.content)
                    if not test_feed.get('bozo', 1) or (hasattr(test_feed, 'entries') and test_feed.entries):
                        validated_feeds.append(feed_url)
                        logger.info(f"Validated feed: {feed_url}")
        except Exception as e:
            logger.debug(f"Failed to validate feed {feed_url}: {e}")

    logger.info(
        f"Validated {len(validated_feeds)} out of {len(feed_urls)} discovered feeds")
    return validated_feeds


def extract_urls_from_rss_feeds(website_url: str, base_url: str, feed_urls: List[str]) -> Set[str]:
    """
    Extract article URLs from RSS feeds

    Args:
        website_url: The main website URL
        base_url: The base domain URL
        feed_urls: List of RSS feed URLs to process

    Returns:
        Set of article URLs extracted from RSS feeds
    """
    rss_article_urls = set()

    for feed_url in feed_urls:
        try:
            logger.info(f"Processing RSS feed: {feed_url}")
            feed_response = make_request(feed_url)

            if not feed_response or feed_response.status_code != 200:
                continue

            # Parse the feed (supports both XML and Atom formats)
            feed_soup = BeautifulSoup(feed_response.text, 'xml')

            # Extract links from items (RSS) or entries (Atom)
            for item in feed_soup.find_all(['item', 'entry']):
                # Try different ways RSS feeds might provide links
                link = None

                # Option 1: <link> element with URL as text content
                link_tag = item.find('link')
                if link_tag and link_tag.string:
                    link = link_tag.string.strip()

                # Option 2: <link> element with href attribute (Atom)
                elif link_tag and link_tag.get('href'):
                    link = link_tag.get('href').strip()

                # Option 3: <guid> element that might contain the URL
                elif item.find('guid'):
                    guid = item.find('guid').string.strip()
                    if guid.startswith('http'):
                        link = guid

                # If we found a link, validate and add it
                if link:
                    full_url = urljoin(website_url, link)
                    if is_valid_article_url(full_url, base_url):
                        rss_article_urls.add(full_url)

            logger.info(
                f"Found {len(rss_article_urls)} article URLs from RSS feed {feed_url}")

        except Exception as e:
            logger.warning(f"Error processing RSS feed {feed_url}: {e}")

    return rss_article_urls


def extract_content_from_rss_feed(feed_url: str) -> List[Dict[str, Any]]:
    """
    Extract full content and metadata from an RSS feed with retry mechanism
    and specialized handling for problematic feeds

    Args:
        feed_url: URL of the RSS feed to extract content from

    Returns:
        List of dictionaries containing article metadata and content
    """
    articles = []

    # Initialize retry counter
    retries = 0
    # Add an overall timeout for the entire function
    overall_start_time = time.time()
    # Maximum time in seconds this function should run before giving up
    max_overall_timeout = 60

    # Track the specific errors for better retry handling
    connection_errors = 0
    timeout_errors = 0
    parse_errors = 0
    http_errors = 0

    # Get domain from feed URL for special handling
    domain = urlparse(feed_url).netloc

    # Track which approaches have been tried to avoid repeating failures
    tried_approaches = set()

    # Identify if this is a problematic feed that needs special handling
    special_handling = None
    for site, config in PROBLEMATIC_FEEDS.items():
        if site in domain:
            special_handling = config
            break

    if not special_handling:
        special_handling = {'method': 'standard', 'parser': 'xml'}

    logger.info(
        f"Feed {feed_url} identified as {special_handling['method']} method")

    while retries < MAX_RETRIES:
        try:
            # Calculate timeout with exponential backoff, but cap at maximum
            backoff_factor = min(TIMEOUT_BACKOFF_FACTOR **
                                 retries, MAX_DELAY / INITIAL_TIMEOUT)
            current_timeout = INITIAL_TIMEOUT * backoff_factor

            # Get special headers if needed for this domain
            domain_headers = None
            for site, headers in SPECIAL_HEADERS.items():
                if site in domain:
                    domain_headers = headers
                    break

            # Select user agent based on special handling method and retry attempt
            # Vary user agent on each retry to bypass blocks
            user_agent = None
            if special_handling['method'] == 'desktop_agent':
                # Use desktop browser user agent for sites that block mobile
                # Cycle through desktop agents
                user_agent = USER_AGENTS[5 + (retries % 3)]
            else:
                # Use a different user agent for each retry
                user_agent = USER_AGENTS[retries % len(USER_AGENTS)]

            # Prepare headers
            headers = {
                'User-Agent': user_agent,
                # Different referrer each time
                'Referer': REFERRERS[retries % len(REFERRERS)],
                **ADDITIONAL_HEADERS
            }

            # Add Accept header indicating we prefer RSS/XML content
            headers['Accept'] = 'application/rss+xml, application/atom+xml, application/xml, text/xml, */*'

            # Override with domain-specific headers if available
            if domain_headers:
                headers.update(domain_headers)

            logger.info(
                f"Extracting content from RSS feed: {feed_url} (Attempt {retries + 1}/{MAX_RETRIES}, timeout={current_timeout:.1f}s)")

            # Track this approach to avoid repeating the exact same approach
            approach = f"{special_handling['method']}_{user_agent[:20]}"
            if approach in tried_approaches:
                # If we've tried this method before, vary the headers
                headers['Accept-Language'] = random.choice(
                    ['en-US,en;q=0.9', 'en-GB,en;q=0.8', 'en;q=0.7'])
                headers['Cache-Control'] = 'no-cache'
                approach = f"{approach}_variant"

            tried_approaches.add(approach)

            feed = None

            # Try multiple approaches in sequence:

            # APPROACH 1: Direct feedparser parsing
            if 'direct_feedparser' not in tried_approaches and retries < 2:
                tried_approaches.add('direct_feedparser')
                try:
                    logger.info(f"Trying direct feedparser for {feed_url}")
                    feed = feedparser.parse(feed_url)

                    if not feed.get('bozo', 0) and hasattr(feed, 'entries') and feed.entries:
                        logger.info(
                            f"Direct feedparser successful for {feed_url}")
                except Exception as e:
                    logger.warning(f"Direct feedparser failed: {e}")

            # Handle different methods based on the special handling type
            if not (feed and hasattr(feed, 'entries') and feed.entries):
                if special_handling['method'] == 'direct_parse':
                    # For feeds that need direct XML parsing
                    try:
                        response = requests.get(
                            feed_url, headers=headers, timeout=current_timeout)
                        if response.status_code == 200:
                            # Try to parse directly with feedparser first
                            feed = feedparser.parse(response.content)

                            # Check if we got valid feed data
                            if hasattr(feed, 'entries') and feed.entries:
                                logger.info(
                                    f"Successfully parsed feed with feedparser: {feed_url}")
                            else:
                                # If feedparser doesn't work, try BeautifulSoup with XML parser
                                soup = BeautifulSoup(
                                    response.text, special_handling['parser'])
                                items = soup.find_all(['item', 'entry'])

                                if items:
                                    logger.info(
                                        f"Falling back to BeautifulSoup XML parsing for {feed_url}")
                                    articles = _extract_articles_from_soup(
                                        soup, items)
                                    if articles:
                                        return articles
                        else:
                            logger.warning(
                                f"HTTP error {response.status_code} for {feed_url}")
                            http_errors += 1
                    except Exception as e:
                        logger.warning(f"Error during direct parsing: {e}")
                        if isinstance(e, requests.Timeout):
                            timeout_errors += 1

                elif special_handling['method'] == 'feedburner_fix':
                    # Special handling for FeedBurner feeds
                    try:
                        # Add specific headers for FeedBurner
                        feedburner_headers = headers.copy()
                        feedburner_headers['Accept'] = 'application/rss+xml, application/rdf+xml, application/atom+xml, application/xml, text/xml'

                        response = requests.get(
                            feed_url, headers=feedburner_headers, timeout=current_timeout)

                        if response.status_code == 200:
                            # Try both XML and regular parsing
                            soup = BeautifulSoup(response.text, 'xml')
                            items = soup.find_all(['item', 'entry'])

                            if items:
                                logger.info(
                                    f"Using XML parser for FeedBurner feed: {feed_url}")
                                articles = _extract_articles_from_soup(
                                    soup, items)
                                if articles:
                                    return articles

                            # If XML parsing doesn't yield results, try feedparser
                            feed = feedparser.parse(response.content)
                        else:
                            logger.warning(
                                f"HTTP error {response.status_code} for {feed_url}")
                            http_errors += 1
                    except Exception as e:
                        logger.warning(f"Error during FeedBurner parsing: {e}")
                        if isinstance(e, requests.Timeout):
                            timeout_errors += 1

            # If we haven't returned articles yet, try standard method
            if not (feed and hasattr(feed, 'entries') and feed.entries):
                try:
                    # Try using requests with chosen headers
                    response = requests.get(
                        feed_url, headers=headers, timeout=current_timeout)

                    if response.status_code == 200:
                        # Try each parser in sequence
                        for parser in FEED_PARSERS:
                            parser_approach = f"parser_{parser}"
                            if parser_approach in tried_approaches:
                                continue

                            tried_approaches.add(parser_approach)

                            try:
                                if parser == 'xml':
                                    # First try feedparser
                                    feed = feedparser.parse(response.content)

                                    # If we have entries, break the loop
                                    if hasattr(feed, 'entries') and feed.entries:
                                        logger.info(
                                            f"Feedparser successful with {parser}")
                                        break

                                # If feedparser doesn't work or we're trying alternative parsers
                                soup = BeautifulSoup(response.text, parser)
                                items = soup.find_all(['item', 'entry'])

                                if items:
                                    logger.info(
                                        f"Using {parser} parser for feed: {feed_url}")
                                    extracted = _extract_articles_from_soup(
                                        soup, items)
                                    if extracted:
                                        return extracted
                            except Exception as parser_e:
                                logger.debug(
                                    f"Parser {parser} failed: {parser_e}")
                                parse_errors += 1
                                continue
                    else:
                        http_status = response.status_code
                        logger.warning(
                            f"HTTP error {http_status} for {feed_url}")
                        http_errors += 1

                        # Adapt retry strategy based on HTTP status
                        if http_status == 403:  # Forbidden
                            # Forbidden might mean we need to vary our user agent more
                            logger.info(
                                "Forbidden response, trying with different headers")
                            headers['Accept'] = '*/*'
                            headers['User-Agent'] = random.choice(USER_AGENTS)
                        elif http_status == 429:  # Too many requests
                            # Rate limited, back off more aggressively
                            timeout_errors += 2  # Count as two timeouts
                        elif http_status >= 500:  # Server error
                            # Server error, might be temporary
                            http_errors += 1

                except requests.Timeout as e:
                    logger.warning(f"Timeout error for {feed_url}: {e}")
                    timeout_errors += 1

                    # For timeout errors, we might need a longer delay
                    sleep_time = min(
                        RETRY_DELAY * (2 ** timeout_errors), MAX_DELAY)
                    logger.info(
                        f"Timeout occurred, retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                    retries += 1
                    continue
                except requests.ConnectionError as e:
                    logger.warning(f"Connection error for {feed_url}: {e}")
                    connection_errors += 1

                    # Connection errors might require different backoff strategy
                    sleep_time = min(
                        RETRY_DELAY * (connection_errors + 1), MAX_DELAY)
                    logger.info(
                        f"Connection error, retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                    retries += 1
                    continue
                except Exception as e:
                    logger.warning(f"Request error for {feed_url}: {e}")

                    # If requests fails, fall back to feedparser's built-in fetching
                    try:
                        if 'direct_feedparser_fallback' not in tried_approaches:
                            tried_approaches.add('direct_feedparser_fallback')
                            feed = feedparser.parse(feed_url)
                    except Exception as inner_e:
                        logger.error(
                            f"Feedparser fallback also failed for {feed_url}: {inner_e}")

            # Process feedparser results if we have them
            if feed and hasattr(feed, 'entries') and feed.entries:
                logger.info(
                    f"Found {len(feed.entries)} entries in feed: {feed_url}")

                # Process each entry in the feed
                for entry in feed.entries:
                    article = {}

                    # Extract basic metadata
                    article['title'] = entry.get('title', '')

                    # Extract link - handle various ways links can be provided
                    article['link'] = entry.get('link', '')
                    if not article['link'] and 'guid' in entry and isinstance(entry.guid, str) and entry.guid.startswith('http'):
                        article['link'] = entry.guid

                    # Normalize the URL
                    if article['link']:
                        article['link'] = normalize_url(article['link'])

                    # Skip entries without a link
                    if not article['link']:
                        continue

                    # Extract date information
                    article['pubDate'] = entry.get('published', '')
                    if not article['pubDate']:
                        article['pubDate'] = entry.get('pubdate', '')
                    if not article['pubDate']:
                        article['pubDate'] = entry.get('updated', '')

                    # Extract language information
                    if 'language' in feed:
                        article['language'] = feed.language
                    else:
                        article['language'] = ''

                    # Extract description/summary
                    if 'summary' in entry:
                        article['description'] = entry.summary
                    elif 'description' in entry:
                        article['description'] = entry.description
                    else:
                        article['description'] = ''

                    # Extract author information
                    if 'author' in entry:
                        article['author'] = entry.author
                    elif 'authors' in entry and isinstance(entry.authors, list):
                        article['author'] = ', '.join(
                            [getattr(author, 'name', '') for author in entry.authors])
                    else:
                        article['author'] = ''

                    # Extract content
                    if 'content' in entry:
                        # Some feeds provide full content
                        if isinstance(entry.content, list) and len(entry.content) > 0:
                            if hasattr(entry.content[0], 'value'):
                                article['content'] = entry.content[0].value
                            else:
                                article['content'] = str(entry.content[0])
                        else:
                            article['content'] = str(entry.content)
                    else:
                        # Use description as fallback
                        article['content'] = article['description']

                    articles.append(article)

                # If we found at least one article, return the results
                if articles:
                    logger.info(
                        f"Successfully processed {len(articles)} articles from feed {feed_url}")
                    return articles

            # Advanced techniques for problematic feeds
            if retries >= MAX_RETRIES // 2:  # Only try these for later retries to save resources
                # Try JSON-based feeds using requests + JSON parsing
                if 'json_approach' not in tried_approaches:
                    tried_approaches.add('json_approach')
                    try:
                        logger.info(f"Trying JSON approach for {feed_url}")
                        json_headers = headers.copy()
                        json_headers['Accept'] = 'application/json, */*'

                        json_response = requests.get(
                            feed_url, headers=json_headers, timeout=current_timeout)
                        if json_response.status_code == 200:
                            try:
                                # Check if it's valid JSON
                                data = json.loads(json_response.text)

                                # Find articles in common JSON structures
                                json_articles = []

                                # Look for common patterns in JSON feeds
                                if 'items' in data:
                                    items = data['items']
                                elif 'entries' in data:
                                    items = data['entries']
                                elif 'articles' in data:
                                    items = data['articles']
                                elif 'posts' in data:
                                    items = data['posts']
                                else:
                                    items = []

                                for item in items:
                                    article = {}
                                    # Extract fields from JSON
                                    article['title'] = item.get('title', '')

                                    # Try different link fields
                                    article['link'] = item.get('link', item.get(
                                        'url', item.get('permalink', '')))

                                    # Skip without link
                                    if not article['link']:
                                        continue

                                    # Normalize link
                                    article['link'] = normalize_url(
                                        article['link'])

                                    # Other fields
                                    article['pubDate'] = item.get(
                                        'pubDate', item.get('date', item.get('published', '')))
                                    article['description'] = item.get(
                                        'description', item.get('summary', item.get('excerpt', '')))
                                    article['author'] = item.get(
                                        'author', item.get('creator', ''))
                                    article['content'] = item.get(
                                        'content', article['description'])

                                    json_articles.append(article)

                                if json_articles:
                                    logger.info(
                                        f"JSON approach found {len(json_articles)} articles for {feed_url}")
                                    return json_articles
                            except json.JSONDecodeError:
                                logger.debug(
                                    f"Not a valid JSON response from {feed_url}")
                    except Exception as e:
                        logger.warning(
                            f"JSON approach failed for {feed_url}: {e}")

                # Try to scrape with raw HTTP method for very problematic feeds
                if 'raw_http_approach' not in tried_approaches:
                    tried_approaches.add('raw_http_approach')
                    try:
                        # Try to use a more powerful scraping method
                        logger.info(f"Trying raw HTTP approach for {feed_url}")
                        result = _try_extract_with_raw_http(feed_url)
                        if result and len(result) > 0:
                            logger.info(
                                f"Successfully extracted {len(result)} articles with raw HTTP method")
                            return result
                    except Exception as e:
                        logger.error(f"Raw HTTP approach failed: {e}")

            # Check if we've exceeded the overall timeout
            if time.time() - overall_start_time > max_overall_timeout:
                logger.warning(
                    f"Exceeded maximum time ({max_overall_timeout}s) trying to extract content from {feed_url}. Giving up.")
                _log_failed_feed(
                    feed_url, f"Exceeded maximum timeout of {max_overall_timeout}s")
                return articles

            # If we have retried too many times, give up
            if retries >= MAX_RETRIES:
                logger.warning(
                    f"Maximum retries ({MAX_RETRIES}) reached for {feed_url}. Giving up.")
                _log_failed_feed(
                    feed_url, f"Maximum retries ({MAX_RETRIES}) reached")
                return articles

            # Calculate delay for next retry with adaptive backoff
            retry_delay = min(RETRY_DELAY * (2 ** retries), MAX_DELAY)

            # Adjust delay based on error types
            if timeout_errors > 0:
                retry_delay *= min(1.5, 1 + (timeout_errors * 0.2))
            if http_errors > 0:
                retry_delay *= min(1.3, 1 + (http_errors * 0.1))

            # Add jitter to avoid thundering herd (±20%)
            jitter_factor = random.uniform(0.8, 1.2)
            retry_delay *= jitter_factor

            retries += 1
            if retries < MAX_RETRIES:
                logger.info(
                    f"Retrying in {retry_delay:.1f} seconds... (Attempt {retries+1}/{MAX_RETRIES})")
                time.sleep(retry_delay)

        except Exception as e:
            logger.error(f"Error extracting content from feed {feed_url}: {e}")
            retries += 1
            if retries < MAX_RETRIES:
                sleep_time = min(RETRY_DELAY * (2 ** retries), MAX_DELAY)
                logger.info(
                    f"Retrying in {sleep_time:.1f} seconds... (Attempt {retries+1}/{MAX_RETRIES})")
                time.sleep(sleep_time)

    # Log empty article info as this is our most common failure
    if not articles:
        logger.error(
            f"No articles extracted from {feed_url} after {MAX_RETRIES} attempts")
        _log_failed_feed(feed_url, "No articles extracted")

    return articles


def _extract_articles_from_soup(soup, items):
    """Helper function to extract articles from soup items"""
    articles = []

    for item in items:
        article = {}

        # Extract title
        title_tag = item.find('title')
        article['title'] = title_tag.text if title_tag else ''

        # Extract link
        link_tag = item.find('link')
        if link_tag and link_tag.string:
            article['link'] = link_tag.string.strip()
        elif link_tag and link_tag.get('href'):
            article['link'] = link_tag.get('href').strip()
        elif item.find('guid') and item.find('guid').string and item.find('guid').string.startswith('http'):
            article['link'] = item.find('guid').string.strip()
        else:
            article['link'] = ''

        # Normalize the URL
        if article['link']:
            article['link'] = normalize_url(article['link'])

        # Skip if no link
        if not article['link']:
            continue

        # Extract date
        date_tag = item.find(
            ['pubDate', 'published', 'date', 'dc:date', 'updated'])
        article['pubDate'] = date_tag.text if date_tag else ''

        # Extract description
        desc_tag = item.find(
            ['description', 'summary', 'content', 'content:encoded'])
        article['description'] = desc_tag.text if desc_tag else ''

        # Extract language
        lang_tag = item.find(['language', 'xml:lang'])
        article['language'] = lang_tag.text if lang_tag else ''

        # Extract author
        author_tag = item.find(['author', 'dc:creator'])
        article['author'] = author_tag.text if author_tag else ''

        articles.append(article)

    return articles


def _try_extract_with_raw_http(feed_url):
    """Last resort method to extract feed content with custom HTTP request handling"""
    articles = []

    try:
        # Create a completely clean session
        session = requests.Session()

        # Use a desktop user agent
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Referer': 'https://www.google.com/',
            'sec-ch-ua': '"Not A(Brand";v="99", "Google Chrome";v="123", "Chromium";v="123"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'Upgrade-Insecure-Requests': '1'
        }

        # Try to get the feed with extended timeout
        response = session.get(feed_url, headers=headers, timeout=30)

        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '').lower()

            # Determine if this is JSON or XML
            if 'json' in content_type:
                # Parse as JSON
                try:
                    data = json.loads(response.text)
                    # Extract articles based on common JSON feed structures
                    if 'items' in data:
                        json_items = data['items']
                    elif 'entries' in data:
                        json_items = data['entries']
                    else:
                        json_items = []

                    for item in json_items:
                        article = {}
                        article['title'] = item.get('title', '')
                        article['link'] = item.get('url', item.get('link', ''))
                        article['pubDate'] = item.get(
                            'date', item.get('published', ''))
                        article['description'] = item.get(
                            'description', item.get('summary', ''))
                        article['author'] = item.get('author', '')

                        if article['link']:
                            articles.append(article)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse JSON from {feed_url}")
            else:
                # Try all parsers for XML/HTML content
                for parser in ['xml', 'html.parser', 'lxml', 'html5lib']:
                    try:
                        soup = BeautifulSoup(response.text, parser)

                        # Look for RSS/Atom items
                        items = soup.find_all(['item', 'entry'])

                        if items:
                            extracted = _extract_articles_from_soup(
                                soup, items)
                            if extracted:
                                articles.extend(extracted)
                                break
                    except Exception:
                        continue

        # Return any articles we found
        return articles

    except Exception as e:
        logger.error(f"Raw HTTP extraction failed: {e}")
        return []


def _log_failed_feed(feed_url, error_message):
    """Log failed feeds to a JSON file for tracking"""
    failed_file = "failed_feeds.json"

    try:
        # Try to read existing file
        try:
            with open(failed_file, 'r') as f:
                failed_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Create new structure if file doesn't exist or is invalid
            failed_data = {
                "total_failed_feeds": 0,
                "export_timestamp": str(time.localtime()),
                "feeds": {}
            }

        # Update the data
        feed_entry = {
            "error": error_message,
            "timestamp": str(time.strftime("%Y-%m-%d %H:%M:%S.%f", time.localtime()))
        }

        failed_data["feeds"][feed_url] = feed_entry
        failed_data["total_failed_feeds"] = len(failed_data["feeds"])
        failed_data["export_timestamp"] = str(time.localtime())

        # Write back to file
        with open(failed_file, 'w') as f:
            json.dump(failed_data, f, indent=2)

        logger.info(f"Logged failed feed {feed_url} to {failed_file}")
    except Exception as e:
        logger.error(f"Error logging failed feed: {e}")
