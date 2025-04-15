"""
Tor Connection Test Script: Verifies that Tor is properly configured and can access the internet.

This script tests:
1. Whether Tor is running and accessible
2. Whether we can connect through the Tor SOCKS proxy
3. Whether IP rotation works correctly

Usage:
    python src/test_tor.py
"""

import asyncio
import time
import sys
import os
import socket
from scraper.tor.tor_client import (
    is_tor_available,
    is_tor_running,
    rotate_tor_ip,
    get_tor_proxy_url,
    check_tor_connection,
    TOR_HOST,
    DEFAULT_SOCKS_PORT,
    DEFAULT_CONTROL_PORT,
    DEFAULT_CONTROL_PASSWORD,
    IN_DOCKER
)


def check_docker_tor_container():
    """Check if the Tor container is running in Docker environment"""
    if not IN_DOCKER:
        return True

    # First check that we can ping the tor host
    try:
        # Try to resolve the hostname
        tor_ip = socket.gethostbyname(TOR_HOST)
        print(f"✅ Tor container hostname resolved: {TOR_HOST} -> {tor_ip}")
    except socket.gaierror:
        print(f"❌ Could not resolve Tor container hostname: {TOR_HOST}")
        print("   Make sure the Tor container is running and on the same Docker network")
        print("   Try: docker-compose ps")
        return False

    # Try to connect to SOCKS port
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect((TOR_HOST, DEFAULT_SOCKS_PORT))
        s.close()
        print(
            f"✅ Successfully connected to Tor SOCKS port at {TOR_HOST}:{DEFAULT_SOCKS_PORT}")
    except Exception as e:
        print(f"❌ Failed to connect to Tor SOCKS port: {e}")
        print(
            f"   Make sure the Tor container is running and exposing port {DEFAULT_SOCKS_PORT}")
        print("   Try: docker-compose logs tor")
        return False

    # Try to connect to Control port
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect((TOR_HOST, DEFAULT_CONTROL_PORT))
        s.close()
        print(
            f"✅ Successfully connected to Tor Control port at {TOR_HOST}:{DEFAULT_CONTROL_PORT}")
    except Exception as e:
        print(f"❌ Failed to connect to Tor Control port: {e}")
        print(
            f"   Make sure the Tor container is running and exposing port {DEFAULT_CONTROL_PORT}")
        print("   Try: docker-compose logs tor")
        return False

    return True


async def test_special_strategy():
    """Test the special strategy with Tor integration"""
    try:
        from scraper.scraper_hooks.strategies.special_strategy import extract_with_special_strategy

        # Test URL - NYTimes (requires special strategy)
        test_url = "https://www.nytimes.com/2023/01/01/business/economy/economy-markets-2023.html"

        # Execute the strategy
        result = await extract_with_special_strategy(test_url)

        if result and isinstance(result, tuple) and len(result) == 2:
            content, final_url = result
            if content and len(content) > 300:
                print(
                    f"✅ Special strategy successfully extracted content ({len(content)} chars)")
                print(f"✅ Final URL: {final_url}")
                # Print a sample of the content
                print(f"Content sample: {content[:150]}...")
                return True
            else:
                print(
                    f"❌ Special strategy extraction failed or returned short content: {len(content) if content else 0} chars")
                return False
        else:
            print(
                f"❌ Special strategy returned invalid result format: {result}")
            return False
    except Exception as e:
        print(f"❌ Error testing special strategy: {e}")
        return False


def main():
    """Main test function"""
    print(f"Running in Docker: {IN_DOCKER}")
    print(f"Tor Host: {TOR_HOST}")
    print(f"Tor SOCKS Port: {DEFAULT_SOCKS_PORT}")
    print(f"Tor Control Port: {DEFAULT_CONTROL_PORT}")

    # Docker-specific checks
    if IN_DOCKER and not check_docker_tor_container():
        print("\n❌ Docker Tor container check failed")
        print(
            "Please check your Docker configuration and ensure the Tor container is running")
        print("Try: docker-compose restart tor")
        sys.exit(1)

    # Test 1: Check if Tor is enabled
    if is_tor_available():
        print("✅ Tor is enabled in configuration")
    else:
        print("❌ Tor is not enabled in configuration. Set TOR_ENABLED=true")
        print("   In Docker, this should be set in docker-compose.yml")
        print("   Example: TOR_ENABLED: \"true\"")
        sys.exit(1)

    # Test 2: Check if Tor is running
    if is_tor_running():
        print(f"✅ Tor service is running on {TOR_HOST}:{DEFAULT_SOCKS_PORT}")
    else:
        print(
            f"❌ Tor service is not running on {TOR_HOST}:{DEFAULT_SOCKS_PORT}")
        print("   Make sure the Tor service is started in Docker")
        print("   Try: docker-compose restart tor")
        sys.exit(1)

    # Test 3: Check connection through Tor
    tor_working, current_ip = check_tor_connection()
    if tor_working:
        print(f"✅ Successfully connected through Tor with IP: {current_ip}")
    else:
        print("❌ Failed to connect through Tor")
        print("   Check if the Tor service is running properly")
        print("   Try: docker logs tor")
        sys.exit(1)

    # Test 4: Test IP rotation
    original_ip = current_ip
    rotation_success = rotate_tor_ip()

    if rotation_success:
        print(f"✅ IP rotation command completed successfully")
        # Wait for circuit to establish
        time.sleep(7)

        # Check new IP
        tor_working, new_ip = check_tor_connection()
        if tor_working:
            if new_ip != original_ip:
                print(
                    f"✅ IP successfully rotated from {original_ip} to {new_ip}")
            else:
                print(
                    f"⚠️ IP did not change ({new_ip}), but rotation command succeeded")
                print(
                    "   This can happen occasionally with Tor - try running the test again")
        else:
            print("❌ Failed to connect through Tor after rotation")
            print("   The rotation may have broken the Tor circuit")
            print("   Try: docker-compose restart tor")
    else:
        print("❌ IP rotation failed")
        print("   Check if the control port is accessible and the password is correct")
        print("   Try: docker exec -it tor sh -c 'nc -z localhost 9051 && echo \"Control port accessible\"'")

    # Test 5: Test special strategy with the Tor integration
    if asyncio.run(test_special_strategy()):
        print("\n✅ All tests completed successfully!")
    else:
        print("\n⚠️ Special strategy test failed")
        print("   This could be due to site changes or Tor exit node blocking")
        print("   Try again with a different exit node by rotating the IP")


if __name__ == "__main__":
    main()
