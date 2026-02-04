VENV=router/venv
ifeq ($(OS),Windows_NT)
PY=$(VENV)/Scripts/python
else
PY=$(VENV)/bin/python
endif

.PHONY: venv install start test docker-up docker-build lint format dashboard tunnel proxy completions-zsh completions-bash windows-setup help

venv:
	python -m venv $(VENV)

install: venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r router/requirements.txt

start: install
	cd router && $(PY) -m uvicorn app:app --host 127.0.0.1 --port 7777 --reload

test: install
	$(PY) -m py_compile router/*.py
	$(PY) -m unittest discover -s tests -p "test_*.py"

docker-build:
	docker compose build

docker-up:
	docker compose up --build -d

lint: install
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

format: install
	$(PY) -m ruff format .

dashboard:
	python -m devhost_cli.main dashboard

tunnel:
	python -m devhost_cli.main tunnel status

proxy:
	python -m devhost_cli.main proxy status

devhost-url:
	./devhost url

devhost-open:
	./devhost open

devhost-list:
	./devhost list

devhost-list-json:
	./devhost list --json

devhost-validate:
	./devhost validate

devhost-export-caddy:
	./devhost export caddy

devhost-edit:
	./devhost edit

devhost-resolve:
	./devhost resolve

devhost-doctor:
	./devhost doctor

devhost-info:
	./devhost info

devhost-status-json:
	./devhost status --json

completions-zsh:
	mkdir -p $(HOME)/.zsh/completions
	cp completions/_devhost $(HOME)/.zsh/completions/_devhost
	@echo "Add to .zshrc if needed: fpath=($(HOME)/.zsh/completions $$fpath) && autoload -U compinit && compinit"

completions-bash:
	mkdir -p $(HOME)/.bash_completion.d
	cp completions/devhost.bash $(HOME)/.bash_completion.d/devhost
	@echo "Add to .bashrc if needed: source $(HOME)/.bash_completion.d/devhost"

windows-setup:
	powershell -ExecutionPolicy Bypass -File scripts\\setup-windows.ps1

help:
	@echo "Available targets: venv install start test docker-build docker-up lint format dashboard tunnel proxy completions-zsh completions-bash windows-setup"
