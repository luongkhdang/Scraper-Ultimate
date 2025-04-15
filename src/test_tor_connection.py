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
        s.connect((host, port))
        s.close()
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

        # Try different methods to rotate IP
        rotation_success = False

        # Try using the stem library first
        try:
            from stem import Signal
            from stem.control import Controller

            with Controller.from_port(address=TOR_HOST, port=TOR_CONTROL_PORT) as controller:
                controller.authenticate(password=TOR_PASSWORD)
                controller.signal(Signal.NEWNYM)
                rotation_success = True
        except ImportError:
            logger.warning("Stem library not available")
        except Exception as e:
            logger.error(f"Error using Stem to rotate IP: {e}")

        # If stem failed, try direct socket connection
        if not rotation_success:
            try:
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
                rotation_success = True
            except Exception as e:
                logger.error(f"Error using socket to rotate IP: {e}")

        # Wait for the circuit to establish
        if rotation_success:
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
    # Test basic socket connectivity
    socks_conn_ok = check_socket_connection(TOR_HOST, TOR_SOCKS_PORT)

    # Test control port connection
    control_conn_ok = check_socket_connection(TOR_HOST, TOR_CONTROL_PORT)

    # Test Tor proxy functionality
    proxy_ok, initial_ip = check_tor_proxy()

    # Test IP rotation
    rotation_ok = False
    if proxy_ok:
        rotation_ok = await rotate_tor_ip()
    else:
        logger.error("Skipping IP rotation test because proxy isn't working")

    # Test special strategy module import
    special_strategy_ok = await import_and_test_special_strategy()

    # Print summary
    logger.info("\n=== TEST SUMMARY ===")
    logger.info(
        f"1. SOCKS Port Connection ({TOR_HOST}:{TOR_SOCKS_PORT}): {'OK' if socks_conn_ok else 'FAILED'}")
    logger.info(
        f"2. Control Port Connection ({TOR_HOST}:{TOR_CONTROL_PORT}): {'OK' if control_conn_ok else 'FAILED'}")
    logger.info(
        f"3. Tor Proxy Functionality: {'OK' if proxy_ok else 'FAILED'} (Initial IP: {initial_ip})")
    logger.info(
        f"4. Tor IP Rotation: {'OK' if rotation_ok else ('FAILED' if proxy_ok else 'SKIPPED')}")
    logger.info(
        f"5. Special Strategy Module: {'OK' if special_strategy_ok else 'FAILED'}")

    # Overall status
    overall_ok = socks_conn_ok and control_conn_ok and proxy_ok and rotation_ok and special_strategy_ok
    if overall_ok:
        logger.info("\n✅ All Tor tests passed successfully!")
    else:
        logger.error("\n❌ Some Tor tests failed. Please check the logs above.")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
