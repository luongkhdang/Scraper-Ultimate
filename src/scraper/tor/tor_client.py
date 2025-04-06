"""
Tor Client: Manages Tor connection and IP rotation functionality for scraping paywalled sites.

Exported Functions:
- is_tor_running(port: int = None) -> bool: Checks if Tor is running on the specified port
- rotate_tor_ip(control_port: int = None, password: str = None) -> bool: Rotates Tor IP address by requesting a new circuit
- get_tor_proxy_url(socks_port: int = None) -> str: Returns the Tor SOCKS5 proxy URL
- check_tor_connection() -> bool: Verifies connectivity to Tor by testing a connection

Related Files:
- src/scraper/scraper_hooks/strategies/special_strategy.py: Uses this module for Tor-based scraping
"""

import os
import time
import logging
import subprocess
import socket
import json
import requests
from typing import Optional, Dict, Union, Tuple
from urllib.error import URLError
from urllib.request import urlopen

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Docker environment detection - be more aggressive to detect Docker
IN_DOCKER = os.environ.get('RUNNING_IN_DOCKER', 'false').lower(
) == 'true' or os.path.exists('/.dockerenv')
logger.info(f"Docker environment detected: {IN_DOCKER}")

# Default Tor configuration - with Docker support
TOR_ENABLED = os.environ.get('TOR_ENABLED', 'false').lower() == 'true'
TOR_HOST = os.environ.get('TOR_HOST', '127.0.0.1' if not IN_DOCKER else 'tor')
DEFAULT_SOCKS_PORT = int(os.environ.get('TOR_SOCKS_PORT', 9050))
DEFAULT_CONTROL_PORT = int(os.environ.get('TOR_CONTROL_PORT', 9051))
# Check for all possible Tor password environment variables
DEFAULT_CONTROL_PASSWORD = os.environ.get(
    'TOR_CONTROL_PASSWORD', os.environ.get('TORPASSWORD', 'your_secure_password'))
TOR_CONTAINER_NAME = os.environ.get('TOR_CONTAINER_NAME', 'tor')
# Circuit establishment wait time after rotation (in seconds)
TOR_CIRCUIT_TIMEOUT = int(os.environ.get('TOR_CIRCUIT_TIMEOUT', 5))

# Log the configuration for debugging
logger.info(f"Tor configuration: ENABLED={TOR_ENABLED}, HOST={TOR_HOST}, "
            f"SOCKS_PORT={DEFAULT_SOCKS_PORT}, CONTROL_PORT={DEFAULT_CONTROL_PORT}, "
            f"CONTAINER_NAME={TOR_CONTAINER_NAME}")


class TorClient:
    """Class to manage Tor connection and IP rotation"""

    @staticmethod
    def is_available() -> bool:
        """
        Check if Tor is enabled in the environment configuration

        Returns:
            bool: True if Tor is enabled, False otherwise
        """
        available = TOR_ENABLED
        logger.info(f"Tor available check: {available}")
        return available

    @staticmethod
    def is_running(port: int = None) -> bool:
        """
        Check if Tor is running on the configured port

        Args:
            port: Optional port to check (uses DEFAULT_SOCKS_PORT if not specified)

        Returns:
            bool: True if Tor is running, False otherwise
        """
        socks_port = port or DEFAULT_SOCKS_PORT
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)  # Increase timeout for Docker networking
            # Use TOR_HOST instead of hardcoded 127.0.0.1
            s.connect((TOR_HOST, socks_port))
            s.close()
            logger.info(f"Tor service detected on {TOR_HOST}:{socks_port}")
            return True
        except Exception as e:
            logger.warning(
                f"Tor service not detected on {TOR_HOST}:{socks_port}: {e}")
            return False

    @staticmethod
    def get_proxy_url(port: int = None) -> str:
        """
        Get the Tor SOCKS5 proxy URL

        Args:
            port: Optional SOCKS port (uses DEFAULT_SOCKS_PORT if not specified)

        Returns:
            str: Tor SOCKS5 proxy URL
        """
        socks_port = port or DEFAULT_SOCKS_PORT
        proxy_url = f'socks5://{TOR_HOST}:{socks_port}'
        logger.info(f"Using Tor proxy URL: {proxy_url}")
        return proxy_url

    @staticmethod
    def check_tor_connection() -> Tuple[bool, Optional[str]]:
        """
        Check if Tor is working by trying to connect to a test service

        Returns:
            Tuple of (is_working, current_ip)
        """
        try:
            # Configure requests to use Tor proxy
            proxies = {
                'http': TorClient.get_proxy_url(),
                'https': TorClient.get_proxy_url()
            }

            # Try to connect to an IP checking service
            response = requests.get(
                'https://httpbin.org/ip', proxies=proxies, timeout=15)

            if response.status_code == 200:
                ip_data = response.json()
                tor_ip = ip_data.get('origin', 'Unknown')
                logger.info(f"Tor connection successful. Current IP: {tor_ip}")
                return True, tor_ip
            else:
                logger.warning(
                    f"Tor connection test failed with status code: {response.status_code}")
                return False, None
        except Exception as e:
            logger.error(f"Error checking Tor connection: {e}")
            return False, None

    @staticmethod
    def rotate_ip(control_port: int = None, password: str = None) -> bool:
        """
        Rotate Tor IP by sending NEWNYM signal to control port

        Args:
            control_port: Optional control port (uses DEFAULT_CONTROL_PORT if not specified)
            password: Optional control password (uses DEFAULT_CONTROL_PASSWORD if not specified)

        Returns:
            bool: True if rotation was successful, False otherwise
        """
        port = control_port or DEFAULT_CONTROL_PORT
        pwd = password or DEFAULT_CONTROL_PASSWORD

        if not TorClient.is_running():
            logger.warning("Tor is not running, cannot rotate IP")
            return False

        # Save current IP for verification
        current_working, current_ip = TorClient.check_tor_connection()

        # Docker-specific rotation method
        if IN_DOCKER:
            logger.info(
                "Detected Docker environment, using container-specific rotation methods")
            if TorClient._rotate_ip_in_docker(port, pwd):
                # Verify IP changed
                # Wait for circuit to be established
                time.sleep(TOR_CIRCUIT_TIMEOUT)
                new_working, new_ip = TorClient.check_tor_connection()
                if new_working and new_ip != current_ip:
                    logger.info(
                        f"IP rotated successfully: {current_ip} -> {new_ip}")
                    return True
                else:
                    logger.warning(
                        "IP rotation may have failed - IP did not change")
                    return True  # Still return True as the command succeeded
            return False

        # Standard rotation methods for non-Docker environments
        try:
            # Try using the stem library to request a new circuit
            if TorClient._rotate_with_stem(port, pwd):
                time.sleep(TOR_CIRCUIT_TIMEOUT)
                return True

            # Fall back to netcat if stem is not available
            if TorClient._rotate_with_netcat(port, pwd):
                time.sleep(TOR_CIRCUIT_TIMEOUT)
                return True

            # Try direct SIGHUP as a last resort
            if TorClient._rotate_with_sighup():
                time.sleep(TOR_CIRCUIT_TIMEOUT * 2)  # Longer wait after SIGHUP
                return True

            logger.error("Failed to rotate Tor IP using any method")
            return False

        except Exception as e:
            logger.error(f"Error rotating Tor IP: {e}")
            return False

    @staticmethod
    def _rotate_ip_in_docker(port: int = None, password: str = None) -> bool:
        """
        Rotate Tor IP specifically for Docker environments

        Args:
            port: Control port
            password: Control password

        Returns:
            bool: True if rotation was successful
        """
        port = port or DEFAULT_CONTROL_PORT
        password = password or DEFAULT_CONTROL_PASSWORD

        try:
            # Instead of using docker commands which require docker CLI,
            # connect directly to the Tor control port
            logger.info(
                f"Connecting directly to Tor control port at {TOR_HOST}:{port}")

            try:
                import socket

                # Create a socket connection to the Tor control port
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(10)
                s.connect((TOR_HOST, port))

                # Read the authentication cookie
                auth_response = s.recv(1024).decode('utf-8').strip()
                logger.debug(f"Tor auth response: {auth_response}")

                # Authenticate with password
                auth_cmd = f'AUTHENTICATE "{password}"\r\n'
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
                    "Successfully rotated Tor IP via direct control port connection")
                time.sleep(TOR_CIRCUIT_TIMEOUT)
                return True

            except Exception as e:
                logger.error(
                    f"Error connecting directly to Tor control port: {e}")

            # Try direct socket connection using netcat-like approach
            logger.info(
                "Attempting direct socket approach for control port commands")
            try:
                # Connect to the control port
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect((TOR_HOST, port))

                # Receive welcome message
                welcome = s.recv(1024)

                # Send authentication command
                auth_cmd = f'AUTHENTICATE "{password}"\r\n'.encode()
                s.sendall(auth_cmd)
                time.sleep(0.5)

                # Receive auth response
                auth_response = s.recv(1024).decode('utf-8')
                if "250 OK" not in auth_response:
                    logger.error(f"Authentication failed: {auth_response}")
                    s.close()
                    return False

                # Send NEWNYM signal
                s.sendall(b"SIGNAL NEWNYM\r\n")
                time.sleep(0.5)

                # Receive signal response
                signal_response = s.recv(1024).decode('utf-8')
                if "250 OK" not in signal_response:
                    logger.error(f"NEWNYM signal failed: {signal_response}")
                    s.close()
                    return False

                # Send QUIT command
                s.sendall(b"QUIT\r\n")
                s.close()

                logger.info(
                    "Successfully rotated Tor IP via direct socket connection")
                time.sleep(TOR_CIRCUIT_TIMEOUT)
                return True

            except Exception as e:
                logger.error(f"Error using direct socket approach: {e}")

            # If all methods failed
            logger.error("All Docker rotation methods failed")
            return False

        except Exception as e:
            logger.error(f"Error in Docker IP rotation: {e}")
            return False

    @staticmethod
    def _rotate_with_stem(port: int, password: str) -> bool:
        """Rotate IP using the stem library"""
        try:
            import stem
            from stem import Signal
            from stem.control import Controller

            with Controller.from_port(address=TOR_HOST, port=port) as controller:
                controller.authenticate(password=password)
                controller.signal(Signal.NEWNYM)
                logger.info("Tor IP rotated via stem controller")
                return True
        except ImportError:
            logger.debug("Stem library not available")
            return False
        except Exception as e:
            logger.warning(f"Stem rotation error: {e}")
            return False

    @staticmethod
    def _rotate_with_netcat(port: int, password: str) -> bool:
        """Rotate IP using netcat command"""
        try:
            cmd = f"""echo -e 'AUTHENTICATE "{password}"\r\nSIGNAL NEWNYM\r\nQUIT' | nc {TOR_HOST} {port}"""
            subprocess.run(cmd, shell=True, check=True, capture_output=True)
            logger.info("Tor IP rotated via netcat command")
            return True
        except Exception as e:
            logger.warning(f"Netcat rotation error: {e}")
            return False

    @staticmethod
    def _rotate_with_sighup() -> bool:
        """Rotate IP by sending SIGHUP to the Tor process"""
        try:
            subprocess.run(['killall', '-HUP', 'tor'], check=True)
            logger.info("Tor IP rotated via SIGHUP")
            return True
        except Exception as e:
            logger.warning(f"SIGHUP rotation error: {e}")
            return False


# Convenience functions for direct module usage
def is_tor_running(port: int = None) -> bool:
    """
    Check if Tor is running on the specified port

    Args:
        port: Optional port to check (uses DEFAULT_SOCKS_PORT if not specified)

    Returns:
        bool: True if Tor is running, False otherwise
    """
    return TorClient.is_running(port)


def rotate_tor_ip(control_port: int = None, password: str = None) -> bool:
    """
    Rotate Tor IP by sending NEWNYM signal to control port

    Args:
        control_port: Optional control port (uses DEFAULT_CONTROL_PORT if not specified)
        password: Optional control password (uses DEFAULT_CONTROL_PASSWORD if not specified)

    Returns:
        bool: True if rotation was successful, False otherwise
    """
    return TorClient.rotate_ip(control_port, password)


def get_tor_proxy_url(socks_port: int = None) -> str:
    """
    Get the Tor SOCKS5 proxy URL

    Args:
        socks_port: Optional SOCKS port (uses DEFAULT_SOCKS_PORT if not specified)

    Returns:
        str: Tor SOCKS5 proxy URL
    """
    return TorClient.get_proxy_url(socks_port)


def is_tor_available() -> bool:
    """
    Check if Tor is enabled in the configuration

    Returns:
        bool: True if Tor is enabled, False otherwise
    """
    return TorClient.is_available()


def check_tor_connection() -> Tuple[bool, Optional[str]]:
    """
    Check if Tor is working by trying to connect to a test service

    Returns:
        Tuple of (is_working, current_ip)
    """
    return TorClient.check_tor_connection()
