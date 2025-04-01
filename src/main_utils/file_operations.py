"""
File Operations Utilities: Functions for handling file operations such as reading RSS feeds from a file.

Exported Functions:
- read_rss_feeds_from_file(file_path: str) -> List[str]: Reads RSS feed URLs from a file
- export_failed_domains(failed_domains: Dict[str, Dict], output_file: str) -> bool: Exports failed domains to a JSON file
- export_failed_feeds(failed_feeds: Dict[str, Dict], output_file: str) -> bool: Exports failed RSS feeds to a JSON file

Related Files:
- main.py: Main orchestration file that uses these utilities
- main_hooks/: Contains the core scraping functionality
"""
import os
import json
import logging
from typing import List, Dict, Any

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def read_rss_feeds_from_file(file_path: str) -> List[str]:
    """
    Read RSS feed URLs from a file

    Args:
        file_path: Path to the file containing RSS feed URLs

    Returns:
        List of RSS feed URLs
    """
    try:
        with open(file_path, 'r') as f:
            # Read lines and strip whitespace
            feeds = [line.strip() for line in f.readlines() if line.strip()
                     and not line.strip().startswith('#')]
        logger.info(f"Read {len(feeds)} RSS feeds from {file_path}")
        return feeds
    except Exception as e:
        logger.error(f"Error reading RSS feeds from {file_path}: {e}")
        return []


def export_failed_domains(failed_domains: Dict[str, Dict[str, Any]], output_file: str) -> bool:
    """
    Export failed domains and their error messages to a JSON file

    Args:
        failed_domains: Dictionary with domains as keys and error details as values
        output_file: Path where to save the JSON file

    Returns:
        True if successful, False otherwise
    """
    try:
        # Create directory if it doesn't exist
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Format the data for better readability
        formatted_data = {
            'total_failed_domains': len(failed_domains),
            'export_timestamp': str(logging.Formatter().converter()),
            'domains': failed_domains
        }

        # Write to JSON file with pretty formatting
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(formatted_data, f, indent=2, ensure_ascii=False)

        logger.info(
            f"Exported {len(failed_domains)} failed domains to {output_file}")
        return True
    except Exception as e:
        logger.error(f"Error exporting failed domains to {output_file}: {e}")
        return False


def export_failed_feeds(failed_feeds: Dict[str, Dict[str, Any]], output_file: str) -> bool:
    """
    Export failed RSS feeds and their error details to a JSON file

    Args:
        failed_feeds: Dictionary with RSS feed URLs as keys and error details as values
        output_file: Path where to save the JSON file

    Returns:
        True if successful, False otherwise
    """
    try:
        # Create directory if it doesn't exist
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Format the data for better readability
        formatted_data = {
            'total_failed_feeds': len(failed_feeds),
            'export_timestamp': str(logging.Formatter().converter()),
            'feeds': failed_feeds
        }

        # Write to JSON file with pretty formatting
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(formatted_data, f, indent=2, ensure_ascii=False)

        logger.info(
            f"Exported {len(failed_feeds)} failed RSS feeds to {output_file}")
        return True
    except Exception as e:
        logger.error(f"Error exporting failed RSS feeds to {output_file}: {e}")
        return False
