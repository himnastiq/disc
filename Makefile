.PHONY: setup data train train-fast eval api web test lint check gates progress clean demo

PYTHON := e:\discover\.venv\Scripts\python.exe
PIP := e:\discover\.venv\Scripts\pip.exe
PYTEST := e:\discover\.venv\Scripts\pytest.exe
RUFF := e:\discover\.venv\Scripts\ruff.exe
MYPY := e:\discover\.venv\Scripts\mypy.exe
UVICORN := e:\discover\.venv\Scripts\uvicorn.exe
TYPE ?=

# ---- Setup ----
setup:
	$(PIP) install -e "backend/.[core,dev]"
	@echo "Backend setup complete."
	@if [ -d frontend/node_modules ]; then echo "Frontend already set up."; \
	else echo "Run 'cd frontend && npm install' for frontend setup."; fi

# ---- Data ----
data:
ifdef TYPE
	$(PYTHON) -m engine.train --type $(TYPE) --download-only
else
	$(PYTHON) backend/scripts/fetch_data.py
endif

# ---- Training ----
train:
ifdef TYPE
	cd backend && $(PYTHON) -m engine.train --type $(TYPE)
else
	cd backend && $(PYTHON) -m engine.train --type movies
	cd backend && $(PYTHON) -m engine.train --type products
	cd backend && $(PYTHON) -m engine.train --type articles
endif

train-fast:
ifdef TYPE
	cd backend && $(PYTHON) -m engine.train --type $(TYPE) --fast
else
	cd backend && $(PYTHON) -m engine.train --type movies --fast
	cd backend && $(PYTHON) -m engine.train --type products --fast
	cd backend && $(PYTHON) -m engine.train --type articles --fast
endif

# ---- Evaluation ----
eval:
	$(PYTHON) tools/make_results.py

# ---- Servers ----
api:
	cd backend && $(UVICORN) api.main:app --reload --host 0.0.0.0 --port 8000

web:
	cd frontend && npm run dev

demo:
	@echo "Starting Discovery Engine demo..."
	@echo "1. Start the API: make api"
	@echo "2. Start the frontend: make web"
	@echo "3. Open http://localhost:3000"

# ---- Quality ----
test:
	cd backend && $(PYTEST) tests/ -v --tb=short

lint:
	cd backend && $(RUFF) check .
	cd backend && $(RUFF) format --check .
	cd backend && $(MYPY) engine/ api/

check: lint test
	@echo "All checks passed."

gates: check
	@echo "Running extended gate checks..."
	cd backend && $(PYTEST) tests/ -v --tb=short -m "slow or integration"
	@echo "Gates complete."

# ---- Utilities ----
progress:
	$(PYTHON) tools/progress.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/*.egg-info 2>/dev/null || true
	@echo "Cleaned."
