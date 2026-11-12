.PHONY: setup api fixture-api web check check-backend check-frontend test-e2e api-types smoke-logfire

setup:
	uv --directory backend sync --locked
	npm --prefix frontend ci

api:
	uv --directory backend run --locked uvicorn lumiere.bootstrap:create_app --factory --reload --reload-dir src --host 127.0.0.1 --port 8000 --no-access-log

fixture-api:
	LUMIERE_TELEMETRY_ENABLED=false uv --directory backend run --locked uvicorn --app-dir tests fixture_app:create_fixture_app --factory --host 127.0.0.1 --port 8000 --no-access-log

smoke-logfire:
	uv --directory backend run --locked python scripts/smoke_logfire.py

web:
	npm --prefix frontend start

check: check-backend check-frontend test-e2e

check-backend:
	uv --directory backend lock --check
	uv --directory backend pip check
	uv --directory backend run --locked ruff check .
	uv --directory backend run --locked ruff format --check .
	uv --directory backend run --locked pyrefly check --min-severity=warn
	uv --directory backend run --locked lint-imports
	uv --directory backend run --locked pytest --cov=lumiere --cov-report=term-missing

check-frontend:
	npm --prefix frontend run check

test-e2e:
	npm --prefix frontend run test:e2e

api-types:
	npm --prefix frontend run api:generate
