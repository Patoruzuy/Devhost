#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE_PLIST="$ROOT_DIR/router/devhost-router.plist.tmpl"
DEST_PLIST="$HOME/Library/LaunchAgents/devhost.router.plist"
RESOLVER_DIR="/etc/resolver"
RESOLVER_FILE="$RESOLVER_DIR/localhost"

usage() {
  cat <<EOF
Usage: $0 [--dry-run] [--yes]

Interactive helper to install Devhost router on macOS.
It will:
 - pick or ask for a path to a uvicorn binary (venv or system)
 - generate a LaunchAgent plist from router/devhost-router.plist.tmpl
 - write a resolver file at /etc/resolver/localhost pointing to 127.0.0.1
 - optionally start dnsmasq via Homebrew services and load the LaunchAgent

Options:
  --dry-run   Print actions without making changes
  --yes       Non-interactive: assume yes for prompts and start dnsmasq if available
EOF
}

DRY_RUN=false
ASSUME_YES=false
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --yes|-y) ASSUME_YES=true ;;
    -h|--help) usage; exit 0 ;;
  esac
done

echo "Devhost macOS setup helper"
echo
if [ ! -f "$TEMPLATE_PLIST" ]; then
  echo "ERROR: template $TEMPLATE_PLIST not found." >&2
  exit 1
fi

detect_uvicorn() {
  candidates=("$ROOT_DIR/.venv/bin/uvicorn" "$ROOT_DIR/router/.venv/bin/uvicorn" "$ROOT_DIR/router/venv/bin/uvicorn" "/usr/local/bin/uvicorn" "/opt/homebrew/bin/uvicorn")
  for c in "${candidates[@]}"; do
    if [ -x "$c" ]; then
      echo "$c" && return 0
    fi
  done
  if command -v uvicorn >/dev/null 2>&1; then
    command -v uvicorn
    return 0
  fi
  return 1
}

echo "Default user: $USER"
if $ASSUME_YES; then
  TARGET_USER="$USER"
else
  read -r -p "Enter target macOS username (press Enter to accept '$USER'): " TARGET_USER
  if [ -z "$TARGET_USER" ]; then TARGET_USER="$USER"; fi
fi

UVICORN_PATH=""
if uvp=$(detect_uvicorn); then
  echo "Found uvicorn at: $uvp"
  if $ASSUME_YES; then
    UVICORN_PATH="$uvp"
  else
    read -r -p "Use this uvicorn binary? [Y/n] " yn
    yn=${yn:-Y}
    if [[ "$yn" =~ ^[Yy]$ ]]; then
      UVICORN_PATH="$uvp"
    fi
  fi
fi

if [ -z "$UVICORN_PATH" ]; then
  if $ASSUME_YES; then
    UVICORN_PATH="python3 -m uvicorn"
  else
    read -r -p "Enter full path to uvicorn (or leave empty to use 'python3 -m uvicorn'): " UVICORN_PATH
    if [ -z "$UVICORN_PATH" ]; then
      UVICORN_PATH="python3 -m uvicorn"
    fi
  fi
fi

echo
echo "Summary of actions to perform:"
echo " - Write LaunchAgent: $DEST_PLIST (from template $TEMPLATE_PLIST)"
echo " - Ensure resolver: $RESOLVER_FILE -> nameserver 127.0.0.1"
echo " - Optionally start dnsmasq via Homebrew and load the LaunchAgent"
echo
if $ASSUME_YES; then
  proceed=Y
else
  read -r -p "Proceed? [y/N] " proceed
  proceed=${proceed:-N}
fi
if [[ ! "$proceed" =~ ^[Yy]$ ]]; then
  echo "Aborted by user."; exit 0
fi

generate_plist() {
  tmpfile=$(mktemp)
  sed "s|{{USER}}|$TARGET_USER|g; s|{{VENV_BIN}}|$UVICORN_PATH|g" "$TEMPLATE_PLIST" > "$tmpfile"
  echo "$tmpfile"
}

if $DRY_RUN; then
  echo "DRY RUN: would generate plist from $TEMPLATE_PLIST replacing {{USER}} and {{VENV_BIN}}"
  echo "DRY RUN: suggested uvicorn: $UVICORN_PATH"
  exit 0
fi

PLIST_TMP=$(generate_plist)
mkdir -p "$(dirname "$DEST_PLIST")"
echo "Installing LaunchAgent to $DEST_PLIST (backup if exists)"
if [ -f "$DEST_PLIST" ]; then
  cp -v "$DEST_PLIST" "$DEST_PLIST.$(date +%s).bak"
fi
cp -v "$PLIST_TMP" "$DEST_PLIST"
chmod 0644 "$DEST_PLIST"

echo "Creating resolver at $RESOLVER_FILE"
if [ ! -d "$RESOLVER_DIR" ]; then
  echo "Creating $RESOLVER_DIR (requires sudo)"; sudo mkdir -p "$RESOLVER_DIR"
fi
echo "nameserver 127.0.0.1" | sudo tee "$RESOLVER_FILE" >/dev/null

echo
if $ASSUME_YES; then
  start_dns=Y
else
  read -r -p "Start dnsmasq via Homebrew services now? [y/N] " start_dns
  start_dns=${start_dns:-N}
fi
if [[ "$start_dns" =~ ^[Yy]$ ]]; then
  if command -v brew >/dev/null 2>&1; then
    echo "Starting dnsmasq (brew services start dnsmasq)"
    brew services start dnsmasq || sudo brew services start dnsmasq || true
  else
    echo "brew not found; please install dnsmasq with Homebrew: brew install dnsmasq" >&2
  fi
fi

echo "Loading LaunchAgent"
launchctl unload "$DEST_PLIST" 2>/dev/null || true
launchctl load -w "$DEST_PLIST"

echo
echo "Setup complete. Check router health with: curl http://127.0.0.1:5555/health"
echo "Logs: tail -f /tmp/devhost-router.log /tmp/devhost-router.err"
echo "If you wish to edit the created plist, it is at: $DEST_PLIST"

exit 0
