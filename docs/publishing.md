# Publishing & Releases

This is a pragmatic checklist for publishing Devhost to GitHub and PyPI.

## GitHub

- Ensure `README.md` reflects the current CLI and behavior.
- Keep `CHANGELOG.md` updated with user-visible changes.
- Tag releases consistently (e.g. `v3.0.0-alpha.1`).

## PyPI

### Pre-flight

- Confirm `pyproject.toml` has the right metadata (`name`, `version`, `readme`, classifiers, URLs).
- Verify `README.md` renders correctly on PyPI (avoid relative links where possible).

### Build

```bash
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*
```

### Upload

TestPyPI first:

```bash
python -m twine upload --repository testpypi dist/*
```

Then PyPI:

```bash
python -m twine upload dist/*
```

### Sanity check

In a clean venv:

```bash
pip install devhost
devhost --help
devhost start
devhost add api 8000
devhost open api
```

