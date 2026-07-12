ifeq ($(OS),Windows_NT)
    PYTHON := python
    BIN_DIR := Scripts
else
    PYTHON := python3
    BIN_DIR := bin
endif

VENV_BIN := backend/.venv/$(BIN_DIR)

.PHONY: install start format test verify

install:
	@echo "Installing backend dependencies..."
	$(PYTHON) -m venv backend/.venv
	$(VENV_BIN)/pip install -r backend/requirements.txt
	@echo "Installing frontend dependencies..."
	cd frontend && npm install

start:
	@echo "Starting development stack..."
	docker compose up --build

format:
	@echo "Formatting backend code..."
	$(VENV_BIN)/black backend/ || black backend/
	$(VENV_BIN)/isort backend/ || isort backend/
	@echo "Formatting frontend code..."
	cd frontend && npm run format

test:
	@echo "Running backend tests..."
	$(VENV_BIN)/pytest backend/ || pytest backend/
	@echo "Running frontend tests..."
	cd frontend && npm run test

verify:
	./verify.sh
