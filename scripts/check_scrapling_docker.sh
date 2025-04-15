#!/bin/bash

# Script to check scrapling availability in Docker container

# Print header
echo "==========================================="
echo "Checking scrapling availability in container"
echo "==========================================="

# Run the diagnostic script in the container
docker exec -it $(docker ps -qf "ancestor=scraper-ultimate") python -m src.scraper.scraper_hooks.strategies.check_scrapling

# Check pip list for scrapling
echo ""
echo "==========================================="
echo "Checking pip list for scrapling package"
echo "==========================================="
docker exec -it $(docker ps -qf "ancestor=scraper-ultimate") pip list | grep scrapling

# Try to install scrapling directly in the container
echo ""
echo "==========================================="
echo "Attempting to reinstall scrapling package"
echo "==========================================="
docker exec -it $(docker ps -qf "ancestor=scraper-ultimate") pip install scrapling==0.2.99

# Run diagnostic again to see if fixed
echo ""
echo "==========================================="
echo "Running diagnostic check again after reinstall"
echo "==========================================="
docker exec -it $(docker ps -qf "ancestor=scraper-ultimate") python -m src.scraper.scraper_hooks.strategies.check_scrapling 