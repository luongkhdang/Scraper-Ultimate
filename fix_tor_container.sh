#!/bin/bash
# fix_tor_container.sh - Install required tools in an existing Tor container

# Color formatting
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Tor Container Fix Script ===${NC}"

# Check if Docker is running
echo -e "${YELLOW}Checking Docker status...${NC}"
if ! docker ps &> /dev/null; then
    echo -e "${RED}Docker is not running or you don't have permission to use it.${NC}"
    exit 1
else
    echo -e "${GREEN}Docker is running.${NC}"
fi

# Check if tor container exists and is running
echo -e "${YELLOW}Checking Tor container...${NC}"
if ! docker ps | grep -q "tor"; then
    echo -e "${RED}Tor container is not running.${NC}"
    
    # Check if it exists but stopped
    if docker ps -a | grep -q "tor"; then
        echo -e "${YELLOW}Tor container exists but is not running. Starting container...${NC}"
        docker start tor
        sleep 5
    else
        echo -e "${RED}Tor container does not exist. Please run setup_tor.sh first.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}Tor container is running.${NC}"
fi

# Install required tools inside the container
echo -e "${YELLOW}Installing required tools inside the Tor container...${NC}"
echo -e "${YELLOW}This may take a moment...${NC}"

# Try to install tools with apk (Alpine Linux)
if docker exec tor apk --help &> /dev/null; then
    echo -e "${YELLOW}Container appears to be based on Alpine Linux, using apk...${NC}"
    docker exec tor apk add --no-cache socat netcat-openbsd procps curl
    RESULT=$?
    if [ $RESULT -eq 0 ]; then
        echo -e "${GREEN}Successfully installed tools using apk.${NC}"
    else
        echo -e "${RED}Failed to install tools using apk (exit code: $RESULT).${NC}"
    fi
# Try to install tools with apt-get (Debian/Ubuntu)
elif docker exec tor apt-get --help &> /dev/null; then
    echo -e "${YELLOW}Container appears to be based on Debian/Ubuntu, using apt-get...${NC}"
    docker exec tor apt-get update
    docker exec tor apt-get install -y socat netcat procps curl
    RESULT=$?
    if [ $RESULT -eq 0 ]; then
        echo -e "${GREEN}Successfully installed tools using apt-get.${NC}"
    else
        echo -e "${RED}Failed to install tools using apt-get (exit code: $RESULT).${NC}"
    fi
else
    echo -e "${RED}Could not determine package manager. Trying direct download...${NC}"
    # Try to download a static binary of socat as last resort
    docker exec tor sh -c "mkdir -p /tmp/tools && cd /tmp/tools && curl -L -o socat.tar.gz https://github.com/andrew-d/static-binaries/raw/master/binaries/linux/x86_64/socat && tar xzf socat.tar.gz && chmod +x socat && mv socat /usr/local/bin/"
    RESULT=$?
    if [ $RESULT -eq 0 ]; then
        echo -e "${GREEN}Successfully installed socat from static binary.${NC}"
    else
        echo -e "${RED}Failed to install tools using direct download.${NC}"
        echo -e "${RED}You may need to rebuild the container using the updated docker-compose.yml.${NC}"
    fi
fi

# Verify tool installation
echo -e "${YELLOW}Verifying tool installation...${NC}"
MISSING_TOOLS=0

# Check for socat
if ! docker exec tor which socat &> /dev/null; then
    echo -e "${RED}socat is missing${NC}"
    MISSING_TOOLS=$((MISSING_TOOLS+1))
else
    echo -e "${GREEN}socat is installed${NC}"
fi

# Check for netcat (nc)
if ! docker exec tor which nc &> /dev/null; then
    echo -e "${RED}netcat (nc) is missing${NC}"
    MISSING_TOOLS=$((MISSING_TOOLS+1))
else
    echo -e "${GREEN}netcat (nc) is installed${NC}"
fi

# Check for pidof
if ! docker exec tor which pidof &> /dev/null; then
    echo -e "${RED}pidof is missing${NC}"
    MISSING_TOOLS=$((MISSING_TOOLS+1))
else
    echo -e "${GREEN}pidof is installed${NC}"
fi

# Check for curl
if ! docker exec tor which curl &> /dev/null; then
    echo -e "${RED}curl is missing${NC}"
    MISSING_TOOLS=$((MISSING_TOOLS+1))
else
    echo -e "${GREEN}curl is installed${NC}"
fi

# Final status
if [ $MISSING_TOOLS -eq 0 ]; then
    echo -e "${GREEN}All required tools are installed!${NC}"
    echo -e "${YELLOW}Testing Tor control port connection...${NC}"
    
    # Try to send a simple command to the control port
    docker exec tor sh -c 'echo "AUTHENTICATE \"your_secure_password\"\r\nGETINFO version\r\nQUIT" | socat - TCP:localhost:9051'
    RESULT=$?
    if [ $RESULT -eq 0 ]; then
        echo -e "${GREEN}Successfully connected to Tor control port.${NC}"
        echo -e "${GREEN}Your Tor container should now be ready for IP rotation.${NC}"
    else
        echo -e "${RED}Failed to connect to Tor control port (exit code: $RESULT).${NC}"
        echo -e "${YELLOW}Check your password in docker-compose.yml and make sure it matches TOR_PASSWORD in your environment.${NC}"
    fi
else
    echo -e "${RED}Some tools are still missing. You may need to rebuild the container.${NC}"
    echo -e "${YELLOW}To rebuild:${NC}"
    echo -e "1. Stop the current container: ${BLUE}docker stop tor${NC}"
    echo -e "2. Remove it: ${BLUE}docker rm tor${NC}"
    echo -e "3. Make sure your docker-compose.yml has the updated command with tool installation"
    echo -e "4. Run: ${BLUE}docker-compose up -d${NC}"
fi

echo -e "${BLUE}=== Fix Complete ===${NC}" 