#!/usr/bin/env bash
set -euo pipefail

GREEN="\033[0;32m"
CYAN="\033[0;36m"
RED="\033[0;31m"
YELLOW="\033[0;33m"
RESET="\033[0m"

info()    { echo -e "${CYAN}[*] $1${RESET}"; }
success() { echo -e "${GREEN}[+] $1${RESET}"; }
warn()    { echo -e "${YELLOW}[!] $1${RESET}"; }
error()   { echo -e "${RED}[!] $1${RESET}"; }

spinner() {
  local pid=$1
  local message=$2
  local delay=0.1
  local spinstr='|/-\'
  printf "${CYAN}>>> %s ${RESET}" "$message"
  while kill -0 "$pid" 2>/dev/null; do
    for i in $(seq 0 3); do
      printf "\b%c" "${spinstr:i:1}"
      sleep $delay
    done
  done
  printf "\b Done\n"
}

HARD_RESET=false
DEV_MODE=false
for arg in "$@"; do
  [[ "$arg" == "--hard-reset" ]] && HARD_RESET=true
  [[ "$arg" == "--dev" ]] && DEV_MODE=true
done

REPO="https://github.com/XeonXE534/Project-Ibuki.git"
BRANCH="main"
[[ "$DEV_MODE" == true ]] && BRANCH="test_branch"

TMP_DIR=$(mktemp -d)

if [[ "$DEV_MODE" == true ]]; then
  warn "Installing from dev branch (test_branch)..."
fi

git clone "$REPO" "$TMP_DIR" --depth 1 --branch "$BRANCH" >/dev/null 2>&1

cd "$TMP_DIR"
if [[ -n "${KITTY_WINDOW_ID-}" && -f "images/halo.png" ]]; then
  kitty +kitten icat images/halo.png
  echo ""
else
  echo -e "${CYAN}"
  cat <<'EOF'
██████╗ ██████╗  ██████╗      ██╗███████╗ ██████╗████████╗    ██╗██████╗ ██╗   ██╗██╗  ██╗██╗
██╔══██╗██╔══██╗██╔═══██╗     ██║██╔════╝██╔════╝╚══██╔══╝    ██║██╔══██╗██║   ██║██║ ██╔╝██║
██████╔╝██████╔╝██║   ██║     ██║█████╗  ██║        ██║       ██║██████╔╝██║   ██║█████╔╝ ██║
██╔═══╝ ██╔══██╗██║   ██║██   ██║██╔══╝  ██║        ██║       ██║██╔══██╗██║   ██║██╔═██╗ ██║
██║     ██║  ██║╚██████╔╝╚█████╔╝███████╗╚██████╗   ██║       ██║██████╔╝╚██████╔╝██║  ██╗██║
╚═╝     ╚═╝  ╚═╝ ╚═════╝  ╚════╝ ╚══════╝ ╚═════╝   ╚═╝       ╚═╝╚═════╝  ╚═════╝ ╚═╝  ╚═╝
EOF
  echo -e "${RESET}"
  echo -e "${CYAN}                         Project-Ibuki installer${RESET}"
  echo ""
fi

PYTHON_CMD=""
if command -v python3 &>/dev/null; then
  PYTHON_CMD=python3
elif command -v python &>/dev/null; then
  PYTHON_CMD=python
else
  error "Python3 not found!"
  exit 1
fi

if ! command -v pipx &>/dev/null; then
  info "pipx not found, installing..."
  $PYTHON_CMD -m pip install --user pipx
  $PYTHON_CMD -m pipx ensurepath
  export PATH="$PATH:$HOME/.local/bin"
fi

if $HARD_RESET; then
  warn "Hard resetting Ibuki environment..."
  pipx uninstall ibuki >/dev/null 2>&1 || true
fi

if pipx list | grep -E -q 'ibuki|project-ibuki'; then
  info "Upgrading Ibuki..."
  pipx install . --force >/dev/null 2>&1 &
  spinner $! "Upgrading"
else
  info "Installing Ibuki..."
  pipx install . >/dev/null 2>&1 &
  spinner $! "Installing"
fi

cd ~
rm -rf "$TMP_DIR"
success "Ibuki installed! Run 'ibuki' to start."