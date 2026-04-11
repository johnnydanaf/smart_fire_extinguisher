VENV_DIR := $(abspath ../fyp_env)
VENV := $(VENV_DIR)
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

$(VENV):
	@echo "Creating virtual environment at $(VENV_DIR)..."
	python3 -m venv $(VENV)
	@echo "✅ Virtual environment created"

check_venv:
	@if [ ! -d "$(VENV)" ]; then \
		echo "❌ Virtual environment not found. Run 'make install-dev' first."; \
		exit 1; \
	fi

install-dev: $(VENV)
	@echo "Installing dev dependencies (no Pi hardware)..."
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt
	@echo "✅ Dev installation complete"
	@echo "Activate with: source ../fyp_env/bin/activate"

install-pi: $(VENV)
	@echo "Installing Pi dependencies..."
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-pi.txt
	@echo "✅ Pi installation complete"

lint: check_venv
	$(PYTHON) -m flake8

run: check_venv
	$(PYTHON) src/main.py

clean:
	@echo "Cleaning cache files..."
	rm -rf __pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Clean complete"

fclean: clean
	@echo "Removing virtual environment..."
	rm -rf $(VENV)
	@echo "✅ Full clean complete"

re: fclean install-dev

help:
	@echo "Available commands:"
	@echo "  make install-dev  - Create venv and install dev dependencies (Linux)"
	@echo "  make install-pi   - Create venv and install Pi dependencies"
	@echo "  make lint         - Run flake8 linter"
	@echo "  make run          - Run main.py"
	@echo "  make clean        - Remove cache files only"
	@echo "  make fclean       - Delete virtual environment"
	@echo "  make re           - Full rebuild (fclean + install-dev)"