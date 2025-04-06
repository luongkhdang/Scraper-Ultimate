#!/usr/bin/env python3
"""
test_ip_rotation.py - Test Tor IP rotation

This script verifies that your Tor IP rotation is working correctly by:
1. Getting your current Tor IP
2. Attempting to rotate it multiple times with different methods
3. Confirming that the IP has changed

Related files:
- src/scraper/tor/tor_client.py - Main Tor client implementation
"""

import sys
import time
import requests
import subprocess
from typing import Tuple, Optional

# Configure the Tor proxy
TOR_PROXY = {
    'http': 'socks5h://localhost:9050',
    'https': 'socks5h://localhost:9050'
}


def get_tor_ip() -> Optional[str]:
    """Get current IP address through Tor."""
    try:
        # Use a request through the Tor proxy to get our IP
        response = requests.get('https://api.ipify.org?format=json',
                                proxies=TOR_PROXY, timeout=30)
        return response.json()['ip']
    except Exception as e:
        print(f"Error getting Tor IP: {e}")
        return None


def docker_restart_tor() -> bool:
    """Restart the Tor container."""
    try:
        print("Attempting to restart Tor container...")
        subprocess.run(["docker", "restart", "tor"], check=True,
                       capture_output=True, text=True)
        # Wait for Tor to restart and establish circuits
        time.sleep(15)
        return True
    except Exception as e:
        print(f"Error restarting Tor container: {e}")
        return False


def signal_tor_new_identity(password: str = "your_secure_password") -> bool:
    """Signal Tor for a new identity using docker exec."""
    try:
        print("Attempting to signal for new identity via container exec...")
        cmd = f'docker exec tor sh -c \'echo "AUTHENTICATE \\"{password}\\"" > /tmp/tor_cmd && echo "SIGNAL NEWNYM" >> /tmp/tor_cmd && echo "QUIT" >> /tmp/tor_cmd && cat /tmp/tor_cmd | socat - TCP:localhost:9051 && rm /tmp/tor_cmd\''
        result = subprocess.run(
            cmd, shell=True, check=True, capture_output=True, text=True)
        print(f"Result: {result.stdout}")
        time.sleep(5)  # Wait for new circuit
        return True
    except Exception as e:
        print(f"Error signaling for new identity: {e}")
        return False


def sighup_tor_process() -> bool:
    """Send SIGHUP to Tor process inside container."""
    try:
        print("Attempting to send SIGHUP to Tor process...")
        cmd = "docker exec tor sh -c 'pidof tor | xargs kill -HUP'"
        subprocess.run(cmd, shell=True, check=True, capture_output=True)
        time.sleep(5)  # Wait for new circuit
        return True
    except Exception as e:
        print(f"Error sending SIGHUP: {e}")
        return False


def test_ip_rotation():
    """Test Tor IP rotation using multiple methods."""
    # First check if we can connect to Tor
    print("Testing connection to Tor...")
    initial_ip = get_tor_ip()
    if not initial_ip:
        print("ERROR: Cannot connect to Tor. Make sure the Tor service is running.")
        sys.exit(1)

    print(f"Connected to Tor! Initial IP: {initial_ip}")

    # Test IP rotation methods
    methods = [
        ("Docker restart", docker_restart_tor),
        ("NEWNYM signal", signal_tor_new_identity),
        ("SIGHUP signal", sighup_tor_process)
    ]

    for name, method in methods:
        print(f"\nTesting IP rotation method: {name}")

        # Get current IP before rotation
        current_ip = get_tor_ip()
        if not current_ip:
            print("ERROR: Lost connection to Tor. Stopping test.")
            break

        print(f"Current IP before rotation: {current_ip}")

        # Try to rotate IP
        if method():
            # Check if IP changed
            new_ip = get_tor_ip()
            if not new_ip:
                print("ERROR: Lost connection to Tor after rotation attempt.")
                continue

            print(f"IP after rotation attempt: {new_ip}")

            if new_ip != current_ip:
                print(f"SUCCESS! IP changed from {current_ip} to {new_ip}")
            else:
                print(
                    "NOTICE: IP remained the same. This can happen occasionally when Tor selects the same exit node.")
        else:
            print(f"Failed to execute {name} method")

    print("\nIP rotation test complete!")


if __name__ == "__main__":
    test_ip_rotation()
