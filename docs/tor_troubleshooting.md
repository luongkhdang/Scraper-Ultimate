# Tor Troubleshooting Guide

This guide provides solutions for common Tor connectivity issues when using the Scraper-Ultimate project with Docker.

## Quick Start

1. Run the troubleshooting script:

   - On Linux/Mac: `./tor_troubleshoot.sh`
   - On Windows: `.\tor_troubleshoot.ps1`

2. Review the script output for specific issues and recommendations.

3. If you're getting "command not found" errors during IP rotation:
   - On Linux/Mac: Run `./fix_tor_container.sh`
   - On Windows: Run `.\fix_tor_container.ps1`

## Common Issues and Solutions

### Issue: Tor Container Won't Start

#### Symptoms:

- Docker logs show "command not found" errors
- Container exits immediately with code 0 or 13

#### Solutions:

1. Check the `docker-compose.yml` configuration:

   ```yaml
   tor:
     image: dperson/torproxy
     container_name: tor
     environment:
       TOR_PASSWORD: "your_secure_password"
     command: -p "your_secure_password"
     volumes:
       - ./torrc:/etc/tor/torrc:ro
       - tor_data:/var/lib/tor
     ports:
       - "9050:9050"
       - "9051:9051"
     networks:
       - scraper-network
     healthcheck:
       test: ["CMD", "nc", "-z", "localhost", "9050"]
       interval: 30s
       timeout: 10s
       retries: 3
   ```

2. Verify the custom `torrc` file contains valid configuration.

3. Restart with detailed logs:
   ```
   docker-compose down
   docker-compose up tor
   ```

### Issue: IP Rotation Fails with Command Not Found (Exit Status 127)

#### Symptoms:

- Error logs show "returned non-zero exit status 127"
- Messages like "Failed to rotate using HUP signal" or "Failed to rotate using control port"
- All rotation methods fail

#### Solutions:

1. Run the fix script to install missing tools in the container:

   - On Linux/Mac: Run `./fix_tor_container.sh`
   - On Windows: Run `.\fix_tor_container.ps1`

2. Or update your docker-compose.yml to include tool installation:

   ```yaml
   tor:
     image: dperson/torproxy:latest
     container_name: tor
     environment:
       TOR_PASSWORD: "your_secure_password"
     command: >
       -s "apk add --no-cache socat netcat-openbsd procps curl" 
       -p "your_secure_password"
     volumes:
       - ./torrc:/etc/tor/torrc:ro
       - tor_data:/var/lib/tor
     ports:
       - "9050:9050"
       - "9051:9051"
     networks:
       - scraper-network
     healthcheck:
       test: ["CMD", "nc", "-z", "localhost", "9050"]
       interval: 30s
       timeout: 10s
       retries: 3
   ```

3. Restart the container:

   ```
   docker-compose down
   docker-compose up -d
   ```

4. Test IP rotation with the test script:
   ```
   python test_ip_rotation.py
   ```

### Issue: Tor Bootstrap Fails

#### Symptoms:

- Docker logs show "Bootstrapped 0%" or stuck at a low percentage
- Errors like "Failed to find node for hop" or "404 Not Found"

#### Solutions:

1. Network might be blocking Tor. Try using bridges by adding to your torrc:

   ```
   UseBridges 1
   ClientTransportPlugin obfs4 exec /usr/bin/obfs4proxy
   Bridge obfs4 X.X.X.X:YYYY FINGERPRINT
   ```

   (Get actual bridge details from https://bridges.torproject.org/)

2. Try using alternate DNS:

   ```
   DNSPort 0
   ServerDNSResolvConfFile /usr/local/etc/tor/resolv.conf
   ```

   With a custom resolv.conf containing:

   ```
   nameserver 1.1.1.1
   nameserver 8.8.8.8
   ```

3. Increase circuit build timeout in torrc:
   ```
   CircuitBuildTimeout 60
   ```

### Issue: Cannot Rotate IP Address

#### Symptoms:

- `tor_client.py` fails to rotate IP
- Error messages about control port connection

#### Solutions:

1. Verify the Tor control port is accessible:

   ```
   nc -z localhost 9051
   ```

2. Test manual IP rotation:

   ```
   # Using password authentication
   printf 'AUTHENTICATE "your_secure_password"\r\nSIGNAL NEWNYM\r\nQUIT\r\n' | nc localhost 9051
   ```

3. Test using the container restart method (most reliable):

   ```
   docker restart tor
   ```

4. Use the test script to troubleshoot:
   ```
   python test_ip_rotation.py
   ```

### Issue: ISP or Network Blocking Tor

#### Symptoms:

- Bootstrap fails regardless of configuration attempts
- Cannot connect to directory servers

#### Solutions:

1. Use a VPN before connecting to Tor:

   ```yaml
   # Add VPN container to docker-compose.yml
   vpn:
     image: dperson/openvpn-client
     # ... VPN configuration ...
     restart: unless-stopped

   tor:
     # ... Tor configuration ...
     depends_on:
       - vpn
     network_mode: "service:vpn"
   ```

2. Use Snowflake bridges which are harder to block:
   ```
   UseBridges 1
   ClientTransportPlugin snowflake exec /usr/bin/snowflake-client
   Bridge snowflake 2B280B23E1107BB62ABFC40DDCC8824814F80A72
   ```

## Useful Tools

### IP Rotation Testing Script

We've created a script to test all IP rotation methods:

```bash
python test_ip_rotation.py
```

This script will:

1. Check if the Tor connection is working
2. Try multiple rotation methods
3. Verify if the IP changed after each attempt

### Fix Container Script

If you're experiencing "command not found" errors, use:

```bash
# For Linux/Mac
./fix_tor_container.sh

# For Windows
.\fix_tor_container.ps1
```

This script will:

1. Check if the Tor container is running
2. Install the necessary tools (socat, netcat, pidof, curl)
3. Verify if the tools were installed correctly
4. Test the connection to the Tor control port

## Advanced Configuration

### Custom Entry Nodes

If you suspect that certain entry nodes are unreliable, you can specify particular entry nodes:

```
EntryNodes {us},{ca},{gb} StrictNodes 1
```

### Disable Exit Functionality

Since we're only using Tor as a client, ensure we're not acting as an exit node:

```
ExitPolicy reject *:*
ExitRelay 0
```

### Debugging Commands

Check if Tor is running within the container:

```
docker exec tor ps aux | grep tor
```

View Tor logs:

```
docker exec tor cat /var/log/tor/notices.log
```

Get current circuit information:

```
docker exec tor cat /var/lib/tor/data/state
```

## Performance Considerations

- Tor connections are significantly slower than direct connections
- Initial bootstrap can take several minutes
- Circuit build times vary from 10-60 seconds
- IP rotation requires 5-15 seconds to establish new circuits

## Next Steps

If you continue to experience issues after trying these solutions:

1. Check for network-level blocks (corporate firewalls, ISP restrictions)
2. Consider using a cloud-based server with fewer restrictions
3. Explore alternative proxy solutions like residential proxies

For additional support, please open an issue on the project's GitHub repository with detailed logs from the troubleshooting script.
