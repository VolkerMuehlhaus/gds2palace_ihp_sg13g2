#!/usr/bin/env bash
#
# install_palace_wsl.sh - installs ONLY the AWS Palace solver, the small
# Touchstone-conversion venv, and the run_palace/combine_snp helper scripts,
# inside a WSL2 Linux distro.
#
# This is the WSL-side half of the gds2palace/setupEM Windows workflow. It is
# normally invoked automatically by install_gds2palace.bat (via
# `wsl.exe -- bash -lc "bash '<path>' <args>"`), NOT run by hand. setupEM and
# gds2palace themselves are installed Windows-native by that .bat, not here -
# this script only sets up the pieces that must be Linux (Palace itself) or
# that setupEM's Windows->WSL hand-off expects to find on the WSL login
# shell's PATH (run_palace, combine_snp).
#
# It can also be run directly inside an already-open WSL/Linux terminal if
# you want to (re)install just the Palace side, e.g.:
#   bash install_palace_wsl.sh --yes
#
# Safe to re-run: every step below is idempotent (skips work that is already
# done).

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults / option parsing
# ---------------------------------------------------------------------------

VENV_DIR="${HOME}/venv/palace"
PALACE_VERSION="016"
RUN_NP=""
ASSUME_YES=0

GDS2PALACE_REPO_RAW="https://raw.githubusercontent.com/VolkerMuehlhaus/gds2palace_ihp_sg13g2/main"

usage() {
  cat <<'EOF'
install_palace_wsl.sh - installs AWS Palace (Apptainer container), a small
Touchstone-conversion venv, and the run_palace/combine_snp helper scripts
inside WSL2/Linux.

Usage:
  bash install_palace_wsl.sh [options]

Options:
  --venv-dir PATH       Where to create the helper Python venv
                         (default: ~/venv/palace)
  --palace-version X    Palace container tag to pull (default: 016)
  --np N                Default core count baked into run_palace
                         (default: number of CPU cores, minimum 4)
  --yes                 Non-interactive: never prompt, accept all defaults
  -h, --help             Show this help and exit
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --venv-dir) VENV_DIR="$2"; shift 2 ;;
    --palace-version) PALACE_VERSION="$2"; shift 2 ;;
    --np) RUN_NP="$2"; shift 2 ;;
    --yes) ASSUME_YES=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

step()  { printf "\n==> %s\n" "$*"; }
info()  { printf "    %s\n" "$*"; }
ok()    { printf "    OK: %s\n" "$*"; }
warn()  { printf "    WARN: %s\n" "$*"; }
fail()  { printf "    ERROR: %s\n" "$*" >&2; exit 1; }

confirm() {
  [ "$ASSUME_YES" = 1 ] && return 0
  local reply
  read -r -p "    $1 [Y/n] " reply || true
  case "$reply" in
    [nN]|[nN][oO]) return 1 ;;
    *) return 0 ;;
  esac
}

# ---------------------------------------------------------------------------
# Step 0: sanity check - this must run inside a real Linux/WSL shell
# ---------------------------------------------------------------------------

step "Checking environment"

[ "$(uname -s)" = "Linux" ] || fail "This script must run inside WSL/Linux, not on Windows directly."
if grep -qi microsoft /proc/version 2>/dev/null || [ -n "${WSL_DISTRO_NAME:-}" ]; then
  ok "Running inside WSL2 (distro: ${WSL_DISTRO_NAME:-unknown})"
else
  ok "Running on native Linux ($(uname -m))"
fi

if [ -z "$RUN_NP" ]; then
  NPROC="$(nproc 2>/dev/null || echo 4)"
  if [ "$NPROC" -lt 4 ]; then
    RUN_NP=4
  else
    RUN_NP=$NPROC
  fi
fi
info "helper venv directory: $VENV_DIR"
info "Palace container tag:  $PALACE_VERSION"
info "run_palace cores:      $RUN_NP  (override with --venv-dir / --palace-version / --np)"

# ---------------------------------------------------------------------------
# Step 1: system prerequisites (python3 + venv module)
# ---------------------------------------------------------------------------

step "Checking system prerequisites"

command -v python3 >/dev/null 2>&1 || fail "python3 not found. Install it first (e.g. 'sudo apt install python3 python3-venv'), then re-run."
ok "python3 found: $(python3 --version)"

if ! command -v curl >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    step "Installing curl (needed to download helper scripts)"
    sudo apt-get update -y || warn "apt-get update reported errors (continuing anyway)"
    sudo apt-get install -y curl || fail "Could not install curl automatically. Install it manually and re-run."
  else
    fail "curl not found and could not be auto-installed on this system (no apt-get found). Install it manually (it's needed to download helper scripts later in this script) and re-run."
  fi
fi
ok "curl found: $(curl --version | head -1)"

if ! python3 -c "import venv" >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    step "Installing python3-venv (needed to create the helper venv)"
    sudo apt-get update -y || warn "apt-get update reported errors (continuing anyway)"
    sudo apt-get install -y python3-venv || fail "Could not install python3-venv automatically. Install it manually and re-run."
  else
    fail "Python's 'venv' module is missing and could not be auto-installed on this system. Install it manually and re-run."
  fi
fi
ok "python3 'venv' module available"

# ---------------------------------------------------------------------------
# Step 2: small helper venv (only needs numpy + scikit-rf, for combine_snp)
# ---------------------------------------------------------------------------

step "Setting up the Touchstone-conversion helper venv at $VENV_DIR"

if [ -f "$VENV_DIR/bin/activate" ]; then
  ok "venv already exists, reusing it"
else
  mkdir -p "$(dirname "$VENV_DIR")"
  python3 -m venv "$VENV_DIR"
  ok "Created venv"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip --quiet
pip install --upgrade numpy scikit-rf --quiet
ok "numpy + scikit-rf installed (used by combine_snp to build Touchstone .snp files)"

# ---------------------------------------------------------------------------
# Step 3: AWS Palace solver via prebuilt Apptainer container
# ---------------------------------------------------------------------------

step "Installing AWS Palace via prebuilt Apptainer container (version $PALACE_VERSION)"

if ! command -v apptainer >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    if confirm "Apptainer is not installed. Install it now via the Apptainer PPA?"; then
      sudo add-apt-repository -y ppa:apptainer/ppa
      sudo apt-get update -y
      sudo apt-get install -y apptainer
    else
      fail "Apptainer is required. Install it manually
    (https://apptainer.org/docs/admin/main/installation.html) and re-run."
    fi
  else
    fail "Apptainer is required and could not be auto-installed on this system
    (no apt-get found). Install it manually
    (https://apptainer.org/docs/admin/main/installation.html) and re-run."
  fi
fi
ok "apptainer found: $(apptainer --version)"

PALACE_SIF="$HOME/palace_${PALACE_VERSION}.sif"
if [ -f "$PALACE_SIF" ]; then
  ok "Container image already present at $PALACE_SIF, reusing it"
else
  step "Pulling palace_${PALACE_VERSION} container image (this downloads a few GB)"
  apptainer pull "$PALACE_SIF" "oras://ghcr.io/volkermuehlhaus/palace_${PALACE_VERSION}:latest"
  ok "Downloaded to $PALACE_SIF"
fi

step "Verifying the Palace container"
apptainer exec "$PALACE_SIF" palace --version || fail "Palace container did not run correctly."

# ---------------------------------------------------------------------------
# Step 4: helper scripts, with real paths already filled in
# ---------------------------------------------------------------------------

step "Installing helper scripts into $VENV_DIR/bin"

curl -fsSL -o "$VENV_DIR/bin/combine_extend_snp.py" "$GDS2PALACE_REPO_RAW/scripts/combine_extend_snp.py"
curl -fsSL -o "$VENV_DIR/bin/palace_summary.py" "$GDS2PALACE_REPO_RAW/scripts/palace_summary.py"
chmod +x "$VENV_DIR/bin/combine_extend_snp.py" "$VENV_DIR/bin/palace_summary.py"
ok "Downloaded combine_extend_snp.py and palace_summary.py"

cat > "$VENV_DIR/bin/combine_snp" <<EOF
#!/bin/sh
# Auto-generated by install_palace_wsl.sh - converts Palace S-parameter
# output to Touchstone SnP format.
"$VENV_DIR/bin/python" "$VENV_DIR/bin/combine_extend_snp.py" "\$@"
EOF
chmod +x "$VENV_DIR/bin/combine_snp"
ok "Generated combine_snp"

cat > "$VENV_DIR/bin/run_palace" <<EOF
#!/bin/bash
# Auto-generated by install_palace_wsl.sh
# Runs Palace from the Apptainer container image at $PALACE_SIF
apptainer exec "$PALACE_SIF" palace -np ${RUN_NP} "\$1"
EOF
chmod +x "$VENV_DIR/bin/run_palace"
ok "Generated run_palace (using $RUN_NP cores by default)"

curl -fsSL -o "$VENV_DIR/bin/run_palace_remote.template" "$GDS2PALACE_REPO_RAW/scripts/run_palace_remote" 2>/dev/null || true
if [ -f "$VENV_DIR/bin/run_palace_remote.template" ]; then
  info "Also saved run_palace_remote.template - edit USERNAME/SERVER/TARGETDIR
    and rename to 'run_palace' if you want to simulate on a remote machine
    instead of locally."
fi

# ---------------------------------------------------------------------------
# Step 5: put $VENV_DIR/bin on PATH for LOGIN shells
# ---------------------------------------------------------------------------
#
# setupEM's Windows->WSL hand-off runs `wsl.exe --cd <dir> -- bash -lc
# ./run_sim`, i.e. a *login* shell, which reads ~/.profile (not ~/.bashrc).
# Add the PATH line there so run_palace/combine_snp resolve the same way
# whether launched from setupEM on Windows or typed by hand in a WSL
# terminal.

step "Adding $VENV_DIR/bin to PATH in ~/.profile"

PROFILE_LINE="export PATH=\"$VENV_DIR/bin:\$PATH\""
if grep -qF "$VENV_DIR/bin" "$HOME/.profile" 2>/dev/null; then
  ok "~/.profile already updated"
else
  echo "$PROFILE_LINE" >> "$HOME/.profile"
  ok "Added to ~/.profile (new terminals/logins pick this up automatically)"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

step "Palace/WSL setup complete"

echo "  What was installed in WSL:"
echo "    - AWS Palace (container)                                       -> $PALACE_SIF"
echo "    - run_palace / combine_snp (already pointing at the above)     -> $VENV_DIR/bin"
echo
echo "  setupEM and gds2palace themselves run natively on Windows (not in WSL)."
echo "  When you click 'Start Simulation' in setupEM, it will hand off into WSL"
echo "  automatically and find run_palace/combine_snp here."
echo
echo "  Re-run this script any time - it will skip anything already done."
