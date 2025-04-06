"""
Base Extractor Module: Provides the base class for all extractor implementations.

This module contains the BaseExtractor abstract class that defines the interface
for all specialized content extractors to implement.

Exported Classes:
- BaseExtractor: Abstract base class for content extractors

Related Files:
- src/scraper/scraper_hooks/strategies/special_strategy.py: Special strategy extractor implementation
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseExtractor(ABC):
    """
    Abstract base class for content extractors.

    This class defines the interface that all specialized content extractors
    must implement. It provides basic configuration handling and abstract
    methods for extraction operations.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the extractor with configuration.

        Args:
            config: Optional configuration dictionary for the extractor
        """
        self.config = config or {}

    @abstractmethod
    async def extract(self, url: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Extract content from a URL.

        Args:
            url: The URL to extract content from
            config: Optional configuration overrides for this extraction

        Returns:
            Dict containing extraction results with at least 'success' and 'content' keys
        """
        pass

    @abstractmethod
    async def clean_up(self):
        """
        Clean up any resources used by the extractor.

        This method should be called after the extractor is no longer needed
        to release any resources it may be holding.
        """
        pass
