VENV = fyp_env
PIP = $(VENV)/bin/pip

install:
	python3 -m venv $(VENV)
	$(PIP) install -r requirements.txt

lint:
	$(VENV)/bin/flake8