# Devhost Development Makefile
# Modern Python development workflow with automated venv setup

VENV = .venv
ifeq ($(OS),Windows_NT)
	PYTHON = $(VENV)/Scripts/python.exe
	PIP = $(VENV)/Scripts/pip.exe
	ACTIVATE = $(VENV)/Scripts/activate
else
	PYTHON = $(VENV)/bin/python
	PIP = $(VENV)/bin/pip
	ACTIVATE = $(VENV)/bin/activate
endif

.PHONY: help install install-dev install-all test test-security lint format clean start dashboard \
        completions-zsh completions-bash venv

help:
	@echo "Devhost Development Commands:"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install          - Create venv and install base package"
	@echo "  make install-dev      - Install with dev dependencies (pytest, ruff)"
	@echo "  make install-all      - Install with all extras (dev, tui, qr)"
	@echo ""
	@echo "Development:"
	@echo "  make test             - Run all tests"
	@echo "  make test-security    - Run security tests only"
	@echo "  make lint             - Check code with ruff"
	@echo "  make format           - Auto-format code with ruff"
	@echo "  make clean            - Remove venv and build artifacts"
	@echo ""
	@echo "Runtime:"
	@echo "  make start            - Start devhost router"
	@echo "  make dashboard        - Launch TUI dashboard"
	@echo ""
	@echo "Shell Completions:"
	@echo "  make completions-zsh  - Install zsh completions"
	@echo "  make completions-bash - Install bash completions"

# Create virtual environment if it doesn't exist
$(VENV):
	python -m venv $(VENV)
	$(PIP) install --upgrade pip setuptools wheel

# Base installation
install: $(VENV)
	$(PIP) install -e .

# Install with dev dependencies
install-dev: $(VENV)
	$(PIP) install -e ".[dev]"

# Install with all extras
install-all: $(VENV)
	$(PIP) install -e ".[dev,all]"

# Run all tests
test: install-dev
	$(PYTHON) -m unittest discover -v

# Run security tests only
test-security: install-dev
	$(PYTHON) -m unittest discover -s tests -p "test_security_*.py" -v

# Lint with ruff
lint: install-dev
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

# Auto-format with ruff
format: install-dev
	$(PYTHON) -m ruff format .

# Start router (requires installation)
start:
	$(PYTHON) -m devhost_cli.main start

# Launch TUI dashboard
dashboard: install-all
	$(PYTHON) -m devhost_cli.main dashboard

# Clean build artifacts and venv
clean:
	rm -rf $(VENV)
	rm -rf *.egg-info
	rm -rf dist build
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Install zsh completions
completions-zsh:
	mkdir -p $(HOME)/.zsh/completions
	cp completions/_devhost $(HOME)/.zsh/completions/_devhost
	@echo "Zsh completions installed. Add to .zshrc:"
	@echo "  fpath=($(HOME)/.zsh/completions \$$fpath)"
	@echo "  autoload -U compinit && compinit"

# Install bash completions
completions-bash:
	mkdir -p $(HOME)/.bash_completion.d
	cp completions/devhost.bash $(HOME)/.bash_completion.d/devhost
	@echo "Bash completions installed. Add to .bashrc:"
	@echo "  source $(HOME)/.bash_completion.d/devhost"
