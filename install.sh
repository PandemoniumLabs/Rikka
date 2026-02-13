#!/usr/bin/env bash
set -euo pipefail

# Colors
GREEN="\033[0;32m"
CYAN="\033[0;36m"
RED="\033[0;31m"
YELLOW="\033[0;33m"
RESET="\033[0m"

info() { echo -e "${CYAN}[*] $1${RESET}"; }
success() { echo -e "${GREEN}[+] $1${RESET}"; }
warn() { echo -e "${YELLOW}[!] $1${RESET}"; }
error() { echo -e "${RED}[!] $1${RESET}"; }

spinner() {
  local pid=$1
  local message=$2
  local delay=0.1
  local spinstr='|/-\'
  printf ">>> %s " "$message"
  while kill -0 "$pid" 2>/dev/null; do
    for i in $(seq 0 3); do
      printf "\b%c" "${spinstr:i:1}"
      sleep $delay
    done
  done
  printf "\b Done\n"
}

HARD_RESET=false
for arg in "$@"; do
  [[ "$arg" == "--hard-reset" ]] && HARD_RESET=true
done

RIKKA_DIR="$HOME/Rikka"
TMP_HELPER="$(mktemp)"

# Atomic hard reset flow
if $HARD_RESET; then
  warn "Hard reset enabled!"
  cd /tmp || exit 1
  rm -rf "$RIKKA_DIR"
  git clone https://github.com/PandemoniumLabs/Rikka.git "$RIKKA_DIR" || {
    echo "Clone failed!"
    exit 1
  }

  echo ">>> Done! Run: bash $RIKKA_DIR/$(basename "$0")"
  exit 0
fi

# Display header
if [[ -n "${KITTY_WINDOW_ID-}" && -f "images/rikka.png" ]]; then
  kitty +kitten icat images/halo.png
  echo ""
else
  echo -e "${CYAN}"
  cat <<'EOF'
██████╗ ██╗██╗  ██╗██╗  ██╗ █████╗ ██╗
██╔══██╗██║██║ ██╔╝██║ ██╔╝██╔══██╗██║
██████╔╝██║█████╔╝ █████╔╝ ███████║██║
██╔══██╗██║██╔═██╗ ██╔═██╗ ██╔══██║╚═╝
██║  ██║██║██║  ██╗██║  ██╗██║  ██║██╗
╚═╝  ╚═╝╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝
EOF
  echo -e "${RESET}"
  echo -e "${CYAN}                         Rikka installer${RESET}"
  echo ""
fi

# Detect python
PYTHON_CMD=""
if command -v python3 &>/dev/null; then
  PYTHON_CMD=python3
elif command -v python &>/dev/null; then
  PYTHON_CMD=python
else
  error "Python3 not found!"
  exit 1
fi
info "Using Python: $($PYTHON_CMD --version 2>&1)"

# Ensure pipx
if ! command -v pipx &>/dev/null; then
  info "pipx not found, installing..."
  $PYTHON_CMD -m pip install --user pipx
  $PYTHON_CMD -m pipx ensurepath
fi

info "Upgrading pipx..."
pip install --upgrade pipx >/dev/null 2>&1 &
spinner $! "Upgrading pipx"

cd "$RIKKA_DIR"

if pipx list | grep -q 'rikka'; then
  info "Rikka detected, upgrading..."
  pipx install . --force >/dev/null 2>&1 &
  spinner $! "Upgrading Rikka"
  success "Rikka upgraded!"
else
  info "Installing Rikka..."
  pipx install . --force >/dev/null 2>&1 &
  spinner $! "Installing Rikka"
  success "Rikka installed!"
fi