"""
Domain Manager: Manages tracking and exporting of unique domains encountered during scraping.

Exported Functions:
- add_domain(domains_set: Set[str], url: str) -> None: Adds domain from URL to the domains set
- export_domains(domains_set: Set[str], output_file: str = "unique_domains.json") -> None: Exports domains to JSON file

Related Files:
- scraper_client.py: Main client file that uses these functions
"""
import logging
import json
import os
from urllib.parse import urlparse
from typing import Set, List

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def add_domain(domains_set: Set[str], url: str) -> None:
    """
    Add domain from URL to the domains set

    Args:
        domains_set: Set where domains are stored
        url: URL to extract domain from
    """
    parsed_url = urlparse(url)
    domains_set.add(parsed_url.netloc)


def add_domains_from_urls(domains_set: Set[str], urls: List[str]) -> None:
    """
    Add domains from multiple URLs to the domains set

    Args:
        domains_set: Set where domains are stored
        urls: List of URLs to extract domains from
    """
    for url in urls:
        add_domain(domains_set, url)


def export_domains(domains_set: Set[str], output_file: str = "unique_domains.json") -> None:
    """
    Export the list of unique domains to a JSON file

    Args:
        domains_set: Set of unique domains
        output_file: Path where to save the JSON file
    """
    logger.info(
        f"Exporting {len(domains_set)} unique domains to {output_file}")

    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Convert set to sorted list for better readability
    domain_list = sorted(list(domains_set))

    # Write domains to JSON file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({"unique_domains": domain_list}, f, indent=2)

    logger.info(f"Successfully exported unique domains to {output_file}")
