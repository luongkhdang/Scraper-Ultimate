#!/bin/bash
# Script to install and verify scrapling in Docker container

echo "==============================================="
echo "Installing scrapling in Docker container"
echo "==============================================="

# Function to execute command in the Docker container
docker_exec() {
  docker exec -it $(docker ps -qf "ancestor=scraper-ultimate") "$@"
}

# Check Docker container is running
if [ -z "$(docker ps -qf "ancestor=scraper-ultimate")" ]; then
  echo "Error: No running container with image 'scraper-ultimate'"
  exit 1
fi

# Print Python version information
echo "Python version in container:"
docker_exec python --version

# Uninstall scrapling if it exists (clean install)
echo "Removing any existing scrapling installation..."
docker_exec pip uninstall -y scrapling

# Install scrapling with all dependencies
echo "Installing scrapling package..."
docker_exec pip install scrapling==0.2.99

# Verify the installation
echo "Verifying scrapling installation..."
docker_exec pip list | grep scrapling

# Create a simple test script
echo "Creating test script..."
cat > test_scrapling.py << 'EOF'
# -*- coding: utf-8 -*-
import sys
import importlib.util

print("Python:", sys.version)
print("Python executable:", sys.executable)

try:
    import scrapling
    print("\nscrapling imported successfully!")
    print(f"Version: {getattr(scrapling, '__version__', 'unknown')}")
    
    try:
        import scrapling.fetchers
        print("\nscrapling.fetchers imported successfully!")
        
        # Check for StealthyFetcher
        fetcher_contents = dir(scrapling.fetchers)
        print("\nContents of scrapling.fetchers:")
        for item in fetcher_contents:
            if not item.startswith('__'):
                print(f"  - {item}")
        
        if 'StealthyFetcher' in fetcher_contents:
            print("\nStealthyFetcher is available!")
            from scrapling.fetchers import StealthyFetcher
            print("StealthyFetcher methods:", [m for m in dir(StealthyFetcher) if not m.startswith('__')])
        else:
            print("\nStealthyFetcher is NOT available in scrapling.fetchers")
    except ImportError as e:
        print(f"\nError importing scrapling.fetchers: {e}")
except ImportError as e:
    print(f"\nError importing scrapling: {e}")

# List installed packages
import subprocess
print("\nInstalled packages:")
result = subprocess.run([sys.executable, '-m', 'pip', 'list'], capture_output=True, text=True)
print(result.stdout)
EOF

# Copy test script to container
echo "Copying test script to container..."
docker cp test_scrapling.py $(docker ps -qf "ancestor=scraper-ultimate"):/app/

# Run the test script
echo "Running test script..."
docker_exec python /app/test_scrapling.py

# Clean up
rm test_scrapling.py

echo "==============================================="
echo "Installation and verification complete"
echo "===============================================" 