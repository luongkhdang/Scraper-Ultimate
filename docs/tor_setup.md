# Tor Setup Guide

This document explains how to set up and use Tor with the scraper for accessing paywalled or restricted content.

## Docker Setup

The easiest way to use Tor is through our Docker Compose configuration, which automatically sets up a Tor proxy service.

1. Make sure Docker and Docker Compose are installed on your system
2. Open the `docker-compose.yml` file and locate the `tor` service section
3. Ensure the password in the command line matches the `TOR_CONTROL_PASSWORD` environment variable:

```yaml
tor:
  image: dperson/torproxy:latest
  container_name: tor
  ports:
    - "9050:9050" # SOCKS proxy
    - "9051:9051" # Control port for IP rotation
  environment:
    TORPASSWORD: "your_secure_password"
  command: -p "your_secure_password" -n
  # ... additional configuration ...
  cap_add:
    - NET_ADMIN # This helps with proper network connectivity
```

4. Start the services using:

```bash
docker-compose up -d
```

## Tor Bootstrap Process

When starting the Tor container for the first time, it needs to bootstrap a connection to the Tor network. This process can take 30-60 seconds or longer depending on network conditions. During bootstrap, the container will go through several stages:

1. **Connecting to directory servers** - Initial connection to the Tor network
2. **Loading network status** - Downloading information about Tor relays
3. **Loading authority certificates** - Verifying the network is authentic
4. **Building circuits** - Establishing encrypted connections through multiple relays

You can monitor this process by checking the logs:

```bash
docker logs -f tor
```

The Tor container is considered healthy once it has successfully built circuits and can connect to the Tor network.

## Testing the Connection

To verify that Tor is working correctly:

1. Run the test script:

```bash
python src/test_tor_connection.py
```

2. The script should output your Tor IP address and confirm connectivity:

```
Tor connection successful. Current IP: 123.45.67.89
```

## Troubleshooting

If you encounter issues with the Tor connection:

### Common Issues

1. **Tor container not starting or unhealthy**:

   - Check container logs: `docker logs tor`
   - Look for bootstrap messages like "Bootstrapped X%" to see where it's stuck
   - Make sure your network allows outbound connections to ports 80 and 443
   - Ensure no firewall or corporate proxy is blocking Tor connections
   - The `-n` flag in the command forces regeneration of circuits

2. **Configuration errors**:

   - If you see `Unknown option 'PASSWORD'`, you've likely used the wrong environment variable name
   - If you see `Unknown option: -P`, you're using uppercase P instead of lowercase p
   - The dperson/torproxy image requires `-p` (lowercase) for password, not `-P` (uppercase)
   - The correct environment variable name is `TORPASSWORD` (no underscore)

3. **Cannot connect to Tor**:

   - Ensure the Tor container is running: `docker ps | grep tor`
   - Check if the SOCKS port is accessible: `nc -zv localhost 9050`
   - Verify that the control port is accessible: `nc -zv localhost 9051`
   - If the container is running but the test script can't connect, the bootstrap may not be complete

4. **IP rotation not working**:
   - Ensure the control password in your environment matches the one in the docker-compose.yml
   - Check that control port authentication is working correctly
   - Verify the Tor network has enough relays (see logs for warnings about "no exits" or similar)

### Network and Firewall Issues

Tor needs outbound access to the internet to function. If you're behind a restrictive firewall or corporate proxy, you may need to:

1. Configure explicit proxy settings in torrc
2. Use Tor bridges (obfuscated relays) to bypass restrictions
3. Request specific ports to be opened by your network administrator

### Docker-specific Fixes

If Tor can't establish connections, try these Docker-specific fixes:

1. **Add network capabilities** - The `cap_add: [NET_ADMIN]` in docker-compose.yml helps with network access
2. **Adjust DNS settings** - You may need to add custom DNS servers if your network has restricted DNS
3. **Check Docker network** - Ensure the containers can communicate with each other on the shared network
4. **Increase timeouts** - For slow networks, increase the `start_period` in the healthcheck

## Using Tor for Scraping

In your Python code, you can use Tor by configuring it as a proxy:

```python
from scraper.tor.tor_client import get_tor_proxy_url, rotate_tor_ip, check_tor_connection

# Get proxy URL for requests
proxy_url = get_tor_proxy_url()
proxies = {
    'http': proxy_url,
    'https': proxy_url
}

# Use with requests
response = requests.get('https://httpbin.org/ip', proxies=proxies)
print(response.json())  # Shows your Tor IP

# Rotate IP when needed
rotate_tor_ip()
```

For more details, see the `tor_client.py` module documentation.
