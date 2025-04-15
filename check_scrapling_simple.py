# -*- coding: utf-8 -*-
import sys

print("Python version:", sys.version)

try:
    import scrapling
    print("Scrapling imported successfully")
    print(f"Version: {getattr(scrapling, '__version__', 'unknown')}")
except ImportError as e:
    print(f"Failed to import scrapling: {e}")

try:
    import scrapling.fetchers
    print("scrapling.fetchers imported successfully")
    print("Contents:")
    for item in dir(scrapling.fetchers):
        if not item.startswith('__'):
            print(f"  - {item}")
except ImportError as e:
    print(f"Failed to import scrapling.fetchers: {e}")

try:
    from scrapling.fetchers import StealthyFetcher
    print("StealthyFetcher imported successfully")
except ImportError as e:
    print(f"Failed to import StealthyFetcher: {e}")

print("\nChecking sys.path:")
for i, path in enumerate(sys.path):
    print(f"{i}: {path}")
