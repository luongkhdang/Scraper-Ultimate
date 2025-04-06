#!/usr/bin/env python3
"""
tor_ip_check.py - Utility to check Tor connectivity and IP address

This script verifies Tor connectivity by:
1. Checking connection to the Tor SOCKS proxy
2. Verifying the IP is different from the direct connection
3. Monitoring IP rotation when signaling for a new circuit

Related files:
- src/scraper/tor/tor_client.py - Main Tor client integration
- src/test_tor.py - Comprehensive Tor testing script
"""

import argparse
import json
import requests
import socket
import subprocess
import sys
import time
from typing import Dict, Optional, Tuple, List

# ANSI colors for terminal output


class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_colored(text: str, color: str) -> None:
    """Print colored text to terminal."""
    print(f"{color}{text}{Colors.ENDC}")


def get_direct_ip() -> Optional[str]:
    """Get direct IP address without Tor."""
    try:
        response = requests.get(
            'https://api.ipify.org?format=json', timeout=10)
        return response.json()['ip']
    except Exception as e:
        print_colored(f"Error getting direct IP: {e}", Colors.RED)
        return None


def get_tor_ip(proxy_port: int = 9050) -> Optional[str]:
    """Get IP through Tor proxy."""
    try:
        session = requests.session()
        session.proxies = {
            'http': f'socks5h://localhost:{proxy_port}',
            'https': f'socks5h://localhost:{proxy_port}'
        }
        response = session.get('https://api.ipify.org?format=json', timeout=30)
        return response.json()['ip']
    except Exception as e:
        print_colored(f"Error getting Tor IP: {e}", Colors.RED)
        return None


def check_tor_connection(proxy_port: int = 9050) -> bool:
    """Check if Tor connection is working."""
    try:
        session = requests.session()
        session.proxies = {
            'http': f'socks5h://localhost:{proxy_port}',
            'https': f'socks5h://localhost:{proxy_port}'
        }

        # Try to connect to check.torproject.org
        response = session.get('https://check.torproject.org/', timeout=30)
        return 'Congratulations. This browser is configured to use Tor.' in response.text
    except Exception as e:
        print_colored(f"Error checking Tor connection: {e}", Colors.RED)
        return False


def rotate_tor_ip(password: str, control_port: int = 9051) -> bool:
    """Rotate Tor IP address by sending NEWNYM signal."""
    try:
        # Method 1: Try using netcat
        cmd = f'printf \'AUTHENTICATE "{password}"\r\nSIGNAL NEWNYM\r\nQUIT\r\n\' | nc localhost {control_port}'
        result = subprocess.run(
            cmd, shell=True, timeout=10, text=True, capture_output=True)
        if "250 OK" in result.stdout:
            print_colored(
                "Successfully rotated Tor IP using netcat", Colors.GREEN)
            time.sleep(10)  # Wait for circuit rebuild
            return True
    except Exception as e:
        print_colored(f"Failed to rotate IP using netcat: {e}", Colors.YELLOW)

    try:
        # Method 2: Try using HUP signal to Tor container
        result = subprocess.run(["docker", "kill", "--signal", "HUP", "tor"],
                                check=True, capture_output=True, text=True)
        print_colored("Sent HUP signal to Tor container", Colors.GREEN)
        time.sleep(10)  # Wait for circuit rebuild
        return True
    except Exception as e:
        print_colored(f"Failed to rotate IP using HUP signal: {e}", Colors.RED)

    return False


def get_tor_circuit_info(password: str, control_port: int = 9051) -> Optional[str]:
    """Get information about current Tor circuits."""
    try:
        cmd = f'printf \'AUTHENTICATE "{password}"\r\nGETINFO circuit-status\r\nQUIT\r\n\' | nc localhost {control_port}'
        result = subprocess.run(
            cmd, shell=True, timeout=10, text=True, capture_output=True)
        if "250-circuit-status=" in result.stdout:
            return result.stdout
        return None
    except Exception as e:
        print_colored(f"Failed to get circuit info: {e}", Colors.RED)
        return None


def test_multiple_sites(proxy_port: int = 9050) -> Dict[str, bool]:
    """Test connectivity to multiple sites through Tor."""
    test_sites = [
        "https://www.google.com",
        "https://www.bbc.com",
        "https://www.nytimes.com",
        "https://www.theguardian.com",
        "https://www.reuters.com"
    ]

    results = {}
    session = requests.session()
    session.proxies = {
        'http': f'socks5h://localhost:{proxy_port}',
        'https': f'socks5h://localhost:{proxy_port}'
    }

    for site in test_sites:
        try:
            response = session.get(site, timeout=30)
            results[site] = response.status_code == 200
        except Exception:
            results[site] = False

    return results


def analyze_tor_status() -> List[str]:
    """Analyze Tor status from Docker container."""
    issues = []
    try:
        # Check if Tor container is running
        result = subprocess.run(["docker", "ps", "-q", "-f", "name=tor"],
                                capture_output=True, text=True)
        if not result.stdout.strip():
            issues.append("Tor container is not running")

            # Check if it exists but stopped
            result = subprocess.run(["docker", "ps", "-a", "-q", "-f", "name=tor"],
                                    capture_output=True, text=True)
            if result.stdout.strip():
                # Get last exit code
                status = subprocess.run(["docker", "inspect", "-f", "{{.State.ExitCode}}", "tor"],
                                        capture_output=True, text=True)
                issues.append(
                    f"Tor container exists but is stopped (exit code: {status.stdout.strip()})")

        # If running, check logs for common issues
        else:
            logs = subprocess.run(["docker", "logs", "tor"],
                                  capture_output=True, text=True)
            log_output = logs.stdout

            if "404 Not Found" in log_output:
                issues.append(
                    "Tor directory servers may be blocked by your network")

            if "Bootstrapped 0%" in log_output:
                issues.append(
                    "Tor bootstrap is not progressing - network may be blocking Tor")

            if "No route to host" in log_output:
                issues.append(
                    "Network connectivity issues - cannot reach Tor servers")

            bootstrap_percent = None
            for line in log_output.split('\n'):
                if "Bootstrapped" in line:
                    try:
                        bootstrap_percent = int(line.split(
                            "Bootstrapped ")[1].split("%")[0])
                    except:
                        pass

            if bootstrap_percent is not None and bootstrap_percent < 100:
                issues.append(
                    f"Tor bootstrap incomplete: {bootstrap_percent}%")

    except Exception as e:
        issues.append(f"Error analyzing Tor status: {e}")

    return issues


def main():
    parser = argparse.ArgumentParser(
        description='Check Tor connectivity and IP address')
    parser.add_argument('--proxy-port', type=int,
                        default=9050, help='Tor SOCKS proxy port')
    parser.add_argument('--control-port', type=int,
                        default=9051, help='Tor control port')
    parser.add_argument('--password', type=str,
                        default='your_secure_password', help='Tor control password')
    parser.add_argument('--rotate', action='store_true',
                        help='Rotate Tor IP address')
    parser.add_argument('--monitor', action='store_true',
                        help='Monitor IP changes over time')
    parser.add_argument('--detailed', action='store_true',
                        help='Show detailed information')
    args = parser.parse_args()

    print_colored("=" * 60, Colors.BOLD)
    print_colored("TOR CONNECTIVITY CHECK", Colors.BOLD)
    print_colored("=" * 60, Colors.BOLD)

    # Check local connection to Tor
    print_colored(
        "\nChecking local connection to Tor SOCKS proxy...", Colors.BLUE)
    socket_check = False
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect(('localhost', args.proxy_port))
        socket_check = True
        print_colored(
            f"✓ Connection to localhost:{args.proxy_port} successful", Colors.GREEN)
    except Exception as e:
        print_colored(
            f"✗ Cannot connect to Tor SOCKS proxy at localhost:{args.proxy_port}", Colors.RED)
        print_colored(f"  Error: {e}", Colors.RED)
    finally:
        s.close()

    if not socket_check:
        issues = analyze_tor_status()
        if issues:
            print_colored("\nPotential issues detected:", Colors.YELLOW)
            for issue in issues:
                print_colored(f"  • {issue}", Colors.YELLOW)
        sys.exit(1)

    # Compare direct vs Tor IP
    print_colored("\nComparing direct vs Tor IP addresses...", Colors.BLUE)
    direct_ip = get_direct_ip()
    tor_ip = get_tor_ip(args.proxy_port)

    if direct_ip:
        print_colored(f"Direct IP: {direct_ip}", Colors.YELLOW)
    else:
        print_colored("Could not determine direct IP", Colors.RED)

    if tor_ip:
        print_colored(f"Tor IP:    {tor_ip}", Colors.GREEN)
        if direct_ip and direct_ip != tor_ip:
            print_colored(
                "✓ Tor is working correctly - IPs are different", Colors.GREEN)
        elif direct_ip:
            print_colored(
                "✗ Tor may not be working - direct and Tor IPs are the same!", Colors.RED)
    else:
        print_colored(
            "Could not determine Tor IP - connection may be failing", Colors.RED)

    # Check Tor verification site
    is_tor = check_tor_connection(args.proxy_port)
    print_colored("\nChecking Tor verification site...", Colors.BLUE)
    if is_tor:
        print_colored(
            "✓ Tor verification successful at check.torproject.org", Colors.GREEN)
    else:
        print_colored(
            "✗ Tor verification failed at check.torproject.org", Colors.RED)

    # Test multiple sites
    if args.detailed:
        print_colored(
            "\nTesting connectivity to multiple sites through Tor...", Colors.BLUE)
        site_results = test_multiple_sites(args.proxy_port)

        for site, success in site_results.items():
            status = "✓" if success else "✗"
            color = Colors.GREEN if success else Colors.RED
            print_colored(f"{status} {site}", color)

    # IP rotation test
    if args.rotate and tor_ip:
        print_colored("\nAttempting to rotate Tor IP...", Colors.BLUE)
        if rotate_tor_ip(args.password, args.control_port):
            time.sleep(5)  # Give some time for the new circuit to establish
            new_tor_ip = get_tor_ip(args.proxy_port)

            if new_tor_ip:
                print_colored(f"New Tor IP: {new_tor_ip}", Colors.GREEN)
                if tor_ip != new_tor_ip:
                    print_colored(
                        "✓ IP rotation successful - IP address changed", Colors.GREEN)
                else:
                    print_colored(
                        "✗ IP rotation may have failed - IP address did not change", Colors.RED)
                    print_colored(
                        "  This can sometimes happen if Tor chooses the same exit node", Colors.YELLOW)
            else:
                print_colored(
                    "Could not determine new Tor IP after rotation", Colors.RED)

            # Get circuit info if detailed mode
            if args.detailed:
                print_colored("\nTor circuit information:", Colors.BLUE)
                circuit_info = get_tor_circuit_info(
                    args.password, args.control_port)
                if circuit_info:
                    for line in circuit_info.split('\r\n'):
                        if line.startswith('250-circuit-status='):
                            print_colored(line.replace(
                                '250-circuit-status=', ''), Colors.YELLOW)
                else:
                    print_colored(
                        "Could not retrieve circuit information", Colors.RED)

    # Monitor mode
    if args.monitor:
        print_colored(
            "\nEntering IP monitoring mode (Ctrl+C to exit)...", Colors.BLUE)
        print_colored(
            "Will check IP every 30 seconds and after rotation", Colors.BLUE)

        try:
            iteration = 1
            while True:
                print_colored(f"\nIteration {iteration}:", Colors.BOLD)

                # Get current IP
                current_ip = get_tor_ip(args.proxy_port)
                if current_ip:
                    print_colored(
                        f"Current Tor IP: {current_ip}", Colors.GREEN)
                else:
                    print_colored("Could not determine Tor IP", Colors.RED)

                # Rotate IP
                print_colored("Rotating IP...", Colors.YELLOW)
                rotate_success = rotate_tor_ip(
                    args.password, args.control_port)

                if rotate_success:
                    time.sleep(10)  # Wait for new circuit
                    new_ip = get_tor_ip(args.proxy_port)

                    if new_ip:
                        print_colored(f"New Tor IP: {new_ip}", Colors.GREEN)
                        if current_ip != new_ip:
                            print_colored(
                                "✓ IP rotation successful", Colors.GREEN)
                        else:
                            print_colored(
                                "Same IP after rotation (might be using same exit node)", Colors.YELLOW)
                else:
                    print_colored("IP rotation command failed", Colors.RED)

                iteration += 1
                print_colored(
                    "Waiting 30 seconds before next check...", Colors.BLUE)
                time.sleep(30)

        except KeyboardInterrupt:
            print_colored("\nMonitoring stopped by user", Colors.YELLOW)

    print_colored("\nTor connectivity check complete", Colors.BOLD)


if __name__ == "__main__":
    main()
