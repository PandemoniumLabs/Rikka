Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

param(
    [switch]$HardReset
)

$ErrorActionPreference = "Stop"

# Colors
function Write-Info { 
    Write-Host "[*] $args" -ForegroundColor Cyan 
}

function Write-Success { 
    Write-Host "[+] $args" -ForegroundColor Green 
}

function Write-Warn { 
    Write-Host "[!] $args" -ForegroundColor Yellow 
}

function Write-Error { 
    Write-Host "[!] $args" -ForegroundColor Red 
}

function Show-Spinner {
    param(
        [scriptblock]$Task,
        [string]$Message
    )
    
    $job = Start-Job -ScriptBlock $Task
    $spinChars = '|', '/', '-', '\'
    $i = 0
    
    Write-Host ">>> $Message " -NoNewline
    
    while ($job.State -eq 'Running') {
        Write-Host "`b$($spinChars[$i % 4])" -NoNewline -ForegroundColor Cyan
        Start-Sleep -Milliseconds 100
        $i++
    }
    
    $result = Receive-Job -Job $job
    Remove-Job -Job $job
    
    Write-Host "`b Done" -ForegroundColor Green
    
    if ($job.State -eq 'Failed') {
        throw "Task failed: $Message"
    }
    
    return $result
}

$IBUKI_DIR = Join-Path $env:USERPROFILE "Project-Ibuki"

# Hard reset flow
if ($HardReset) {
    Write-Warn "Hard reset enabled!"
    
    if (Test-Path $IBUKI_DIR) {
        Write-Info "Removing existing installation..."
        Remove-Item -Path $IBUKI_DIR -Recurse -Force -ErrorAction SilentlyContinue
    }
    
    try {
        Write-Info "Cloning repository..."
        git clone https://github.com/XeonXE534/Project-Ibuki.git $IBUKI_DIR
        Write-Success "Clone complete!"
        Write-Host ""
        Write-Host ">>> Done! Run: powershell -File $IBUKI_DIR\install.ps1" -ForegroundColor Cyan
    } catch {
        Write-Error "Clone failed: $_"
        exit 1
    }
    
    exit 0
}

# Display header
Write-Host ""
Write-Host "██████╗ ██████╗  ██████╗      ██╗███████╗ ██████╗████████╗    ██╗██████╗ ██╗   ██╗██╗  ██╗██╗" -ForegroundColor Cyan
Write-Host "██╔══██╗██╔══██╗██╔═══██╗     ██║██╔════╝██╔════╝╚══██╔══╝    ██║██╔══██╗██║   ██║██║ ██╔╝██║" -ForegroundColor Cyan
Write-Host "██████╔╝██████╔╝██║   ██║     ██║█████╗  ██║        ██║       ██║██████╔╝██║   ██║█████╔╝ ██║" -ForegroundColor Cyan
Write-Host "██╔═══╝ ██╔══██╗██║   ██║██   ██║██╔══╝  ██║        ██║       ██║██╔══██╗██║   ██║██╔═██╗ ██║" -ForegroundColor Cyan
Write-Host "██║     ██║  ██║╚██████╔╝╚█████╔╝███████╗╚██████╗   ██║       ██║██████╔╝╚██████╔╝██║  ██╗██║" -ForegroundColor Cyan
Write-Host "╚═╝     ╚═╝  ╚═╝ ╚═════╝  ╚════╝ ╚══════╝ ╚═════╝   ╚═╝       ╚═╝╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "                         Project-Ibuki installer" -ForegroundColor Cyan
Write-Host ""

# Check Python
$pythonCmd = $null

foreach ($cmd in @('python3', 'python', 'py')) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
        $pythonCmd = $cmd
        break
    }
}

if (-not $pythonCmd) {
    Write-Error "Python3 not found! Install from https://python.org"
    Write-Host ""
    Write-Host "After installing, make sure to check 'Add Python to PATH' during installation" -ForegroundColor Yellow
    exit 1
}

$pythonVersion = & $pythonCmd --version 2>&1
Write-Info "Using Python: $pythonVersion"

# Ensure pip is available
try {
    & $pythonCmd -m pip --version | Out-Null
} catch {
    Write-Error "pip not found! Reinstall Python with pip included"
    exit 1
}

# Install/upgrade pipx
$pipxInstalled = Get-Command pipx -ErrorAction SilentlyContinue

if (-not $pipxInstalled) {
    Write-Info "pipx not found, installing..."
    
    try {
        Show-Spinner -Message "Installing pipx" -Task {
            & $using:pythonCmd -m pip install --user pipx 2>&1 | Out-Null
            & $using:pythonCmd -m pipx ensurepath 2>&1 | Out-Null
        }
        
        Write-Success "pipx installed!"
        Write-Warn "Please restart your terminal for pipx to be available in PATH"
        Write-Warn "Then run this installer again"
        exit 0
        
    } catch {
        Write-Error "Failed to install pipx: $_"
        exit 1
    }
} else {
    Write-Info "Upgrading pipx..."
    
    try {
        Show-Spinner -Message "Upgrading pipx" -Task {
            & pip install --upgrade pipx 2>&1 | Out-Null
        }
    } catch {
        Write-Warn "pipx upgrade failed, continuing anyway..."
    }
}

# Change to project directory
if (-not (Test-Path $IBUKI_DIR)) {
    Write-Error "Project directory not found: $IBUKI_DIR"
    Write-Info "Run with -HardReset flag to clone the repository"
    exit 1
}

Set-Location $IBUKI_DIR

# Check if Ibuki is already installed
$ibukiInstalled = & pipx list 2>&1 | Select-String -Pattern "ibuki" -Quiet

if ($ibukiInstalled) {
    Write-Info "Ibuki detected, upgrading..."
    
    try {
        Show-Spinner -Message "Upgrading Ibuki" -Task {
            & pipx install . --force 2>&1 | Out-Null
        }
        Write-Success "Ibuki upgraded!"
    } catch {
        Write-Error "Upgrade failed: $_"
        Write-Info "Try running with -HardReset flag"
        exit 1
    }
    
} else {
    Write-Info "Installing Ibuki..."
    
    try {
        Show-Spinner -Message "Installing Ibuki" -Task {
            & pipx install . --force 2>&1 | Out-Null
        }
        Write-Success "Ibuki installed!"
    } catch {
        Write-Error "Installation failed: $_"
        exit 1
    }
}

Write-Host ""
Write-Success "Installation complete!"
Write-Host ""
Write-Info "Run 'ibuki' to start using Project-Ibuki"
Write-Host ""

# Check if pipx bin directory is in PATH
$pipxBinDir = & pipx environment 2>&1 | Select-String -Pattern "PIPX_BIN_DIR" | ForEach-Object { $_.ToString().Split('=')[1].Trim() }

if ($pipxBinDir -and ($env:PATH -notlike "*$pipxBinDir*")) {
    Write-Warn "pipx bin directory may not be in your PATH"
    Write-Info "Add this to your PATH: $pipxBinDir"
    Write-Info "Or run: pipx ensurepath"
}