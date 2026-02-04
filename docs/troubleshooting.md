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
- configure DNS on your network, or
- use hosts file entries (`devhost hosts sync` on Windows), or
- run a local DNS resolver.

## TUI import error

If `devhost dashboard` fails to import Textual:

```bash
pip install devhost[tui]
```

