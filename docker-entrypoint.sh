#!/bin/bash
set -e

echo "==================================================="
echo "Docker entrypoint script for Scraper Ultimate"
echo "==================================================="

# Ensure scrapling is installed
echo "Checking scrapling installation..."
if ! pip list | grep -q scrapling; then
    echo "scrapling not found. Installing..."
    pip install scrapling==0.2.99
else
    echo "scrapling is already installed. Checking version..."
    INSTALLED_VERSION=$(pip list | grep scrapling | awk '{print $2}')
    if [ "$INSTALLED_VERSION" != "0.2.99" ]; then
        echo "Wrong version of scrapling installed ($INSTALLED_VERSION). Installing correct version..."
        pip install scrapling==0.2.99 --force-reinstall
    else
        echo "Correct version of scrapling is installed."
    fi
fi

# Test scrapling import
echo "Testing scrapling import..."
python -c "
import sys
try:
    import scrapling
    from scrapling.fetchers import StealthyFetcher
    print(f'scrapling {scrapling.__version__} successfully imported with StealthyFetcher')
    sys.exit(0)
except ImportError as e:
    print(f'Error importing scrapling: {e}')
    sys.exit(1)
"

# If the import test fails, try to diagnose and fix
if [ $? -ne 0 ]; then
    echo "Import test failed. Running diagnostic..."
    # Try fixing common issues
    echo "Installing missing dependencies..."
    pip install requests beautifulsoup4 lxml tqdm playwright
    
    # Try again
    python -c "import scrapling; from scrapling.fetchers import StealthyFetcher; print('Import successful after fix')" || echo "Still having issues with scrapling import"
fi

# Check all critical dependencies
echo "Checking all critical dependencies..."
python -m src.scraper.scraper_hooks.strategies.check_scrapling

# Execute the main command
echo "Starting main application..."
exec "$@" 