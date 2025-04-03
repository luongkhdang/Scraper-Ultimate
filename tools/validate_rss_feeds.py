#!/usr/bin/env python
"""
RSS Feed Validator

This script validates RSS feeds from sources/rss.md and reports their status.
Useful for identifying problematic feeds before running the main scraper.

Usage:
    python validate_rss_feeds.py
"""
import os
import sys
import time
import logging
import feedparser
import requests
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Tuple

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))), 'src'))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('rss_validator')

# Configuration
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
HEADERS = {'User-Agent': USER_AGENT}
TIMEOUT = REQUEST_TIMEOUT
MAX_WORKERS = 30


def read_rss_feeds(file_path: str) -> List[str]:
    """Read RSS feed URLs from a file"""
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()

        # Filter out empty lines, comments, and section headers
        feeds = [line.strip() for line in lines if line.strip() and
                 not line.strip().startswith('#')]

        logger.info(f"Read {len(feeds)} RSS feeds from {file_path}")
        return feeds
    except Exception as e:
        logger.error(f"Error reading RSS feeds from {file_path}: {e}")
        return []


def validate_feed(feed_url: str) -> Tuple[str, bool, str, int]:
    """
    Validate a single RSS feed

    Returns:
        Tuple of (url, is_valid, message, entry_count)
    """
    try:
        # Try with requests first for better error handling
        response = requests.get(feed_url, headers=HEADERS, timeout=TIMEOUT)

        if response.status_code != 200:
            return feed_url, False, f"HTTP error: {response.status_code}", 0

        # Parse the feed
        feed = feedparser.parse(response.content)

        # Check for bozo flag (feedparser's error indicator)
        if feed.get('bozo', 0) == 1 and hasattr(feed, 'bozo_exception'):
            exception = str(feed.bozo_exception)
            # Some warnings can be ignored
            if "is not well-formed" in exception:
                logger.warning(
                    f"Feed has format issues but may still work: {feed_url}")
                # Continue checking anyway
            else:
                return feed_url, False, f"Parse error: {exception}", 0

        # Check if entries are available
        if not hasattr(feed, 'entries') or len(feed.entries) == 0:
            return feed_url, False, "No entries found", 0

        # Check if entries have the required fields (title, link)
        entry_count = len(feed.entries)
        valid_entries = 0

        for entry in feed.entries:
            if 'title' in entry and ('link' in entry or hasattr(entry, 'link')):
                valid_entries += 1

        if valid_entries == 0:
            return feed_url, False, "No valid entries with title and link", 0

        return feed_url, True, f"Valid ({valid_entries}/{entry_count} entries)", entry_count

    except requests.RequestException as e:
        return feed_url, False, f"Request error: {str(e)}", 0
    except Exception as e:
        return feed_url, False, f"Error: {str(e)}", 0


def main():
    # Determine the path to sources/rss.md
    script_dir = os.path.dirname(os.path.abspath(__file__))
    rss_file_path = os.path.join(
        os.path.dirname(script_dir), 'sources', 'rss.md')

    if not os.path.exists(rss_file_path):
        logger.error(f"RSS file not found: {rss_file_path}")
        return

    # Read feeds
    feeds = read_rss_feeds(rss_file_path)

    if not feeds:
        logger.error("No feeds found to validate")
        return

    logger.info(f"Validating {len(feeds)} RSS feeds...")

    # Track results
    results = []

    # Process feeds in parallel
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_feed = {executor.submit(
            validate_feed, feed): feed for feed in feeds}

        for future in future_to_feed:
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                feed = future_to_feed[future]
                logger.error(f"Error processing feed {feed}: {e}")
                results.append((feed, False, f"Processing error: {str(e)}", 0))

    # Sort results by validity and URL
    results.sort(key=lambda x: (not x[1], x[0]))

    # Count valid and invalid feeds
    valid_feeds = sum(1 for r in results if r[1])
    invalid_feeds = len(results) - valid_feeds

    # Print summary
    print("\n" + "="*80)
    print(
        f"RSS FEED VALIDATION RESULTS: {valid_feeds} valid, {invalid_feeds} invalid")
    print("="*80)

    # Print valid feeds
    if valid_feeds > 0:
        print("\nVALID FEEDS:")
        for url, valid, message, count in results:
            if valid:
                print(f"✅ {url} - {message}")

    # Print invalid feeds
    if invalid_feeds > 0:
        print("\nINVALID FEEDS:")
        for url, valid, message, count in results:
            if not valid:
                print(f"❌ {url} - {message}")

    # Write recommendations to file
    output_file = os.path.join(os.path.dirname(
        script_dir), 'sources', 'reliable_rss.md')
    with open(output_file, 'w') as f:
        f.write("# Reliable RSS Feeds\n\n")
        f.write(
            "The following feeds have been automatically validated and are confirmed working:\n\n")

        for url, valid, message, count in results:
            if valid:
                f.write(f"{url}\n")

    logger.info(f"Recommendations written to {output_file}")


if __name__ == "__main__":
    main()
