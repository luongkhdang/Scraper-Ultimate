"""
Scrapling Availability Checker

This utility script checks if the scrapling package is correctly installed and accessible.
It provides detailed diagnostic information about the package installation.

Exports:
    - check_scrapling_availability: Function to verify scrapling installation
    - get_scrapling_info: Function to get detailed information about scrapling

Related files:
    - special_strategy.py: Uses scrapling.fetchers.StealthyFetcher for fallback extraction
"""
import sys
import logging
import importlib
import importlib.util
import os

logger = logging.getLogger(__name__)


def check_scrapling_availability():
    """
    Check if the scrapling package is available and properly installed.

    Returns:
        bool: True if scrapling is available, False otherwise
    """
    scrapling_available = False
    stealthy_fetcher_available = False

    try:
        # Check if scrapling is installed
        scrapling_spec = importlib.util.find_spec("scrapling")
        if scrapling_spec is None:
            logger.error("scrapling package not found in sys.path")
            logger.info("Python paths:")
            for path in sys.path:
                logger.info(f"  - {path}")
            return False

        logger.info(f"scrapling package found at: {scrapling_spec.origin}")
        scrapling_available = True

        # Try to import scrapling
        import scrapling
        version = getattr(scrapling, '__version__', 'unknown')
        logger.info(f"scrapling version: {version}")

        # Try to import the fetchers module
        import scrapling.fetchers
        logger.info("scrapling.fetchers module imported successfully")

        # Check for StealthyFetcher
        dir_fetchers = dir(scrapling.fetchers)
        logger.info(f"Contents of scrapling.fetchers: {dir_fetchers}")

        if 'StealthyFetcher' in dir_fetchers:
            from scrapling.fetchers import StealthyFetcher
            stealthy_fetcher_available = True
            logger.info("StealthyFetcher is available")
        else:
            logger.error(
                "StealthyFetcher class not found in scrapling.fetchers module")

        return stealthy_fetcher_available

    except ImportError as e:
        logger.error(f"Error importing scrapling: {e}")
        return False


def get_scrapling_info():
    """
    Get detailed information about the scrapling package installation.

    Returns:
        dict: Information about scrapling installation
    """
    info = {
        "scrapling_installed": False,
        "version": None,
        "path": None,
        "fetchers_available": False,
        "stealthy_fetcher_available": False,
        "in_docker": os.environ.get('RUNNING_IN_DOCKER', 'false').lower() == 'true',
        "python_version": sys.version,
        "python_path": sys.executable,
        "sys_paths": sys.path,
        "error": None
    }

    try:
        # Check if scrapling is installed
        spec = importlib.util.find_spec("scrapling")
        if spec is None:
            info["error"] = "scrapling package not found in sys.path"
            return info

        info["scrapling_installed"] = True
        info["path"] = spec.origin

        # Try to import scrapling and get version
        import scrapling
        info["version"] = getattr(scrapling, '__version__', 'unknown')

        # Try to import fetchers
        try:
            import scrapling.fetchers
            info["fetchers_available"] = True

            # Check for StealthyFetcher
            if hasattr(scrapling.fetchers, 'StealthyFetcher'):
                info["stealthy_fetcher_available"] = True
        except ImportError as e:
            info["error"] = f"Failed to import scrapling.fetchers: {e}"

    except ImportError as e:
        info["error"] = f"Failed to import scrapling: {e}"

    return info


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    # Check availability
    available = check_scrapling_availability()
    logger.info(f"scrapling availability check result: {available}")

    # Get detailed info
    info = get_scrapling_info()
    for key, value in info.items():
        if key == "sys_paths":
            logger.info(f"{key}:")
            for path in value:
                logger.info(f"  - {path}")
        else:
            logger.info(f"{key}: {value}")
