# Tor connectivity troubleshooting script (PowerShell version)

# Color formatting
$RED = [System.Console]::ForegroundColor = 'Red'
$GREEN = [System.Console]::ForegroundColor = 'Green'
$YELLOW = [System.Console]::ForegroundColor = 'Yellow'
$BLUE = [System.Console]::ForegroundColor = 'Cyan'
$NC = [System.Console]::ResetColor()

function WriteColor($text, $color) {
    $originalColor = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $color
    Write-Output $text
    $host.UI.RawUI.ForegroundColor = $originalColor
}

WriteColor "=== Tor Connectivity Troubleshooting ===" "Cyan"

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

# Check if tor container exists
WriteColor "Checking Tor container..." "Yellow"
$torContainer = docker ps -a | Select-String "tor"
if (-not $torContainer) {
    WriteColor "Tor container not found. Make sure it's properly defined in docker-compose.yml." "Red"
    exit 1
}

# Check if tor container is running
WriteColor "Checking if Tor container is running..." "Yellow"
$runningTor = docker ps | Select-String "tor"
if (-not $runningTor) {
    WriteColor "Tor container is not running." "Red"
    
    # Check exit status
    WriteColor "Last container exit status:" "Yellow"
    docker ps -a | Select-String "tor"
    
    WriteColor "Starting Tor container logs:" "Yellow"
    docker logs tor | Select-Object -First 20
    
    WriteColor "Ending Tor container logs:" "Yellow"
    docker logs tor | Select-Object -Last 20
} else {
    WriteColor "Tor container is running." "Green"
}

# Test Tor connectivity inside the container
WriteColor "Testing network connectivity inside Tor container..." "Yellow"
WriteColor "Testing DNS resolution..." "Yellow"
$dnsTest = docker exec tor nslookup google.com 2>&1
if ($LASTEXITCODE -ne 0) {
    WriteColor "DNS resolution failed" "Red"
}

WriteColor "Testing internet connectivity..." "Yellow"
$connectivityTest = docker exec tor wget -q --timeout=10 --tries=2 -O- https://check.torproject.org 2>&1
if ($LASTEXITCODE -ne 0) {
    WriteColor "Internet connectivity test failed" "Red"
}

# Output Tor bootstrap status
WriteColor "Tor bootstrap status:" "Yellow"
$bootstrapStatus = docker exec tor grep "Bootstrapped" /var/log/tor/notices.log 2>&1
if ($LASTEXITCODE -ne 0) {
    docker logs tor | Select-String "Bootstrapped"
} else {
    Write-Output $bootstrapStatus
}

# Check external connectivity to Tor ports
WriteColor "Checking external connectivity to Tor SOCKS port..." "Yellow"
$testSocket = New-Object Net.Sockets.TcpClient
try {
    $testConnection = $testSocket.BeginConnect("localhost", 9050, $null, $null)
    $wait = $testConnection.AsyncWaitHandle.WaitOne(1000, $false)
    if ($wait -and $testSocket.Connected) {
        WriteColor "SOCKS port 9050 is accessible." "Green"
    } else {
        WriteColor "SOCKS port 9050 is not accessible." "Red"
    }
} catch {
    WriteColor "SOCKS port 9050 is not accessible: $_" "Red"
} finally {
    $testSocket.Close()
}

WriteColor "Checking external connectivity to Tor Control port..." "Yellow"
$testSocket = New-Object Net.Sockets.TcpClient
try {
    $testConnection = $testSocket.BeginConnect("localhost", 9051, $null, $null)
    $wait = $testConnection.AsyncWaitHandle.WaitOne(1000, $false)
    if ($wait -and $testSocket.Connected) {
        WriteColor "Control port 9051 is accessible." "Green"
    } else {
        WriteColor "Control port 9051 is not accessible." "Red"
    }
} catch {
    WriteColor "Control port 9051 is not accessible: $_" "Red"
} finally {
    $testSocket.Close()
}

# Check if we can get a Tor circuit
WriteColor "Attempting to get a Tor circuit..." "Yellow"
$torState = docker exec tor cat /var/lib/tor/data/state 2>&1
if ($LASTEXITCODE -ne 0) {
    WriteColor "Could not read Tor state file" "Red"
}

# Check for network restrictions
WriteColor "Checking for network restrictions..." "Yellow"
Write-Output "Try using Tor bridges if you're on a restricted network."
Write-Output "Add the following to torrc and restart the container:"
WriteColor "UseBridges 1" "Cyan"
WriteColor "ClientTransportPlugin obfs4 exec /usr/bin/obfs4proxy" "Cyan"
WriteColor "Bridge obfs4 X.X.X.X:YYYY FINGERPRINT" "Cyan"
Write-Output "(You can get bridges from https://bridges.torproject.org/)"

# Suggestions
WriteColor "Suggestions:" "Green"
Write-Output "1. Try restarting the Tor container: docker-compose restart tor"
Write-Output "2. Wait longer for bootstrap (can take several minutes)"
Write-Output "3. If you're on a restricted network, try using bridges"
Write-Output "4. Check if your ISP or network is blocking Tor"
Write-Output "5. Try using a VPN to connect to Tor"

# Provide next steps
WriteColor "Next steps:" "Yellow"
Write-Output "If you're seeing '404 Not Found' errors for directory servers:"
Write-Output "- This often means Tor directories are blocked on your network"
Write-Output "- Try using bridges (obfs4, snowflake) to bypass restrictions"
Write-Output "- Check firewall settings that might block Tor"
Write-Output "- Some ISPs actively block Tor connections"

WriteColor "=== Troubleshooting Complete ===" "Cyan" 