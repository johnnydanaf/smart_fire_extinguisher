# Virtual environment location (one level above repo)
VENV_DIR := $(abspath ../fyp_env)
VENV := $(VENV_DIR)
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

# Create venv if it doesn't exist
$(VENV):
	@echo "Creating virtual environment at $(VENV_DIR)..."
	python3 -m venv $(VENV)
	@echo "✅ Virtual environment created"

# Check if venv exists and activate it
check_venv:
	@if [ ! -d "$(VENV)" ]; then \
		echo "❌ Virtual environment not found. Run 'make install' first."; \
		exit 1; \
	fi

# Install dependencies inside venv
install: $(VENV)
	@echo "Installing dependencies..."
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "✅ Installation complete"
	@echo "Activate with: source ../fyp_env/bin/activate"

# Run lint inside venv
lint: check_venv
	$(PYTHON) -m flake8

# Run main inside venv
run: check_venv
	$(PYTHON) src/main.py

# Clean cache only
clean:
	@echo "Cleaning cache files..."
	rm -rf __pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Clean complete"

# Full clean (delete venv)
fclean: clean
	@echo "Removing virtual environment..."
	rm -rf $(VENV)
	@echo "✅ Full clean complete"

# Reinstall everything
re: fclean install

# Show help
help:
	@echo "Available commands:"
	@echo "  make install  - Create venv (if missing) and install requirements"
	@echo "  make lint     - Run flake8 linter"
	@echo "  make run      - Run main.py"
	@echo "  make clean    - Remove cache files only"
	@echo "  make fclean   - Delete virtual environment"
	@echo "  make re       - Full rebuild (fclean + install)"