
---

### `install.sh`
```bash
#!/bin/bash

set -e

echo "[+] Installing dependencies..."

# Install caddy if not already installed
if ! command -v caddy &> /dev/null; then
    echo "[+] Installing Caddy..."
    sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo apt-key add -
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
    sudo apt update
    sudo apt install caddy
fi

# Setup Python virtual environment for router
echo "[+] Setting up router..."
cd router
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
cd ..

# Install dnsmasq if not present
if ! command -v dnsmasq &> /dev/null; then
    echo "[+] Installing dnsmasq..."
    sudo apt install dnsmasq
fi

# Configure dnsmasq
echo "[+] Configuring dnsmasq..."
echo 'port=5353' | sudo tee -a /etc/dnsmasq.conf
echo 'address=/localhost/127.0.0.1' | sudo tee -a /etc/dnsmasq.conf
sudo systemctl restart dnsmasq

# Configure resolv.conf
echo "[!] About to update DNS resolver configuration. This can interfere with system DNS." 
echo "If you're on Debian/Ubuntu with systemd-resolved, run:"
echo "  sudo ln -sf /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf"
echo "and ensure 127.0.0.1 is present, or add a nameserver entry manually if appropriate."
echo "To let this script attempt a safe append, uncomment the command below after reviewing it."
# sudo sed -i '1inameserver 127.0.0.1' /etc/resolv.conf

# Set up CLI tool
echo "[+] Installing devhost CLI..."
chmod +x devhost
sudo ln -sf "$PWD/devhost" /usr/local/bin/devhost

# Create initial files
touch devhost.json
cp caddy/Caddyfile.template caddy/Caddyfile

echo "[+] Done! You can now run 'devhost add <name> <port>'"
