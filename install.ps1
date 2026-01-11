$ErrorActionPreference = "Stop"

$Cyan = "`e[36m"
$Green = "`e[32m"
$Yellow = "`e[33m"
$Red = "`e[31m"
$Reset = "`e[0m"

function Write-Info($msg)    { Write-Host "${Cyan}[*] $msg${Reset}" }
function Write-Success($msg) { Write-Host "${Green}[+] $msg${Reset}" }
function Write-Warn($msg)    { Write-Host "${Yellow}[!] $msg${Reset}" }
function Write-Error($msg)   { Write-Host "${Red}[!] $msg${Reset}" }

$HardReset = $args -contains "--hard-reset"
$DevMode = $args -contains "--dev"
$Repo = "https://github.com/XeonXE534/Project-Ibuki.git"
$Branch = if ($DevMode) { "test_branch" } else { "main" }
$TempDir = Join-Path $env:TEMP "Project-Ibuki-$([Guid]::NewGuid().ToString().Substring(0,8))"

Clear-Host
Write-Host "${Cyan}"
@"
██████╗ ██████╗  ██████╗      ██╗███████╗ ██████╗████████╗    ██╗██████╗ ██╗   ██╗██╗  ██╗██╗
██╔══██╗██╔══██╗██╔═══██╗     ██║██╔════╝██╔════╝╚══██╔══╝    ██║██╔══██╗██║   ██║██║ ██╔╝██║
██████╔╝██████╔╝██║   ██║     ██║█████╗  ██║        ██║       ██║██████╔╝██║   ██║█████╔╝ ██║
██╔═══╝ ██╔══██╗██║   ██║██   ██║██╔══╝  ██║        ██║       ██║██╔══██╗██║   ██║██╔═██╗ ██║
██║     ██║  ██║╚██████╔╝╚█████╔╝███████╗╚██████╗   ██║       ██║██████╔╝╚██████╔╝██║  ██╗██║
╚═╝     ╚═╝  ╚═╝ ╚═════╝  ╚════╝ ╚══════╝ ╚═════╝   ╚═╝       ╚═╝╚═════╝  ╚═════╝ ╚═╝  ╚═╝
"@
Write-Host "${Reset}"
Write-Host "${Cyan}                         Project-Ibuki installer${Reset}"
Write-Host ""

if ($DevMode) {
    Write-Warn "Installing from dev branch (test_branch)..."
}

if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python not found!"
    exit 1
}

if (!(Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Error "Git not found!"
    exit 1
}

if (!(Get-Command pipx -ErrorAction SilentlyContinue)) {
    Write-Info "Installing pipx..."
    python -m pip install --user pipx
    python -m pipx ensurepath
    # Refresh PATH for current session
    $env:PATH += ";$env:USERPROFILE\.local\bin"
}

Write-Info "Cloning repository..."
git clone $Repo $TempDir --depth 1 --branch $Branch --quiet

Set-Location $TempDir

if ($HardReset) {
    Write-Warn "Hard resetting Ibuki..."
    pipx uninstall ibuki 2>$null
}

$installed = pipx list | Select-String "ibuki"
if ($installed) {
    Write-Info "Upgrading Ibuki..."
    pipx install . --force
} else {
    Write-Info "Installing Ibuki..."
    pipx install .
}

Set-Location $env:USERPROFILE
Remove-Item -Recurse -Force $TempDir
Write-Success "Installation complete! Restart your terminal and run 'ibuki'"