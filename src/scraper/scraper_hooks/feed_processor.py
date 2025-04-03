"""
Feed Processor: Processes RSS feed content, extracting specified fields.

Exported Functions:
- filter_feed_content(feed_items: List[Dict[str, Any]]) -> List[Dict[str, str]]: Filters feed content to include only specific fields
- filter_by_date(feed_items: List[Dict[str, str]], days: int = 2, feed_url: str = None) -> List[Dict[str, str]]: Filters feed items by publication date

Related Files:
- scraper_client.py: Main client file that uses these functions
- rss_feed_extractor.py: Core functions for RSS feed extraction
"""
import logging
from typing import List, Dict, Any
import datetime
from dateutil import parser
from email.utils import parsedate_to_datetime
import time

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def parse_date(date_str: str) -> datetime.datetime:
    """
    Parse a date string into a datetime object

    Args:
        date_str: Date string in various formats

    Returns:
        Datetime object or None if parsing fails
    """
    if not date_str:
        return None

    try:
        # Try email format (RFC 2822) first - common in RSS feeds
        return parsedate_to_datetime(date_str)
    except (TypeError, ValueError):
        pass

    try:
        # Try ISO format
        return parser.parse(date_str)
    except (TypeError, ValueError, parser.ParserError):
        pass

    return None


def filter_by_date(feed_items: List[Dict[str, str]], days: int = 2, feed_url: str = None) -> List[Dict[str, str]]:
    """
    Filter feed items to only include those published within specified days

    Args:
        feed_items: List of dictionaries containing feed item data
        days: Number of days to look back (default: 2 day)
        feed_url: Original feed URL for special handling of certain feeds

    Returns:
        List of dictionaries filtered by publication date
    """
    # Calculate the cutoff time (days ago from now)
    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(days=days)

    logger.info(
        f"Filtering items by publication date: newer than {cutoff.isoformat()}")

    # List of exempt feeds that always provide recent content but may not have pubDate
    EXEMPT_FEEDS = [
        "https://rsshub.app/apnews/topics/apf-topnews",
        "https://asia.nikkei.com/rss/feed/nar"
    ]

    # Check if this is an exempt feed that should bypass date filtering
    is_exempt_feed = feed_url and any(
        exempt_feed in feed_url for exempt_feed in EXEMPT_FEEDS)
    if is_exempt_feed:
        logger.info(
            f"Feed {feed_url} is exempt from date filtering - all articles will be kept")

        # Add current timestamp as pubDate for articles without pubDate
        timestamp_str = now.strftime("%a, %d %b %Y %H:%M:%S %z")
        for item in feed_items:
            if not item.get('pubDate'):
                item['pubDate'] = timestamp_str
                logger.debug(
                    f"Added current timestamp as pubDate for article: {item.get('title', 'No title')}")

        return feed_items

    filtered_items = []
    skipped_items = 0
    unparseable_dates = 0

    for item in feed_items:
        # Get publication date
        pub_date_str = item.get('pubDate', '')

        # Skip items without publication date
        if not pub_date_str:
            unparseable_dates += 1
            continue

        # Parse the date
        pub_date = parse_date(pub_date_str)

        # Skip items with unparseable dates
        if not pub_date:
            unparseable_dates += 1
            continue

        # Make pub_date timezone-aware if it isn't already
        if pub_date.tzinfo is None:
            pub_date = pub_date.replace(tzinfo=datetime.timezone.utc)

        # Keep only items newer than the cutoff
        if pub_date >= cutoff:
            filtered_items.append(item)
        else:
            skipped_items += 1

    logger.info(f"Date filtering results: {len(filtered_items)} items kept, "
                f"{skipped_items} skipped (too old), "
                f"{unparseable_dates} with unparseable dates")

    return filtered_items


def filter_feed_content(feed_items: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Filter feed content to include only specified fields: language, title, description, link, and pubDate

    Args:
        feed_items: List of dictionaries containing feed item data

    Returns:
        List of dictionaries containing only the specified fields
    """
    filtered_content = []
    logger.info(f"Filtering {len(feed_items)} feed items")

    # Debug info about first item if available
    if feed_items and len(feed_items) > 0:
        logger.info(f"Sample feed item keys: {list(feed_items[0].keys())}")

    for item in feed_items:
        # Handle link field - might be under different keys depending on the feed format
        link = item.get('link', '')
        if not link and 'url' in item:
            link = item.get('url', '')

        # Handle pubDate field - might be under different keys
        pub_date = item.get('pubDate', '')
        if not pub_date:
            # Try alternate fields for published date
            pub_date = item.get('published', '')
            if not pub_date:
                pub_date = item.get('date_published', '')
                if not pub_date:
                    pub_date = item.get('updated', '')

        # Handle description field - might be under different keys
        description = item.get('description', '')
        if not description and 'summary' in item:
            description = item.get('summary', '')
        if not description and 'content' in item:
            description = item.get('content', '')

        # Create filtered item with all the fields we need
        filtered_item = {
            'language': item.get('language', ''),
            'title': item.get('title', ''),
            'description': description,
            'link': link,
            'pubDate': pub_date
        }

        # Only add items that have at minimum a link and title
        if filtered_item['link'] and filtered_item['title']:
            filtered_content.append(filtered_item)

    logger.info(f"Filtered down to {len(filtered_content)} valid items")

    # Print sample of first item if available
    if filtered_content and len(filtered_content) > 0:
        logger.info(f"Sample filtered item: {filtered_content[0]}")

    return filtered_content
