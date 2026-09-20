#!/usr/bin/env bash
#
# install_gds2palace.sh - one-shot Linux setup for the gds2palace/setupEM/
# AWS Palace workflow, for users with little or no Python experience.
#
# What this does:
#   1. Creates a Python venv (default: ~/venv/palace) and installs setupEM
#      there, which pulls in gds2palace, gds_prepare_for_EM, and every other
#      Python dependency (including scikit-rf, needed by combine_snp below) -
#      one venv holds everything, since Palace runs on this same machine.
#   2. Adds that venv's bin/ to PATH via ~/.profile, so setupEM/run_palace/
#      combine_snp are typeable directly in any new terminal - no manual
#      "source .../activate" needed.
#   3. Installs the AWS Palace FEM solver itself via a prebuilt Apptainer
#      container image, unless --skip-palace is given.
#   4. Downloads the helper scripts (combine_extend_snp.py, palace_summary.py)
#      from the gds2palace repo and generates ready-to-use wrapper scripts
#      (run_palace, combine_snp) with the correct, literal paths for THIS
#      machine already filled in - no manual template editing required.
#   5. Prints a short verification report and "what to type next".
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/VolkerMuehlhaus/gds2palace_ihp_sg13g2/main/scripts/install_gds2palace.sh | bash
#   # or, downloaded locally:
#   ./install_gds2palace.sh [options]
#
# Run with NO options at all for an interactive wizard instead (asks for the
# venv location, whether to add KLayout integration, and whether to set up
# Palace now, with defaults shown in brackets - just press Enter to accept).
# Any option at all (even just --yes) skips the wizard and uses the fully
# automatic, script-friendly behavior below instead.
#
# Options:
#   --venv-dir PATH     Where to create the Python venv (default: ~/venv/palace)
#   --palace-version X   Palace container tag to pull (default: 016)
#   --np N               Default core count baked into run_palace (default:
#                        number of CPU cores, minimum 4, no upper limit)
#   --skip-palace        Only set up the Python side (venv, setupEM,
#                        gds2palace); skip installing the Palace solver itself
#   --with-klayout       Also download the KLayout integration helper script
#   --yes                Non-interactive: never prompt, accept all defaults
#                        (needed when piping this script through curl | bash)
#   -h, --help            Show this help and exit
#
# Safe to re-run: every step below is idempotent (skips work that is already
# done) so you can re-run this after a partial failure, or to pick up updates.
#
# Linux only - no macOS support (Apptainer containers don't run natively on
# macOS; see doc/building-palace-spack.md if you need a from-source build
# there instead). Works the same whether run on native Linux or inside WSL2.

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults / option parsing
# ---------------------------------------------------------------------------

VENV_DIR="${HOME}/venv/palace"
PALACE_VERSION="016"
RUN_NP=""
SKIP_PALACE=0
WITH_KLAYOUT=0
ASSUME_YES=0

GDS2PALACE_REPO_RAW="https://raw.githubusercontent.com/VolkerMuehlhaus/gds2palace_ihp_sg13g2/main"
SETUPEM_REPO_RAW="https://raw.githubusercontent.com/VolkerMuehlhaus/setupEM/main"

usage() { sed -n '2,/^set -euo pipefail/p' "$0" | sed '$d; s/^# \{0,1\}//'; }

# No options at all (e.g. just double-clicked, or `bash install_gds2palace.sh`
# with nothing after it) drops into an interactive wizard for the handful of
# settings worth asking about; any option at all (even just --yes) keeps the
# fully-automatic, script-friendly behavior with no prompts - checked here,
# before the option-parsing loop below consumes "$@".
NO_ARGS=0
[ $# -eq 0 ] && NO_ARGS=1

while [ $# -gt 0 ]; do
  case "$1" in
    --venv-dir) VENV_DIR="$2"; shift 2 ;;
    --palace-version) PALACE_VERSION="$2"; shift 2 ;;
    --np) RUN_NP="$2"; shift 2 ;;
    --skip-palace) SKIP_PALACE=1; shift ;;
    --with-klayout) WITH_KLAYOUT=1; shift ;;
    --yes) ASSUME_YES=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

C_BOLD="\033[1m"; C_GREEN="\033[32m"; C_YELLOW="\033[33m"; C_RED="\033[31m"; C_RESET="\033[0m"

step()  { printf "\n${C_BOLD}==> %s${C_RESET}\n" "$*"; }
info()  { printf "    %s\n" "$*"; }
ok()    { printf "    ${C_GREEN}OK:${C_RESET} %s\n" "$*"; }
warn()  { printf "    ${C_YELLOW}WARN:${C_RESET} %s\n" "$*"; }
fail()  { printf "    ${C_RED}ERROR:${C_RESET} %s\n" "$*" >&2; exit 1; }

confirm() {
  # confirm "question" - returns 0 (yes) unless the user explicitly says no.
  # Always yes in --yes mode.
  [ "$ASSUME_YES" = 1 ] && return 0
  local reply
  read -r -p "    $1 [Y/n] " reply || true
  case "$reply" in
    [nN]|[nN][oO]) return 1 ;;
    *) return 0 ;;
  esac
}

require_sudo() {
  # Validates (and caches) sudo credentials ONCE, so the "sudo apt-get ..."
  # calls that follow in the same step don't each prompt for a password
  # separately. Returns 1 with a clear, specific message if this account has
  # no sudo access at all - instead of silently retrying apt-get two or three
  # times in a row, each one prompting again and failing the same way, then
  # ending on a generic "install it manually" message that's actually
  # useless advice when the real problem is "this account can't install
  # anything, with or without a manual command".
  [ "$(id -u)" = "0" ] && return 0
  if ! command -v sudo >/dev/null 2>&1; then
    warn "No sudo found, and this isn't running as root. Ask whoever administers this system to install the needed packages."
    return 1
  fi
  if [ -t 0 ]; then
    # Real terminal attached: let sudo prompt normally (once, then cached
    # for this step's remaining sudo calls). Fails fast with sudo's own
    # "not in sudoers" message if this account has no rights at all - no
    # hang risk, since sudo can actually show/read a real prompt here.
    if ! sudo -v; then
      warn "This account doesn't have sudo access, so packages can't be installed automatically. Ask your system administrator to install them, or re-run this script from an account that has sudo access."
      return 1
    fi
  else
    # No terminal (e.g. piped through curl | bash): sudo -v here can HANG
    # indefinitely instead of failing, on systems where it still tries some
    # other prompt mechanism despite stdin not being a TTY (confirmed by
    # testing). "-n" makes sudo never attempt to prompt at all, so this only
    # succeeds if credentials are already cached or passwordless sudo is
    # configured - failing immediately otherwise, rather than risking a
    # silent, indefinite hang waiting for input that can never arrive.
    if ! sudo -n -v 2>/dev/null; then
      warn "No terminal available to prompt for a sudo password (this looks like a piped/non-interactive run), and no cached sudo credentials were found. Run 'sudo -v' yourself first, or run this script interactively instead."
      return 1
    fi
  fi
  return 0
}

interactive_wizard() {
  step "No options given - interactive setup. Press Enter to accept each default shown in brackets."
  echo

  local reply
  read -r -p "Python venv location [$VENV_DIR]: " reply
  [ -n "$reply" ] && VENV_DIR="$reply"

  read -r -p "Also install the KLayout integration script? [y/N]: " reply
  case "$reply" in [yY]*) WITH_KLAYOUT=1 ;; esac

  read -r -p "Set up AWS Palace now too? [Y/n]: " reply
  case "$reply" in
    [nN]*)
      SKIP_PALACE=1
      ;;
    *)
      read -r -p "Palace container version [$PALACE_VERSION]: " reply
      [ -n "$reply" ] && PALACE_VERSION="$reply"
      read -r -p "Cores for run_palace, blank = auto [auto]: " reply
      [ -n "$reply" ] && RUN_NP="$reply"
      ;;
  esac
  echo
}

[ "$NO_ARGS" = 1 ] && interactive_wizard

# ---------------------------------------------------------------------------
# Step 0: platform check
# ---------------------------------------------------------------------------

step "Checking your platform"

UNAME_S="$(uname -s)"
IS_WSL=0

case "$UNAME_S" in
  Linux)
    if grep -qi microsoft /proc/version 2>/dev/null || [ -n "${WSL_DISTRO_NAME:-}" ]; then
      IS_WSL=1
    fi
    ;;
  Darwin)
    fail "This script does not support macOS (Apptainer containers don't run
    natively on macOS). See doc/building-palace-spack.md for a from-source
    build there instead."
    ;;
  *)
    fail "Unsupported platform: $UNAME_S. This script is Linux-only (native
    or WSL2)."
    ;;
esac

if [ "$IS_WSL" = 1 ]; then
  ok "Linux under WSL2 (distro: ${WSL_DISTRO_NAME:-unknown})"
else
  ok "Native Linux ($(uname -m))"
fi

if [ -z "$RUN_NP" ]; then
  NPROC="$(nproc 2>/dev/null || echo 4)"
  if [ "$NPROC" -lt 4 ]; then
    RUN_NP=4
  else
    RUN_NP=$NPROC
  fi
fi

info "venv directory:    $VENV_DIR"
info "Palace container:  $PALACE_VERSION"
info "run_palace cores:  $RUN_NP  (override with --venv-dir / --palace-version / --np)"

# ---------------------------------------------------------------------------
# Step 1: system prerequisites (Python venv module, Qt runtime libs)
# ---------------------------------------------------------------------------

step "Checking system prerequisites"

command -v python3 >/dev/null 2>&1 || fail "python3 not found. Install Python 3.9+ first (e.g. 'sudo apt install python3 python3-venv' on Ubuntu/Debian), then re-run this script."
ok "python3 found: $(python3 --version)"

if ! command -v curl >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    step "Installing curl (needed to download helper scripts)"
    require_sudo || fail "Install curl yourself (as an account with sudo/root access): sudo apt-get update && sudo apt-get install -y curl - then re-run this script."
    sudo apt-get update -y || warn "apt-get update reported errors (continuing anyway)"
    sudo apt-get install -y curl || fail "Could not install curl automatically. Install it manually: sudo apt-get install -y curl - then re-run this script."
  else
    fail "curl not found and could not be auto-installed on this system (no apt-get found). Install it manually with your distro's package manager (it's needed to download helper scripts later in this script) and re-run."
  fi
fi
ok "curl found: $(curl --version | head -1)"

if ! python3 -c "import venv" >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    step "Installing python3-venv (needed to create the venv)"
    require_sudo || fail "Install python3-venv yourself (as an account with sudo/root access): sudo apt-get update && sudo apt-get install -y python3-venv - then re-run this script."
    sudo apt-get update -y || warn "apt-get update reported errors (continuing anyway)"
    sudo apt-get install -y python3-venv || fail "Could not install python3-venv automatically. Install it manually: sudo apt-get install -y python3-venv - then re-run this script."
  else
    fail "Python's 'venv' module is missing and could not be auto-installed on this system. Install it manually with your distro's package manager and re-run."
  fi
fi
ok "python3 'venv' module available"

if command -v apt-get >/dev/null 2>&1; then
  # These are the Qt/XCB runtime libraries setupEM's GUI needs on Linux
  # (see setupEM README, "Missing libraries on installation").
  QT_PKGS="libxcb-cursor0 libxcb-xinerama0 libxcb-xkb1 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-render0 libxcb-shape0 libxcb-shm0 libxcb-sync1 libxcb-xfixes0 libxcb-xinput0 libxcb-xv0 libxcb-util1 libxkbcommon-x11-0"
  MISSING_PKGS=""
  for pkg in $QT_PKGS; do
    dpkg -s "$pkg" >/dev/null 2>&1 || MISSING_PKGS="$MISSING_PKGS $pkg"
  done
  if [ -n "$MISSING_PKGS" ]; then
    step "Installing Qt runtime libraries needed by the setupEM GUI"
    info "Missing:$MISSING_PKGS"
    if confirm "Install these now with sudo apt-get?" && require_sudo; then
      sudo apt-get update -y || warn "apt-get update reported errors (continuing anyway)"
      # shellcheck disable=SC2086 # intentionally unquoted: MISSING_PKGS is a
      # space-separated list that must word-split into separate apt-get args
      if sudo apt-get install -y $MISSING_PKGS; then
        ok "Qt runtime libraries installed"
      else
        warn "apt-get install failed. Install these packages manually: sudo apt-get install -y$MISSING_PKGS"
      fi
    else
      warn "Skipped. setupEM's GUI may fail to start until these are installed: sudo apt-get install -y$MISSING_PKGS"
    fi
  else
    ok "Qt runtime libraries already present"
  fi
else
  warn "Not an apt-based system - please make sure the XCB/Qt runtime libraries
    setupEM needs are installed via your distro's package manager if the GUI
    fails to start (see setupEM README, 'Missing libraries on installation')."
fi

# ---------------------------------------------------------------------------
# Step 2: Python venv + setupEM (pulls in gds2palace + scikit-rf automatically)
# ---------------------------------------------------------------------------

step "Setting up the Python environment at $VENV_DIR"

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

step "Installing setupEM (this also installs gds2palace, gds_prepare_for_EM, scikit-rf, and every other Python dependency)"
pip install --upgrade setupEM --quiet
ok "setupEM installed: $(python -c 'import setupEM; print(getattr(setupEM, "__version__", "unknown"))' 2>/dev/null || echo 'installed')"
ok "gds2palace installed: $(python -c 'import gds2palace; print(getattr(gds2palace, "__version__", "unknown"))' 2>/dev/null || echo 'installed')"

# ---------------------------------------------------------------------------
# Step 3: put $VENV_DIR/bin on PATH for LOGIN shells
# ---------------------------------------------------------------------------

step "Adding $VENV_DIR/bin to PATH in ~/.profile"

PROFILE_LINE="export PATH=\"$VENV_DIR/bin:\$PATH\""
if grep -qF "$VENV_DIR/bin" "$HOME/.profile" 2>/dev/null; then
  ok "~/.profile already updated"
else
  echo "$PROFILE_LINE" >> "$HOME/.profile"
  ok "Added to ~/.profile (new terminals/logins pick this up automatically)"
fi

if [ "$WITH_KLAYOUT" = 1 ]; then
  step "Downloading KLayout integration script"
  mkdir -p "$HOME/scripts"
  curl -fsSL -o "$HOME/scripts/klayout_setupEM.py" "$SETUPEM_REPO_RAW/src/scripts/klayout_setupEM.py"
  ok "Saved to ~/scripts/klayout_setupEM.py - see setupEM README, 'KLayout Integration', to wire this into KLayout's Tools menu."
fi

# ---------------------------------------------------------------------------
# Step 4: AWS Palace solver itself (prebuilt Apptainer container)
# ---------------------------------------------------------------------------

PALACE_SIF=""   # absolute path to the .sif container image, set below if installed

if [ "$SKIP_PALACE" = 1 ]; then
  step "Skipping Palace solver installation (--skip-palace)"
  warn "You'll need to install Palace yourself and re-run with --skip-palace
    omitted (or edit $VENV_DIR/bin/run_palace by hand) before you can run
    simulations."
else
  step "Installing AWS Palace via prebuilt Apptainer container (version $PALACE_VERSION)"

  if ! command -v apptainer >/dev/null 2>&1; then
    if command -v apt-get >/dev/null 2>&1; then
      if confirm "Apptainer is not installed. Install it now via the Apptainer PPA?" && require_sudo; then
        sudo add-apt-repository -y ppa:apptainer/ppa
        sudo apt-get update -y
        sudo apt-get install -y apptainer
      else
        fail "Apptainer is required for this. Install it yourself (as an account
    with sudo/root access): sudo add-apt-repository -y ppa:apptainer/ppa &&
    sudo apt-get update && sudo apt-get install -y apptainer - or see
    (https://apptainer.org/docs/admin/main/installation.html) and re-run, or
    re-run with --skip-palace."
      fi
    else
      fail "Apptainer is required and could not be auto-installed on this
    system (no apt-get found). Install it manually
    (https://apptainer.org/docs/admin/main/installation.html) and re-run, or
    re-run with --skip-palace."
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
fi

# ---------------------------------------------------------------------------
# Step 5: helper scripts, with real paths already filled in
# ---------------------------------------------------------------------------

step "Installing helper scripts into $VENV_DIR/bin"

curl -fsSL -o "$VENV_DIR/bin/combine_extend_snp.py" "$GDS2PALACE_REPO_RAW/scripts/combine_extend_snp.py"
curl -fsSL -o "$VENV_DIR/bin/palace_summary.py" "$GDS2PALACE_REPO_RAW/scripts/palace_summary.py"
chmod +x "$VENV_DIR/bin/combine_extend_snp.py" "$VENV_DIR/bin/palace_summary.py"
ok "Downloaded combine_extend_snp.py and palace_summary.py"

cat > "$VENV_DIR/bin/combine_snp" <<EOF
#!/bin/sh
# Auto-generated by install_gds2palace.sh - converts Palace S-parameter
# output to Touchstone SnP format.
"$VENV_DIR/bin/python" "$VENV_DIR/bin/combine_extend_snp.py" "\$@"
EOF
chmod +x "$VENV_DIR/bin/combine_snp"
ok "Generated combine_snp"

if [ "$SKIP_PALACE" != 1 ] && [ -n "$PALACE_SIF" ]; then
  cat > "$VENV_DIR/bin/run_palace" <<EOF
#!/bin/bash
# Auto-generated by install_gds2palace.sh
# Runs Palace from the Apptainer container image at $PALACE_SIF
apptainer exec "$PALACE_SIF" palace -np ${RUN_NP} "\$1"
EOF
  chmod +x "$VENV_DIR/bin/run_palace"
  ok "Generated run_palace (using $RUN_NP cores by default)"
fi

# Also fetch the remote-simulation template for users who want to send jobs
# to a separate simulation server - left unconfigured (needs a real
# USERNAME/SERVER/TARGETDIR), since that's specific to each user's setup.
curl -fsSL -o "$VENV_DIR/bin/run_palace_remote.template" "$GDS2PALACE_REPO_RAW/scripts/run_palace_remote" 2>/dev/null || true
if [ -f "$VENV_DIR/bin/run_palace_remote.template" ]; then
  info "Also saved run_palace_remote.template - edit USERNAME/SERVER/TARGETDIR
    and rename to 'run_palace' if you want to simulate on a remote machine
    instead of locally."
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

step "Setup complete"

info "Everything below \$VENV_DIR/bin is already on your PATH in any NEW terminal (~/.profile)."
echo
echo "  To start working right now in THIS terminal, run:"
echo
echo "      source $VENV_DIR/bin/activate"
echo "      setupEM"
echo
if [ "$SKIP_PALACE" = 1 ]; then
  warn "Palace solver install was skipped - simulations won't run until that's set up."
fi
echo "  What was installed:"
echo "    - setupEM + gds2palace (Python GUI and workflow)              -> $VENV_DIR"
[ -n "$PALACE_SIF" ] && echo "    - AWS Palace (container)                                       -> $PALACE_SIF"
echo "    - run_palace / combine_snp (already pointing at the above)    -> $VENV_DIR/bin"
echo
echo "  Re-run this script any time - it will skip anything already done."
