ifeq ($(OS),Windows_NT)
    PYTHON := python
    BIN_DIR := Scripts
else
    PYTHON := python3
    BIN_DIR := bin
endif

VENV_BIN := backend/.venv/$(BIN_DIR)

.DEFAULT_GOAL := help

.PHONY: help install start smoke format test verify setup env scan-vulns install-tools

help: ## List available commands
	@awk 'BEGIN { FS = ":.*## " } /^[a-zA-Z0-9_.-]+:.*## / { printf "  %-18s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

setup: env ## Create local environment files
	@echo "Setup complete! Run 'make install' to set up dependencies or 'make start' for Docker."

env: ## Copy example environment files when missing
	@echo "Setting up environment files from examples..."
	@test -f backend/.env || cp backend/.env.example backend/.env && echo "Created backend/.env" || echo "backend/.env already exists"
	@test -f frontend/.env || cp frontend/.env.example frontend/.env && echo "Created frontend/.env" || echo "frontend/.env already exists"
	@test -f docker-compose.override.yml || cp docker-compose.override.yml.example docker-compose.override.yml && echo "Created docker-compose.override.yml" || echo "docker-compose.override.yml already exists"

install: ## Install backend and frontend dependencies
	@echo "Installing backend dependencies..."
	$(PYTHON) -m venv backend/.venv
	$(VENV_BIN)/pip install -r backend/requirements.txt
	@echo "Installing frontend dependencies..."
	cd frontend && npm install

start: ## Start the development stack with Docker
	@echo "Starting development stack..."
	docker compose up --build

smoke: ## Start the Docker stack, check service endpoints, then tear it down
	bash scripts/compose_smoke.sh

format: ## Format backend and frontend code
	@echo "Formatting backend code..."
	$(VENV_BIN)/black backend/ || black backend/
	$(VENV_BIN)/isort backend/ || isort backend/
	@echo "Formatting frontend code..."
	cd frontend && npm run format

test: ## Run backend and frontend tests
	@echo "Running backend tests..."
	$(VENV_BIN)/pytest backend/ || pytest backend/
	@echo "Running frontend tests..."
	cd frontend && npm run test

verify: ## Run the repository verification script
	./verify.sh

TOOL_VERSIONS := grype:v0.79.1 pip-audit:2.7.3

install-tools: ## Install pinned vulnerability scanners
	@echo "Installing vulnerability scanning tools (pinned versions)..."
	pip install pip-audit==2.7.3
	@echo "To install Grype: curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh | sh -s -- -b /usr/local/bin v0.79.1"

scan-vulns: install-tools ## Scan dependencies and the Docker image
	@echo "=== pip-audit (Python) ==="
	pip-audit --strict -r backend/requirements.txt
	@echo ""
	@echo "=== npm audit (Frontend) ==="
	cd frontend && npm audit --audit-level=high
	@echo ""
	@echo "=== Grype (Docker image) ==="
	grype open-contribution-atelier-backend:latest --fail-on HIGH --only-fixed
	@echo ""
	@echo "=== Allowlist Check ==="
	python backend/scripts/check_dependency_allowlist.py \
		--reports-dir . \
		--allowlist backend/scripts/vuln-allowlist.json \
		--output vuln-report-consolidated.json
	@echo "=== Done ==="
