#!/bin/bash
# Setup script for Tor integration with the web scraper

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Tor Integration Setup ===${NC}"
echo -e "This script will help you set up and test the Tor integration for web scraping."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Docker Compose is not installed. Please install Docker Compose first.${NC}"
    exit 1
fi

# Check if docker-compose.yml exists
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}docker-compose.yml not found. Make sure you're in the project root directory.${NC}"
    exit 1
fi

# Generate a secure password
RANDOM_PASSWORD=$(openssl rand -base64 12)

echo -e "${YELLOW}Generating a secure password for Tor control port...${NC}"

# Create backup of docker-compose.yml
cp docker-compose.yml docker-compose.yml.bak
echo -e "${GREEN}Backup created: docker-compose.yml.bak${NC}"

# Update docker-compose.yml with the secure password
sed -i "s/TORPASSWORD: \"your_secure_password\"/TORPASSWORD: \"$RANDOM_PASSWORD\"/g" docker-compose.yml
# Update the command to use the correct format (lowercase -p flag with -n flag for new circuits)
sed -i "s/command: -p \"your_secure_password\"/command: -p \"$RANDOM_PASSWORD\" -n/g" docker-compose.yml
sed -i "s/command: -p \"your_secure_password\" -n/command: -p \"$RANDOM_PASSWORD\" -n/g" docker-compose.yml
sed -i "s/TOR_CONTROL_PASSWORD: \"your_secure_password\"/TOR_CONTROL_PASSWORD: \"$RANDOM_PASSWORD\"/g" docker-compose.yml

echo -e "${GREEN}docker-compose.yml updated with secure password.${NC}"

# Stop any running containers
echo -e "${YELLOW}Stopping any running containers...${NC}"
docker-compose down

# Start the services
echo -e "${YELLOW}Starting services...${NC}"
docker-compose up -d

# Wait for services to be ready
echo -e "${YELLOW}Waiting for services to start (this may take up to 60 seconds for Tor to bootstrap)...${NC}"
sleep 30

# Check if tor service is running
TOR_RUNNING=$(docker-compose ps | grep tor | grep "Up")

if [ -z "$TOR_RUNNING" ]; then
    echo -e "${RED}Tor service is not running. Checking logs...${NC}"
    docker-compose logs tor

    echo -e "${YELLOW}Waiting another 30 seconds for Tor to bootstrap...${NC}"
    sleep 30
    
    TOR_RUNNING=$(docker-compose ps | grep tor | grep "Up")
    if [ -z "$TOR_RUNNING" ]; then
        echo -e "${RED}Tor service still not running. Please check the logs above for errors.${NC}"
        echo -e "${RED}You might need to check your network connection or firewall settings.${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}Tor service is running.${NC}"

# Additional wait for Tor to establish circuits
echo -e "${YELLOW}Waiting for Tor to establish circuits...${NC}"
sleep 20

# Run the test script
echo -e "${YELLOW}Running Tor connection test...${NC}"
docker exec -it scraper python src/test_tor_connection.py

# Check the test result
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Tor integration setup successful!${NC}"
    echo -e "${BLUE}Your Tor control password is: $RANDOM_PASSWORD${NC}"
    echo -e "${BLUE}Keep this password secure, it's needed for IP rotation.${NC}"
else
    echo -e "${RED}Tor connection test failed. Please check the logs for errors.${NC}"
    echo -e "${YELLOW}Try running the setup again or check the documentation in docs/tor_setup.md${NC}"
    echo -e "${YELLOW}You can also try running:${NC}"
    echo -e "${YELLOW}  docker logs tor${NC}"
    echo -e "${YELLOW}to see more details about the Tor service.${NC}"
fi 