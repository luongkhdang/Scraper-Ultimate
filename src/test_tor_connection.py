#!/usr/bin/env python
"""
Tor Connection Test Script

This script tests the connection to the Tor service and verifies that IP rotation is working.
It provides diagnostic information about the Tor configuration and connectivity status.

Usage: python test_tor_connection.py
"""

import os
import sys
import time
import socket
import logging
import asyncio
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path to allow importing modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Check Docker environment
IN_DOCKER = os.environ.get('RUNNING_IN_DOCKER', 'false').lower(
) == 'true' or os.path.exists('/.dockerenv')
logger.info(f"Docker environment detected: {IN_DOCKER}")

# Get Tor configuration from environment variables
TOR_HOST = os.environ.get('TOR_HOST', '127.0.0.1' if not IN_DOCKER else 'tor')
TOR_SOCKS_PORT = int(os.environ.get('TOR_SOCKS_PORT', 9050))
TOR_CONTROL_PORT = int(os.environ.get('TOR_CONTROL_PORT', 9051))
TOR_PASSWORD = os.environ.get('TOR_CONTROL_PASSWORD', os.environ.get(
    'TORPASSWORD', 'your_secure_password'))

logger.info(
    f"Tor configuration: HOST={TOR_HOST}, SOCKS_PORT={TOR_SOCKS_PORT}, CONTROL_PORT={TOR_CONTROL_PORT}")


def check_socket_connection(host, port, timeout=5):
    """Test if a socket connection can be established"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        logger.info(f"Attempting to connect to {host}:{port}")
        s.connect((host, port))
        s.close()
        logger.info(f"Successfully connected to {host}:{port}")
        return True
    except Exception as e:
        logger.error(f"Failed to connect to {host}:{port}: {e}")
        return False


def check_tor_proxy():
    """Test if the Tor proxy is working by making a request through it"""
    try:
        # Configure requests to use Tor proxy
        proxy_url = f'socks5://{TOR_HOST}:{TOR_SOCKS_PORT}'
        proxies = {
            'http': proxy_url,
            'https': proxy_url
        }

        logger.info(f"Testing Tor proxy using {proxy_url}")

        # Make a request to an IP checking service
        response = requests.get('https://httpbin.org/ip',
                                proxies=proxies, timeout=15)

        if response.status_code == 200:
            ip_data = response.json()
            tor_ip = ip_data.get('origin', 'Unknown')
            logger.info(f"Tor connection successful. Current IP: {tor_ip}")

            # Compare with direct connection IP
            try:
                direct_response = requests.get(
                    'https://httpbin.org/ip', timeout=10)
                if direct_response.status_code == 200:
                    direct_ip = direct_response.json().get('origin', 'Unknown')
                    logger.info(f"Direct connection IP: {direct_ip}")

                    if direct_ip != tor_ip:
                        logger.info(
                            "SUCCESS: Tor is working correctly! IPs are different.")
                        return True, tor_ip
                    else:
                        logger.warning(
                            "WARNING: Tor and direct connection have the same IP!")
                        return False, tor_ip
            except Exception as e:
                logger.error(f"Error checking direct IP: {e}")
                # Still return True if we could connect through Tor
                return True, tor_ip
        else:
            logger.error(
                f"Tor connection test failed with status code: {response.status_code}")
            return False, None
    except Exception as e:
        logger.error(f"Error testing Tor proxy: {e}")
        return False, None


async def rotate_tor_ip():
    """Test rotating the Tor IP address"""
    try:
        # First check the current IP
        success, current_ip = check_tor_proxy()
        if not success:
            logger.error("Cannot rotate IP because Tor proxy is not working")
            return False

        logger.info(f"Current Tor IP: {current_ip}")
        logger.info("Attempting to rotate Tor IP...")

        # Try different methods to rotate IP
        rotation_success = False

        # Try using the stem library first
        try:
            logger.info("Trying to rotate using Stem library...")
            from stem import Signal
            from stem.control import Controller

            with Controller.from_port(address=TOR_HOST, port=TOR_CONTROL_PORT) as controller:
                controller.authenticate(password=TOR_PASSWORD)
                controller.signal(Signal.NEWNYM)
                logger.info("Sent NEWNYM signal to Tor controller")
                rotation_success = True
        except ImportError:
            logger.warning("Stem library not available")
        except Exception as e:
            logger.error(f"Error using Stem to rotate IP: {e}")

        # If stem failed, try direct socket connection
        if not rotation_success:
            try:
                logger.info(
                    "Trying to rotate using direct socket connection...")
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(10)
                s.connect((TOR_HOST, TOR_CONTROL_PORT))

                # Read the authentication cookie
                auth_response = s.recv(1024).decode('utf-8').strip()
                logger.debug(f"Tor auth response: {auth_response}")

                # Authenticate with password
                auth_cmd = f'AUTHENTICATE "{TOR_PASSWORD}"\r\n'
                s.sendall(auth_cmd.encode('utf-8'))
                auth_result = s.recv(1024).decode('utf-8').strip()

                if '250 OK' not in auth_result:
                    logger.error(f"Authentication failed: {auth_result}")
                    s.close()
                    return False

                # Send NEWNYM signal to request a new circuit
                s.sendall(b'SIGNAL NEWNYM\r\n')
                newnym_result = s.recv(1024).decode('utf-8').strip()

                if '250 OK' not in newnym_result:
                    logger.error(f"NEWNYM signal failed: {newnym_result}")
                    s.close()
                    return False

                # Close the connection
                s.sendall(b'QUIT\r\n')
                s.close()
                logger.info(
                    "Successfully sent NEWNYM signal using socket connection")
                rotation_success = True
            except Exception as e:
                logger.error(f"Error using socket to rotate IP: {e}")

        # Wait for the circuit to establish
        if rotation_success:
            logger.info("Waiting for new Tor circuit to establish...")
            await asyncio.sleep(5)

            # Check if IP actually changed
            success, new_ip = check_tor_proxy()
            if success:
                if new_ip != current_ip:
                    logger.info(
                        f"SUCCESS: IP rotated from {current_ip} to {new_ip}")
                    return True
                else:
                    logger.warning(
                        f"IP rotation may not have worked: IP is still {new_ip}")
                    # Sometimes Tor reuses the same exit node, so this isn't necessarily an error
                    return True
            else:
                logger.error("Failed to verify new IP after rotation")
                return False

        return rotation_success
    except Exception as e:
        logger.error(f"Error during IP rotation: {e}")
        return False


async def import_and_test_special_strategy():
    """Test importing and using the special_strategy module"""
    try:
        logger.info("Testing special_strategy module import...")

        # Import the module
        from scraper.scraper_hooks.strategies.special_strategy import SpecialStrategyExtractor
        logger.info("Successfully imported SpecialStrategyExtractor")

        # Initialize the extractor
        extractor = SpecialStrategyExtractor()
        logger.info(
            f"Initialized SpecialStrategyExtractor with Tor available: {extractor.tor_available}")

        # Additional test: Try importing tor_integration
        try:
            from scraper.scraper_hooks.strategies import tor_integration
            logger.info("Successfully imported tor_integration module")

            # Check Tor availability
            available = tor_integration.is_available()
            logger.info(f"Tor integration available: {available}")

            # Check if Tor is ready
            ready = tor_integration.is_ready()
            logger.info(f"Tor integration ready: {ready}")

            return True
        except ImportError as e:
            logger.error(f"Failed to import tor_integration: {e}")
            return False
    except ImportError as e:
        logger.error(f"Failed to import SpecialStrategyExtractor: {e}")
        return False
    except Exception as e:
        logger.error(f"Error testing special_strategy: {e}")
        return False


async def run_all_tests():
    """Run all Tor tests"""
    logger.info("=== STARTING TOR CONNECTION TESTS ===")

    # Test 1: Basic socket connection to Tor SOCKS port
    logger.info("\n=== Test 1: Basic socket connection to Tor SOCKS port ===")
    socks_connected = check_socket_connection(TOR_HOST, TOR_SOCKS_PORT)

    # Test 2: Basic socket connection to Tor Control port
    logger.info("\n=== Test 2: Basic socket connection to Tor Control port ===")
    control_connected = check_socket_connection(TOR_HOST, TOR_CONTROL_PORT)

    # Test 3: Tor proxy functionality
    logger.info("\n=== Test 3: Tor proxy functionality ===")
    proxy_working, tor_ip = check_tor_proxy()

    # Test 4: Tor IP rotation
    logger.info("\n=== Test 4: Tor IP rotation ===")
    if proxy_working:
        rotation_working = await rotate_tor_ip()
    else:
        logger.error("Skipping IP rotation test because proxy isn't working")
        rotation_working = False

    # Test 5: Special strategy module
    logger.info("\n=== Test 5: Special strategy module ===")
    strategy_working = await import_and_test_special_strategy()

    # Print summary
    logger.info("\n=== TEST SUMMARY ===")
    logger.info(
        f"Socket connection to Tor SOCKS port: {'SUCCESS' if socks_connected else 'FAILED'}")
    logger.info(
        f"Socket connection to Tor Control port: {'SUCCESS' if control_connected else 'FAILED'}")
    logger.info(
        f"Tor proxy functionality: {'SUCCESS' if proxy_working else 'FAILED'}")
    logger.info(
        f"Tor IP rotation: {'SUCCESS' if rotation_working else 'FAILED'}")
    logger.info(
        f"Special strategy module: {'SUCCESS' if strategy_working else 'FAILED'}")

    # Overall result
    if socks_connected and proxy_working and strategy_working:
        logger.info(
            "\n✅ OVERALL: Tor is configured correctly for special_strategy")
    else:
        logger.error(
            "\n❌ OVERALL: Tor is NOT configured correctly. See logs for details.")

if __name__ == "__main__":
    # Run all the tests
    asyncio.run(run_all_tests())
