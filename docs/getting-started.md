# Getting Started with Devhost

Welcome! Devhost is designed to be safe-by-default and easy to start with. This guide will walk you through your first 5 minutes with Devhost.

## 1. Quick Installation

```bash
pip install devhost
```

*(Optional but recommended: `pip install devhost[tui]` if you want the interactive dashboard.)*

## 2. Start the Gateway

Devhost defaults to **Gateway Mode**, which runs a single router on port `7777`. This requires no administrator/root permissions.

```bash
devhost start
```

## 3. Register Your First App

Let's say you have a web app running on `localhost:3000`. You want to reach it at `http://web.localhost:7777`.

```bash
devhost add web 3000
```

## 4. Open it!

```bash
devhost open web
```

Your browser will open `http://web.localhost:7777`.

## 5. View Your Routes

```bash
devhost list
```

## Next Steps

- **Portless URLs**: Ready for the next level? Upgrade to **System Mode** to use `http://web.localhost` (no port).
  ```bash
  devhost proxy upgrade --to system
  ```
  *(Requires one-time admin permission to bind port 80/443.)*

- **Dashboard**: Try the interactive TUI if you installed the `[tui]` extra:
  ```bash
  devhost dashboard
  ```

- **Integration**: Learn how to integrate Devhost into your [Flask/FastAPI/Django](../examples/README.md) apps automatically.

---

See also:
- [Installation Guide](installation.md)
- [Proxy Modes](modes.md)
- [CLI Reference](cli.md)
