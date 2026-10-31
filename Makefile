.PHONY: setup data train train-fast eval api web test lint check gates progress clean demo

PYTHON ?= python3
PIP ?= pip
TYPE ?=

# ---- Setup ----
setup:
	$(PIP) install -e "backend/.[core,dev]"
	@echo "Backend setup complete."
	@if [ -d frontend/node_modules ]; then echo "Frontend already set up."; \
	else echo "Run 'cd frontend && npm ci' for reproducible frontend setup."; fi

# ---- Data ----
data:
ifdef TYPE
	$(PYTHON) backend/scripts/fetch_data.py --type $(TYPE)
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
	cd backend && $(PYTHON) -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

web:
	@if [ -d frontend ]; then cd frontend && npm run dev; \
	else echo "Frontend not yet created (Phase 8)."; exit 1; fi

demo:
	$(PYTHON) tools/demo.py

demo-stop:
	$(PYTHON) tools/demo.py --stop

screenshots:
	$(PYTHON) tools/capture_screenshots.py

# ---- Quality ----
test:
	cd backend && $(PYTHON) -m pytest tests/ -v --tb=short

lint:
	cd backend && $(PYTHON) -m ruff check .
	cd backend && $(PYTHON) -m ruff format --check .
	cd backend && $(PYTHON) -m mypy engine/ api/

check:
	$(PYTHON) tools/check.py

gates: check
	@echo "Running extended gate checks..."
	cd backend && $(PYTHON) -m pytest tests/ -v --tb=short -m "slow or integration"
	@echo "Gates complete."

# ---- Utilities ----
progress:
	$(PYTHON) tools/progress.py

docs:
	$(PYTHON) tools/make_docs.py

docs-check:
	$(PYTHON) tools/make_docs.py --check
	$(PYTHON) tools/check_docs.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/*.egg-info 2>/dev/null || true
	@echo "Cleaned."
