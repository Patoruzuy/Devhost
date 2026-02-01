# macOS Setup for Devhost

> **⚠️ Recommended**: Use the automated installer for easier setup:
> ```bash
> python install.py --macos --yes --start-dns --install-completions
> ```
> See the main [README.md](../README.md) for installation options and details.

---

## Manual Installation (Advanced)

This document describes the manual setup process for advanced users who want to understand how Devhost works under the hood.

### Install dnsmasq

```bash
brew install dnsmasq
```

Configure dnsmasq to resolve `*.localhost` to 127.0.0.1

Note: use `tee` with `sudo` when writing to files that require root.

```bash
echo 'address=/.localhost/127.0.0.1' | sudo tee -a /opt/homebrew/etc/dnsmasq.conf
```

Start dnsmasq as a service

```bash
sudo brew services start dnsmasq
```

Create a resolver so macOS will query the local dnsmasq for `.localhost` names

```bash
sudo mkdir -p /etc/resolver
echo 'nameserver 127.0.0.1' | sudo tee /etc/resolver/localhost
# verify
dig @127.0.0.1 hello.localhost
```

Notes about ports and system DNS

- dnsmasq by default listens on port 53; do not change to port 5353 (mDNS) unless you have a specific reason.
- `networksetup -setdnsservers` will overwrite the DNS servers for a network service; prefer the resolver file approach above which targets a specific domain.

Install and run the router on boot (LaunchAgent)

1. Edit `router/devhost-router.plist.tmpl`, replace `{{USER}}` and `{{VENV_BIN}}` with your macOS username and path to the venv `uvicorn` binary (or to system `uvicorn`).

2. Copy to your LaunchAgents folder and load it:

```bash
cp router/devhost-router.plist.tmpl ~/Library/LaunchAgents/devhost.router.plist
launchctl load ~/Library/LaunchAgents/devhost.router.plist
```

3. To stop/unload:

```bash
launchctl unload ~/Library/LaunchAgents/devhost.router.plist
```

Developer notes

- For development you can run the router directly with reload support:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --host 127.0.0.1 --port 5555
```

- If you prefer a managed approach, use the provided `devhost-router.plist.tmpl` to point at the venv `uvicorn` binary (example: `/Users/you/devhost/.venv/bin/uvicorn`).

Security & safety

- Inspect `caddy/Caddyfile` before reloading system Caddy.
- Avoid globally changing system DNS unless you understand the effects; the `/etc/resolver/localhost` method is scoped and safer.

Troubleshooting

- Check dnsmasq logs: `tail -f /usr/local/var/log/dnsmasq.log` (path may vary by Homebrew prefix).
- Verify resolver: `scutil --dns` and `dig @127.0.0.1 hello.localhost`.

That's it — after the router is running and dnsmasq is configured you can run `devhost add <name> <port>` and open `https://<name>.localhost`.