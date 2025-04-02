"""
Rate Limiter Utility: Provides rate limiting functionality for web scraping operations.

Exported Classes:
- RateLimiter: Manages rate limiting for requests, with domain-specific controls
  - acquire(domain: str) -> bool: Acquires permission to make a request to a domain
  - release(domain: str) -> None: Releases a previously acquired request slot
  - report_success(domain: str) -> None: Reports a successful request
  - report_error(domain: str) -> None: Reports a failed request, triggering restrictive rate limiting

Related Files:
- main.py: Main orchestration file that uses these utilities
- scraper/scraper_client.py: Main client that would use this rate limiter
- scraper/scraper_hooks/*: Functions that make web requests
"""
import time
import threading
import logging
from collections import defaultdict
from typing import Dict, Set

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter with domain-specific restrictions that activates stricter limits on errors.

    Features:
    - Global request limit (max concurrent requests)
    - Global cooldown between requests
    - Domain-specific cooldown between requests
    - Dynamic rate limiting that becomes more restrictive after errors
    """

    def __init__(self, max_concurrent: int = 10, global_cooldown_ms: int = 500, domain_cooldown_ms: int = 2000):
        """
        Initialize the rate limiter

        Args:
            max_concurrent: Maximum number of concurrent requests
            global_cooldown_ms: Minimum time between any requests in milliseconds
            domain_cooldown_ms: Minimum time between requests to the same domain in milliseconds
        """
        self.max_concurrent = max_concurrent
        self.global_cooldown_ms = global_cooldown_ms
        self.domain_cooldown_ms = domain_cooldown_ms

        # Locks and counters
        self.lock = threading.RLock()
        self.current_requests = 0
        self.last_request_time = 0

        # Domain-specific tracking
        self.domain_last_request: Dict[str, float] = defaultdict(float)
        self.domain_error_count: Dict[str, int] = defaultdict(int)
        self.active_domains: Set[str] = set()

        logger.info(f"Rate limiter initialized: max_concurrent={max_concurrent}, "
                    f"global_cooldown={global_cooldown_ms}ms, domain_cooldown={domain_cooldown_ms}ms")

    def acquire(self, domain: str) -> bool:
        """
        Acquire permission to make a request to a domain

        Args:
            domain: Domain to make a request to

        Returns:
            True if request is allowed, False if it should be delayed
        """
        with self.lock:
            current_time = time.time() * 1000  # Convert to milliseconds

            # Check for global concurrency limit
            if self.current_requests >= self.max_concurrent:
                logger.debug(
                    f"Rate limit: reached max concurrent requests ({self.max_concurrent})")
                return False

            # Check for global cooldown
            time_since_last_request = current_time - self.last_request_time
            if time_since_last_request < self.global_cooldown_ms:
                logger.debug(
                    f"Rate limit: global cooldown ({self.global_cooldown_ms}ms)")
                return False

            # Check for domain-specific cooldown, applying error backoff if needed
            domain_cooldown = self.domain_cooldown_ms
            if domain in self.domain_error_count and self.domain_error_count[domain] > 0:
                # Use a less aggressive backoff formula: 1.5^error_count instead of 2^error_count
                # Cap at 30 seconds instead of 60 seconds (30000ms)
                backoff_factor = min(
                    1.5 ** self.domain_error_count[domain], 30)
                domain_cooldown = self.domain_cooldown_ms * backoff_factor
                logger.debug(f"Rate limit: domain {domain} has error count {self.domain_error_count[domain]}, "
                             f"cooldown increased to {domain_cooldown}ms")

            time_since_domain_request = current_time - \
                self.domain_last_request[domain]
            if time_since_domain_request < domain_cooldown:
                logger.debug(
                    f"Rate limit: domain {domain} cooldown ({domain_cooldown}ms)")
                return False

            # All checks passed, allow the request
            self.current_requests += 1
            self.last_request_time = current_time
            self.domain_last_request[domain] = current_time
            self.active_domains.add(domain)

            if self.domain_error_count[domain] > 0:
                logger.info(f"Rate limit: allowing request to {domain} after error backoff "
                            f"(error count: {self.domain_error_count[domain]})")

            return True

    def release(self, domain: str) -> None:
        """
        Release a previously acquired request slot

        Args:
            domain: Domain that was requested
        """
        with self.lock:
            if self.current_requests > 0:
                self.current_requests -= 1
            if domain in self.active_domains:
                self.active_domains.remove(domain)

    def report_success(self, domain: str) -> None:
        """
        Report a successful request, which may reduce error count

        Args:
            domain: Domain that was successfully requested
        """
        with self.lock:
            # After a successful request, reduce the error count more aggressively
            if domain in self.domain_error_count and self.domain_error_count[domain] > 0:
                # Reduce by 2 instead of 1 to recover faster from errors
                self.domain_error_count[domain] = max(
                    0, self.domain_error_count[domain] - 2)
                logger.debug(
                    f"Rate limit: reduced error count for {domain} to {self.domain_error_count[domain]}")

    def report_error(self, domain: str) -> None:
        """
        Report a failed request, which increases rate limiting for the domain

        Args:
            domain: Domain that failed
        """
        with self.lock:
            # Increment error count, which will increase backoff
            self.domain_error_count[domain] += 1
            logger.info(
                f"Rate limit: increased error count for {domain} to {self.domain_error_count[domain]}")

            # Calculate new backoff time using less aggressive formula
            backoff_factor = min(1.5 ** self.domain_error_count[domain], 30)
            domain_cooldown = self.domain_cooldown_ms * backoff_factor
            logger.info(
                f"Rate limit: domain {domain} cooldown increased to {domain_cooldown}ms ({domain_cooldown/1000:.1f}s)")
