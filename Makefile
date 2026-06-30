.PHONY: help install start lint format test test-backend test-frontend test-e2e migrate makemigrations clean

help:
	@echo "Available commands:"
	@echo "  make install         - Install frontend and backend dependencies"
	@echo "  make start           - Start the full stack using Docker (Postgres, Redis, Django, Vite)"
	@echo "  make lint            - Run linters on frontend (ESLint) and backend (Black check)"
	@echo "  make format          - Format code for frontend (Prettier) and backend (Black)"
	@echo "  make test            - Run all backend and frontend unit tests"
	@echo "  make test-backend    - Run backend unit tests (pytest)"
	@echo "  make test-frontend   - Run frontend unit tests (Vitest)"
	@echo "  make test-e2e        - Run frontend E2E tests (Playwright)"
	@echo "  make migrate         - Apply backend database migrations"
	@echo "  make makemigrations  - Generate backend database migrations"
	@echo "  make clean           - Remove caches, pycache, and build artifacts"

install:
	npm --prefix frontend install
	cd backend && pip install -r requirements.txt

start:
	docker compose up --build

lint:
	npm --prefix frontend run lint
	cd backend && python -m black --check . && python -m isort --check-only .

format:
	npm --prefix frontend run format
	cd backend && python -m black . && python -m isort .

test: test-backend test-frontend

test-backend:
	cd backend && pytest

test-frontend:
	npm --prefix frontend run test

test-e2e:
	npm --prefix frontend run test:e2e

migrate:
	cd backend && python manage.py migrate

makemigrations:
	cd backend && python manage.py makemigrations

clean:
	npm --prefix frontend exec -- rimraf node_modules dist || true
	cd backend && python -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('.pytest_cache')]"
