#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "[+] Installing dependencies..."

# Install Caddy if not already installed
if ! command -v caddy &> /dev/null; then
    echo "[+] Installing Caddy..."
    sudo apt-get update
    sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl gnupg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
    sudo apt-get update
    sudo apt-get install -y caddy
fi

# Setup Python virtual environment for router
echo "[+] Setting up router..."
cd "$ROOT_DIR/router"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
cd "$ROOT_DIR"

# Install dnsmasq if not present
if ! command -v dnsmasq &> /dev/null; then
    echo "[+] Installing dnsmasq..."
    sudo apt-get install -y dnsmasq
fi

# Configure dnsmasq for *.localhost
echo "[+] Configuring dnsmasq..."
DNSMASQ_CONF_DIR="/etc/dnsmasq.d"
DNSMASQ_CONF_FILE="$DNSMASQ_CONF_DIR/devhost.conf"
DNSMASQ_PORT=53
DNSMASQ_LISTEN_ADDR="127.0.0.1"

if command -v ss >/dev/null 2>&1 && ss -lntup 2>/dev/null | grep -qE '[:.]53\\s'; then
    echo "[!] Port 53 is already in use. Configuring dnsmasq on 127.0.0.1:5353."
    DNSMASQ_PORT=5353
fi

if [ -d "$DNSMASQ_CONF_DIR" ]; then
    cat <<EOF | sudo tee "$DNSMASQ_CONF_FILE" >/dev/null
address=/localhost/127.0.0.1
listen-address=$DNSMASQ_LISTEN_ADDR
bind-interfaces
port=$DNSMASQ_PORT
EOF
else
    if ! grep -q '^address=/localhost/127.0.0.1$' /etc/dnsmasq.conf; then
        echo 'address=/localhost/127.0.0.1' | sudo tee -a /etc/dnsmasq.conf >/dev/null
    fi
    if ! grep -q '^listen-address=127.0.0.1$' /etc/dnsmasq.conf; then
        echo 'listen-address=127.0.0.1' | sudo tee -a /etc/dnsmasq.conf >/dev/null
    fi
    if ! grep -q '^bind-interfaces$' /etc/dnsmasq.conf; then
        echo 'bind-interfaces' | sudo tee -a /etc/dnsmasq.conf >/dev/null
    fi
    if ! grep -q '^port=' /etc/dnsmasq.conf; then
        echo "port=$DNSMASQ_PORT" | sudo tee -a /etc/dnsmasq.conf >/dev/null
    fi
fi

if command -v systemctl &> /dev/null; then
    sudo systemctl restart dnsmasq || true
fi

if [ "$DNSMASQ_PORT" -ne 53 ]; then
    if command -v systemctl &> /dev/null && systemctl is-active --quiet systemd-resolved; then
        echo "[+] Configuring systemd-resolved to forward *.localhost to 127.0.0.1:$DNSMASQ_PORT"
        RESOLVED_DROPIN_DIR="/etc/systemd/resolved.conf.d"
        RESOLVED_DROPIN_FILE="$RESOLVED_DROPIN_DIR/devhost.conf"
        sudo mkdir -p "$RESOLVED_DROPIN_DIR"
        cat <<EOF | sudo tee "$RESOLVED_DROPIN_FILE" >/dev/null
[Resolve]
DNS=127.0.0.1#$DNSMASQ_PORT
Domains=~localhost
EOF
        sudo systemctl restart systemd-resolved
    else
        echo "[!] systemd-resolved not active. Port 53 is in use, so dnsmasq is on $DNSMASQ_PORT."
        echo "    You may need to free port 53 or configure your resolver to use 127.0.0.1#$DNSMASQ_PORT for *.localhost."
    fi
fi

# Configure resolv.conf (informational only)
echo "[!] About to update DNS resolver configuration. This can interfere with system DNS."
echo "If you're on Debian/Ubuntu with systemd-resolved, run:"
echo "  sudo ln -sf /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf"
echo "and ensure 127.0.0.1 is present, or add a nameserver entry manually if appropriate."
echo "To let this script attempt a safe append, uncomment the command below after reviewing it."
# sudo sed -i '1inameserver 127.0.0.1' /etc/resolv.conf

# Set up CLI tool
echo "[+] Installing devhost CLI..."
chmod +x "$ROOT_DIR/devhost"
sudo ln -sf "$ROOT_DIR/devhost" /usr/local/bin/devhost

# Create initial files if missing
if [ ! -f "$ROOT_DIR/devhost.json" ]; then
    echo '{}' > "$ROOT_DIR/devhost.json"
fi
if [ ! -f "$ROOT_DIR/caddy/Caddyfile" ]; then
    cp "$ROOT_DIR/caddy/Caddyfile.template" "$ROOT_DIR/caddy/Caddyfile"
fi

echo "[+] Done! You can now run 'devhost add <name> <port>'"
