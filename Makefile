.PHONY: install start format test verify

install:
	@echo "Installing backend dependencies..."
	python3 -m venv backend/.venv
	backend/.venv/bin/pip install -r backend/requirements.txt
	@echo "Installing frontend dependencies..."
	cd frontend && npm install

start:
	@echo "Starting development stack..."
	docker compose up --build

format:
	@echo "Formatting backend code..."
	backend/.venv/bin/black backend/ || black backend/
	backend/.venv/bin/isort backend/ || isort backend/
	@echo "Formatting frontend code..."
	cd frontend && npm run format

test:
	@echo "Running backend tests..."
	backend/.venv/bin/pytest backend/ || pytest backend/
	@echo "Running frontend tests..."
	cd frontend && npm run test

verify:
	./verify.sh
