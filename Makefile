VENV=router/venv
ifeq ($(OS),Windows_NT)
PY=$(VENV)/Scripts/python
else
PY=$(VENV)/bin/python
endif

.PHONY: venv install start test docker-up docker-build lint help

venv:
	python -m venv $(VENV)

install: venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r router/requirements.txt

start: install
	cd router && $(PY) -m uvicorn app:app --host 127.0.0.1 --port 5555 --reload

test: install
	$(PY) -m py_compile router/*.py

docker-build:
	docker compose build

docker-up:
	docker compose up --build -d

lint: install
	-$(PY) -m ruff check .

help:
	@echo "Available targets: venv install start test docker-build docker-up lint"
