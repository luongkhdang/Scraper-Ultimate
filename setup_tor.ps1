# setup_tor.ps1 - PowerShell script to setup Tor in Docker environment

# Color functions for better output
function Write-ColorOutput($ForegroundColor) {
    # Store current colors
    $fc = $host.UI.RawUI.ForegroundColor

    # Set colors
    $host.UI.RawUI.ForegroundColor = $ForegroundColor

    # Restore colors (using trap to ensure they're restored even if the script fails)
    trap { 
        $host.UI.RawUI.ForegroundColor = $fc
        break
    }
    
    # Return the output
    return
}

function Write-Green($str) {
    Write-ColorOutput Green
    Write-Output $str
    $host.UI.RawUI.ForegroundColor = $fc
}

function Write-Yellow($str) {
    Write-ColorOutput Yellow
    Write-Output $str
    $host.UI.RawUI.ForegroundColor = $fc
}

function Write-Red($str) {
    Write-ColorOutput Red
    Write-Output $str
    $host.UI.RawUI.ForegroundColor = $fc
}

function Write-Cyan($str) {
    Write-ColorOutput Cyan
    Write-Output $str
    $host.UI.RawUI.ForegroundColor = $fc
}

# Display header
Write-Cyan "======================================================"
Write-Cyan "  Tor Setup Script for Scraper-Ultimate (Windows)     "
Write-Cyan "======================================================"
Write-Output ""

# Check for Docker
Write-Yellow "Checking for Docker..."
try {
    $dockerCheck = docker --version
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed"
    }
    Write-Green "Docker is installed: $dockerCheck"
} catch {
    Write-Red "Error: Docker is not installed or not in PATH"
    Write-Red "Please install Docker Desktop for Windows and try again"
    exit 1
}

# Check for Docker Compose
Write-Yellow "Checking for Docker Compose..."
try {
    $composeCheck = docker-compose --version
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose command failed"
    }
    Write-Green "Docker Compose is installed: $composeCheck"
} catch {
    Write-Red "Error: Docker Compose is not installed or not in PATH"
    Write-Red "Please install Docker Compose and try again"
    exit 1
}

# Check for docker-compose.yml
Write-Yellow "Checking for docker-compose.yml..."
if (-not (Test-Path -Path "docker-compose.yml")) {
    Write-Red "Error: docker-compose.yml not found in the current directory"
    Write-Red "Please run this script from the root of the Scraper-Ultimate project"
    exit 1
}
Write-Green "docker-compose.yml found"

# Generate a secure password
Write-Yellow "Generating a secure password for Tor control port..."
try {
    # Using .NET's random number generator for a secure password
    $randomBytes = New-Object byte[] 12
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($randomBytes)
    $securePassword = [Convert]::ToBase64String($randomBytes)
    Write-Green "Password generated: $securePassword"
} catch {
    Write-Red "Error generating secure password: $_"
    Write-Yellow "Using fallback password: your_secure_password"
    $securePassword = "your_secure_password"
}

# Backup docker-compose.yml
Write-Yellow "Creating backup of docker-compose.yml..."
try {
    Copy-Item -Path "docker-compose.yml" -Destination "docker-compose.yml.bak" -Force
    Write-Green "Backup created: docker-compose.yml.bak"
} catch {
    Write-Red "Error creating backup: $_"
    Write-Red "Proceeding without backup"
}

# Update docker-compose.yml file with the secure password
Write-Yellow "Updating docker-compose.yml with new Tor password..."
try {
    $composeFile = Get-Content -Path "docker-compose.yml" -Raw
    
    # Look for the Tor service
    if ($composeFile -match "tor:") {
        # Replace the password in TOR_PASSWORD environment variable
        $composeFile = $composeFile -replace '(TOR_PASSWORD: )"([^"]*)"', "`$1""$securePassword"""
        
        # Replace the password in command
        $composeFile = $composeFile -replace '(command: .* -p )"([^"]*)"', "`$1""$securePassword"""
        
        # Save the file
        $composeFile | Set-Content -Path "docker-compose.yml" -NoNewline
        Write-Green "docker-compose.yml updated with new password"
    } else {
        Write-Yellow "No Tor service found in docker-compose.yml"
        Write-Yellow "Checking if we need to add it..."
        
        # Check if we need to add the Tor service (this is simplified - might need adjustment)
        $torService = @"

  tor:
    image: dperson/torproxy
    container_name: tor
    environment:
      TOR_PASSWORD: "$securePassword"
      DNS1: "1.1.1.1"
      DNS2: "8.8.8.8"
    command: -p "$securePassword"
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
    restart: unless-stopped

volumes:
  tor_data:

"@
        # Append Tor service to the compose file
        $composeFile += $torService
        $composeFile | Set-Content -Path "docker-compose.yml" -NoNewline
        Write-Green "Added Tor service to docker-compose.yml"
    }
} catch {
    Write-Red "Error updating docker-compose.yml: $_"
    Write-Red "Please manually update the Tor password in docker-compose.yml"
}

# Stop running containers to prepare for restart
Write-Yellow "Stopping any running Docker containers..."
try {
    docker-compose down
    Write-Green "Containers stopped successfully"
} catch {
    Write-Red "Error stopping containers: $_"
    Write-Red "Proceeding anyway"
}

# Start the services
Write-Yellow "Starting Docker services..."
try {
    docker-compose up -d
    if ($LASTEXITCODE -ne 0) {
        throw "docker-compose up failed"
    }
    Write-Green "Docker services started successfully"
} catch {
    Write-Red "Error starting Docker services: $_"
    Write-Red "Try running 'docker-compose up -d' manually to see detailed errors"
    exit 1
}

# Wait for services to start
Write-Yellow "Waiting for services to start (20 seconds)..."
Start-Sleep -Seconds 20

# Check if Tor service is running
Write-Yellow "Checking if Tor service is running..."
try {
    $torCheck = docker ps | Select-String "tor"
    if (-not $torCheck) {
        Write-Red "Tor service is not running"
        Write-Yellow "Checking Tor container logs..."
        docker logs tor
        
        Write-Yellow "Attempting a simpler Tor setup..."
        # Fallback to a simpler configuration if the Tor service fails to start
        $composeFile = Get-Content -Path "docker-compose.yml" -Raw
        $simpleTorService = @"

  tor:
    image: dperson/torproxy
    container_name: tor
    environment:
      TOR_PASSWORD: "$securePassword"
    ports:
      - "9050:9050"
      - "9051:9051"
    restart: unless-stopped

"@
        # Replace the Tor service section
        $pattern = "(?s)tor:.*?(?=\n\n)"
        $composeFile = $composeFile -replace $pattern, "tor:$simpleTorService"
        $composeFile | Set-Content -Path "docker-compose.yml" -NoNewline
        
        Write-Yellow "Restarting with simpler Tor configuration..."
        docker-compose down
        docker-compose up -d
        
        # Wait again
        Write-Yellow "Waiting for services to restart (20 seconds)..."
        Start-Sleep -Seconds 20
        
        # Check again
        $torCheck = docker ps | Select-String "tor"
        if (-not $torCheck) {
            Write-Red "Tor service still not running after fallback attempt"
            Write-Red "Please check the Tor configuration manually"
        } else {
            Write-Green "Tor service is now running with simpler configuration"
        }
    } else {
        Write-Green "Tor service is running"
    }
} catch {
    Write-Red "Error checking Tor service: $_"
}

# Run the test script to verify Tor connection
Write-Yellow "Testing Tor connection..."
try {
    # Check if the script exists
    if (Test-Path -Path "src/test_tor.py") {
        # Run the test script
        python src/test_tor.py
        if ($LASTEXITCODE -eq 0) {
            Write-Green "Tor connection test successful!"
        } else {
            Write-Red "Tor connection test failed"
            Write-Red "Please check the logs above for more information"
        }
    } else {
        Write-Red "src/test_tor.py not found"
        Write-Red "Skipping Tor connection test"
    }
} catch {
    Write-Red "Error testing Tor connection: $_"
}

# Final instructions
Write-Cyan "======================================================"
Write-Cyan "                   Setup Complete                     "
Write-Cyan "======================================================"
Write-Output ""
Write-Green "Tor service should now be configured and running."
Write-Output ""
Write-Yellow "To use Tor with the scraper:"
Write-Output "1. Set USE_TOR=true in your .env file"
Write-Output "2. Set TOR_PASSWORD='$securePassword' in your .env file"
Write-Output ""
Write-Yellow "To verify Tor connectivity:"
Write-Output "- Run: python src/tor_ip_check.py --rotate --password '$securePassword'"
Write-Output ""
Write-Yellow "For troubleshooting:"
Write-Output "- Run: .\tor_troubleshoot.ps1"
Write-Output "- View logs: docker-compose logs tor"
Write-Output "- Read docs: docs/tor_troubleshooting.md"
Write-Output ""
Write-Green "Happy scraping with enhanced anonymity!" 