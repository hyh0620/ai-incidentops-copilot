PY=.venv/bin/python

.PHONY: setup migrate seed ingest test lint evaluate run backend frontend ci

setup:
	cd backend && python3.11 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
	cd frontend && npm install

seed:
	cd backend && .venv/bin/alembic upgrade head && $(PY) -m app.seed --reset

ingest:
	cd backend && .venv/bin/alembic upgrade head && $(PY) -m app.scripts.ingest_kb --rebuild --force-fallback

migrate:
	cd backend && .venv/bin/alembic upgrade head

test:
	cd backend && $(PY) -m pytest
	cd frontend && npm run test

lint:
	cd backend && .venv/bin/ruff check .
	cd frontend && npm run lint

evaluate:
	cd backend && $(PY) -m app.scripts.evaluate

ci:
	cd backend && $(PY) -m pytest && .venv/bin/ruff check . && $(PY) -m app.scripts.ingest_kb --check && $(PY) -m app.scripts.evaluate
	cd frontend && npm run test && npm run lint && npm run build

backend:
	cd backend && .venv/bin/alembic upgrade head && $(PY) -m uvicorn app.main:app --reload

frontend:
	cd frontend && npm run dev

run:
	docker compose up --build
