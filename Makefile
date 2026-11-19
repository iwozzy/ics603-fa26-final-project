UV ?= uv
NPM ?= npm
COMPOSE = docker compose --env-file /dev/null

.PHONY: dev test generate lint migrate test-integration test-e2e test-cache-expiry

dev:
	$(COMPOSE) up --build

test:
	$(UV) --directory backend run pytest tests/unit tests/api tests/integration/clients -q
	$(NPM) --prefix frontend test -- --runInBand

generate:
	$(UV) --directory backend run python scripts/export_openapi.py
	$(NPM) --prefix frontend run generate:api

lint:
	$(UV) --directory backend run ruff check src tests scripts migrations
	$(UV) --directory backend run pyrefly check
	$(UV) --directory backend run lint-imports
	$(NPM) --prefix frontend run typecheck
	$(NPM) --prefix frontend run lint

migrate:
	$(UV) --directory backend run alembic upgrade head

test-integration:
	@set -eu; trap '$(COMPOSE) -f compose.test.yaml down --volumes' EXIT; \
	$(COMPOSE) -f compose.test.yaml up -d --wait postgres; \
	LUMIERE_RUN_PERSISTENCE=1 $(UV) --directory backend run pytest tests/integration/persistence -q

test-e2e:
	$(NPM) --prefix e2e test

test-cache-expiry:
	$(NPM) --prefix e2e run test:cache-expiry
