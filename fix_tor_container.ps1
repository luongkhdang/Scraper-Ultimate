# fix_tor_container.ps1 - PowerShell script to fix Tor container tools

# Color functions for better output
function WriteColor($text, $color) {
    $originalColor = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $color
    Write-Output $text
    $host.UI.RawUI.ForegroundColor = $originalColor
}

WriteColor "=== Tor Container Fix Script ===" "Cyan"

# Check Docker
WriteColor "Checking Docker status..." "Yellow"
try {
    $dockerStatus = docker ps 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed"
    }
    WriteColor "Docker is running." "Green"
} catch {
    WriteColor "Docker is not running or you don't have permission to use it." "Red"
    exit 1
}

# Check if tor container exists and is running
WriteColor "Checking Tor container..." "Yellow"
$torRunning = docker ps | Select-String "tor"
if (-not $torRunning) {
    WriteColor "Tor container is not running." "Red"
    
    # Check if it exists but stopped
    $torExists = docker ps -a | Select-String "tor"
    if ($torExists) {
        WriteColor "Tor container exists but is not running. Starting container..." "Yellow"
        docker start tor
        Start-Sleep -Seconds 5
    } else {
        WriteColor "Tor container does not exist. Please run setup_tor.ps1 first." "Red"
        exit 1
    }
} else {
    WriteColor "Tor container is running." "Green"
}

# Install required tools inside the container
WriteColor "Installing required tools inside the Tor container..." "Yellow"
WriteColor "This may take a moment..." "Yellow"

# Try to install tools with apk (Alpine Linux)
$apkCheck = docker exec tor apk --help 2>&1
if ($LASTEXITCODE -eq 0) {
    WriteColor "Container appears to be based on Alpine Linux, using apk..." "Yellow"
    docker exec tor apk add --no-cache socat netcat-openbsd procps curl
    if ($LASTEXITCODE -eq 0) {
        WriteColor "Successfully installed tools using apk." "Green"
    } else {
        WriteColor "Failed to install tools using apk (exit code: $LASTEXITCODE)." "Red"
    }
} 
# Try to install tools with apt-get (Debian/Ubuntu)
else {
    $aptCheck = docker exec tor apt-get --help 2>&1
    if ($LASTEXITCODE -eq 0) {
        WriteColor "Container appears to be based on Debian/Ubuntu, using apt-get..." "Yellow"
        docker exec tor apt-get update
        docker exec tor apt-get install -y socat netcat procps curl
        if ($LASTEXITCODE -eq 0) {
            WriteColor "Successfully installed tools using apt-get." "Green"
        } else {
            WriteColor "Failed to install tools using apt-get (exit code: $LASTEXITCODE)." "Red"
        }
    } else {
        WriteColor "Could not determine package manager. Trying direct download..." "Red"
        # Try to download a static binary of socat as last resort
        docker exec tor sh -c "mkdir -p /tmp/tools && cd /tmp/tools && curl -L -o socat.tar.gz https://github.com/andrew-d/static-binaries/raw/master/binaries/linux/x86_64/socat && tar xzf socat.tar.gz && chmod +x socat && mv socat /usr/local/bin/"
        if ($LASTEXITCODE -eq 0) {
            WriteColor "Successfully installed socat from static binary." "Green"
        } else {
            WriteColor "Failed to install tools using direct download." "Red"
            WriteColor "You may need to rebuild the container using the updated docker-compose.yml." "Red"
        }
    }
}

# Verify tool installation
WriteColor "Verifying tool installation..." "Yellow"
$missingTools = 0

# Check for socat
docker exec tor which socat 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    WriteColor "socat is missing" "Red"
    $missingTools++
} else {
    WriteColor "socat is installed" "Green"
}

# Check for netcat (nc)
docker exec tor which nc 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    WriteColor "netcat (nc) is missing" "Red"
    $missingTools++
} else {
    WriteColor "netcat (nc) is installed" "Green"
}

# Check for pidof
docker exec tor which pidof 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    WriteColor "pidof is missing" "Red"
    $missingTools++
} else {
    WriteColor "pidof is installed" "Green"
}

# Check for curl
docker exec tor which curl 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    WriteColor "curl is missing" "Red"
    $missingTools++
} else {
    WriteColor "curl is installed" "Green"
}

# Final status
if ($missingTools -eq 0) {
    WriteColor "All required tools are installed!" "Green"
    WriteColor "Testing Tor control port connection..." "Yellow"
    
    # Try to send a simple command to the control port
    docker exec tor sh -c 'echo "AUTHENTICATE \"your_secure_password\"\r\nGETINFO version\r\nQUIT" | socat - TCP:localhost:9051'
    if ($LASTEXITCODE -eq 0) {
        WriteColor "Successfully connected to Tor control port." "Green"
        WriteColor "Your Tor container should now be ready for IP rotation." "Green"
    } else {
        WriteColor "Failed to connect to Tor control port (exit code: $LASTEXITCODE)." "Red"
        WriteColor "Check your password in docker-compose.yml and make sure it matches TOR_PASSWORD in your environment." "Yellow"
    }
} else {
    WriteColor "Some tools are still missing. You may need to rebuild the container." "Red"
    WriteColor "To rebuild:" "Yellow"
    WriteColor "1. Stop the current container: docker stop tor" "Cyan"
    WriteColor "2. Remove it: docker rm tor" "Cyan"
    WriteColor "3. Make sure your docker-compose.yml has the updated command with tool installation" "Cyan"
    WriteColor "4. Run: docker-compose up -d" "Cyan"
}

WriteColor "=== Fix Complete ===" "Cyan" 