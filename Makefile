VENV = fyp_env
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip

# Create venv if it doesn't exist
$(VENV):
	python3 -m venv $(VENV)

# Install dependencies inside venv
install: $(VENV)
	$(PIP) install -r requirements.txt

# Run lint inside venv
lint: $(VENV)
	$(PYTHON) -m flake8

# Run main inside venv (will use src/main.py when we have it)
run: $(VENV)
	$(PYTHON) src/main.py

# Clean cache only
clean:
	rm -rf __pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Full clean (delete venv)
fclean: clean
	rm -rf $(VENV)

# Reinstall everything
re: fclean install