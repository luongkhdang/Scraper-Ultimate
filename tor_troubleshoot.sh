#!/bin/bash
# Tor connectivity troubleshooting script

# Color formatting
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Tor Connectivity Troubleshooting ===${NC}"

# Check Docker
echo -e "${YELLOW}Checking Docker status...${NC}"
if ! docker ps &> /dev/null; then
    echo -e "${RED}Docker is not running or you don't have permission to use it.${NC}"
    exit 1
else
    echo -e "${GREEN}Docker is running.${NC}"
fi

# Check if tor container exists
echo -e "${YELLOW}Checking Tor container...${NC}"
if ! docker ps -a | grep -q "tor"; then
    echo -e "${RED}Tor container not found. Make sure it's properly defined in docker-compose.yml.${NC}"
    exit 1
fi

# Check if tor container is running
echo -e "${YELLOW}Checking if Tor container is running...${NC}"
if ! docker ps | grep -q "tor"; then
    echo -e "${RED}Tor container is not running.${NC}"
    
    # Check exit status
    echo -e "${YELLOW}Last container exit status:${NC}"
    docker ps -a | grep tor
    
    echo -e "${YELLOW}Starting Tor container logs:${NC}"
    docker logs tor | head -20
    
    echo -e "${YELLOW}Ending Tor container logs:${NC}"
    docker logs tor | tail -20
else
    echo -e "${GREEN}Tor container is running.${NC}"
fi

# Test Tor connectivity inside the container
echo -e "${YELLOW}Testing network connectivity inside Tor container...${NC}"
echo -e "${YELLOW}Testing DNS resolution...${NC}"
docker exec tor nslookup google.com || echo -e "${RED}DNS resolution failed${NC}"

echo -e "${YELLOW}Testing internet connectivity...${NC}"
docker exec tor wget -q --timeout=10 --tries=2 -O- https://check.torproject.org || echo -e "${RED}Internet connectivity test failed${NC}"

# Output Tor bootstrap status
echo -e "${YELLOW}Tor bootstrap status:${NC}"
docker exec tor grep "Bootstrapped" /var/log/tor/notices.log 2>/dev/null || docker logs tor | grep "Bootstrapped"

# Check external connectivity to Tor ports
echo -e "${YELLOW}Checking external connectivity to Tor SOCKS port...${NC}"
nc -z localhost 9050 > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}SOCKS port 9050 is accessible.${NC}"
else
    echo -e "${RED}SOCKS port 9050 is not accessible.${NC}"
fi

echo -e "${YELLOW}Checking external connectivity to Tor Control port...${NC}"
nc -z localhost 9051 > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Control port 9051 is accessible.${NC}"
else
    echo -e "${RED}Control port 9051 is not accessible.${NC}"
fi

# Check if we can get a Tor circuit
echo -e "${YELLOW}Attempting to get a Tor circuit...${NC}"
docker exec tor cat /var/lib/tor/data/state || echo -e "${RED}Could not read Tor state file${NC}"

# Check for network restrictions
echo -e "${YELLOW}Checking for network restrictions...${NC}"
echo -e "Try using Tor bridges if you're on a restricted network."
echo -e "Add the following to torrc and restart the container:"
echo -e "${BLUE}UseBridges 1"
echo -e "ClientTransportPlugin obfs4 exec /usr/bin/obfs4proxy"
echo -e "Bridge obfs4 X.X.X.X:YYYY FINGERPRINT${NC}"
echo -e "(You can get bridges from https://bridges.torproject.org/)"

# Suggestions
echo -e "${GREEN}Suggestions:${NC}"
echo -e "1. Try restarting the Tor container: ${BLUE}docker-compose restart tor${NC}"
echo -e "2. Wait longer for bootstrap (can take several minutes)"
echo -e "3. If you're on a restricted network, try using bridges"
echo -e "4. Check if your ISP or network is blocking Tor"
echo -e "5. Try using a VPN to connect to Tor"

# Provide next steps
echo -e "${YELLOW}Next steps:${NC}"
echo -e "If you're seeing '404 Not Found' errors for directory servers:"
echo -e "- This often means Tor directories are blocked on your network"
echo -e "- Try using bridges (obfs4, snowflake) to bypass restrictions"
echo -e "- Check firewall settings that might block Tor"
echo -e "- Some ISPs actively block Tor connections"

echo -e "${BLUE}=== Troubleshooting Complete ===${NC}" 