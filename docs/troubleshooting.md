# Troubleshooting

## “No module named 'setuptools'” / PEP 517 backend unavailable

If you see errors like:

- `ModuleNotFoundError: No module named 'setuptools'`
- `BackendUnavailable: Cannot import 'setuptools.build_meta'`

Fix (inside your venv):

```bash
python -m pip install --upgrade pip setuptools wheel
```

Tip: avoid `--no-build-isolation` unless you know why you need it.

## Router not responding on `:7777`

```bash
devhost status
devhost start
devhost logs --follow
```

If port `7777` is taken:
- stop the conflicting process, or
- change `proxy.gateway.listen` in `~/.devhost/state.yml` (then restart `devhost start`).

## System mode: ports 80/443 in use

```bash
devhost proxy status
devhost doctor
```

If another process owns port 80/443, stop it or switch to External mode.

## DNS: `api.<domain>` does not resolve

For `localhost`, this usually works without extra setup.

For custom domains:
- Configure DNS on your network.
- Use hosts file entries (`devhost hosts sync` on Windows as Administrator).
- Run a local DNS resolver (e.g. `dnsmasq`).

## Windows: "Permission Denied" when editing hosts

Editing the system hosts file requires Administrator privileges.

1. Close your terminal.
2. Right-click your terminal (PowerShell/CMD) and select **Run as Administrator**.
3. Run `devhost hosts sync` again.

## WSL2 Connectivity

If you run your app in WSL2 and Devhost in Windows (or vice versa):
- Browsers on Windows can hit `myapp.localhost:7777` if Devhost is running on Windows.
- If Devhost is in WSL2 and you want to hit it from Windows, make sure you use `127.0.0.1` and that WSL2 port forwarding is working.
- Prefer running both in the same environment (either both in WSL2 or both in Windows) for the most stable experience.

## TUI dashboard looks distorted

If the TUI dashboard has broken lines or strange characters:
- Make sure your terminal supports UTF-8.
- Use a modern terminal like **Windows Terminal**, **iTerm2**, or **Kitty**.
- Use a Nerd Font for better icon support.

## WebSocket "Upgrade Failed"

If your real-time app fails to establish a WebSocket connection:
- Check `devhost logs` to see if the router is rejecting the request.
- Ensure your upstream app is actually listening for WebSockets on the registered port.
- If using `https`, ensure your certificates are valid.

## TUI import error

If `devhost dashboard` fails to import Textual:

```bash
pip install devhost[tui]
```

