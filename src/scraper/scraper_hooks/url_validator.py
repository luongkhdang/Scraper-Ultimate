"""
URL Validator: Functions to validate and filter article URLs.

Exported Functions:
- is_valid_article_url(url: str, base_url: str) -> bool: Checks if a URL is likely to be an article

Related Files:
- src/scraper/scraper_hooks/url_extractor.py: Uses this module to validate URLs during extraction
- src/scraper/scraper_hooks/content_extractor.py: May use this module to validate URLs before content extraction
"""
import re
from urllib.parse import urlparse


def is_valid_article_url(url: str, base_url: str) -> bool:
    """
    Check if the URL is likely to be an article

    Args:
        url: URL to check
        base_url: Base URL of the website

    Returns:
        True if likely an article URL, False otherwise
    """
    # Skip empty URLs
    if not url:
        return False

    # Parse the URL
    parsed_url = urlparse(url)

    # Skip URLs that don't belong to the same domain
    base_domain = urlparse(base_url).netloc
    if parsed_url.netloc and parsed_url.netloc != base_domain:
        # Allow subdomains of the same site (e.g., m.example.com for example.com)
        if not parsed_url.netloc.endswith(base_domain.split('www.')[-1]):
            return False

    # Skip common non-article paths
    skip_patterns = [
        '/tag/', '/tags/', '/category/', '/categories/', '/author/', '/authors/',
        '/about/', '/contact/', '/privacy/', '/terms/', '/search/', '/feeds/',
        '/login/', '/register/', '/account/', '/profile/', '/rss/', '/feed/',
        '/page/', '/comment/', '/video/', '/videos/', '/gallery/', '/galleries/',
        '/wp-content/', '/wp-includes/', '/assets/', '/css/', '/js/', '/images/',
        '/login', '/register', '/account', '/profile', '/search', '/feed',
        '/sitemap', '/terms-of-service', '/privacy-policy', '/faq', '/help',
        '/subscribe', '/newsletter', '/advertise', '/careers', '/jobs'
    ]

    # Skip URLS without path (like example.com/) or common non-article URL patterns
    path = parsed_url.path.lower()
    if not path or path == '/' or any(pattern in path for pattern in skip_patterns):
        return False

    # Common article URL patterns (adapt based on the sites you're scraping)
    article_patterns = [
        r'/\d{4}/\d{2}/\d{2}/',  # Date patterns: /2023/03/15/
        r'/news/',                # News section
        r'/articles?/',           # Articles section
        r'/story/',               # Story
        r'/post/',                # Post
        r'/blog/',                # Blog post
        r'\.html$',               # HTML extension
        r'/\d+/$',                # Numbered articles
        r'-news$',                # Ends with -news
        r'-story$',               # Ends with -story
        r'-article$',             # Ends with -article
        r'/[a-z0-9-]{10,}$',      # Long slug, likely an article
    ]

    # Check for article patterns
    if any(re.search(pattern, path) for pattern in article_patterns):
        return True

    # If the path has multiple segments and no disqualifying patterns, it might be an article
    segments = [s for s in path.split('/') if s]
    if len(segments) >= 2 and len(segments[-1]) > 5:
        return True

    return False
