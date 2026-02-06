# Installation Guide

Devhost is a Python-based tool. It works on Windows, macOS, and Linux.

## Prerequisites

- **Python 3.10 or higher**
- **pip** (Python package manager)

## 1. Core Installation

Install the core package from PyPI:

```bash
pip install devhost
```

## 2. Optional Extras

Devhost offers several extras for specific workflows:

| Extra | Description |
|-------|-------------|
| `[tui]` | Interactive terminal dashboard (`devhost dashboard`) |
| `[qr]` | QR code generation for mobile access |
| `[fastapi]` | Helpers for FastAPI integration |
| `[flask]` | Helpers for Flask integration |
| `[django]` | Helpers for Django integration |
| `[dev]` | Testing and linting tools (for contributors) |

To install multiple extras:
```bash
pip install "devhost[tui,qr,fastapi]"
```

## 3. System Proxy (Optional)

If you plan to use **System Mode** (portless URLs on 80/443), you need **Caddy** installed on your system.

### Windows
The easiest way is via [WinGet](https://github.com/microsoft/winget-cli):
```powershell
winget install CaddyServer.Caddy
```
Or download the binary from [caddyserver.com](https://caddyserver.com/download).

### macOS
Using [Homebrew](https://brew.sh/):
```bash
brew install caddy
```

### Linux
Follow the [official installation instructions](https://caddyserver.com/docs/install#debian-ubuntu-raspbian) for your distribution.

## 4. Verification

Run the diagnostics command to ensure everything is set up correctly:

```bash
devhost doctor
```

If you are on Windows and intend to use custom domains (other than `.localhost`), make sure you run the doctor as Administrator once to verify hosts file access.
