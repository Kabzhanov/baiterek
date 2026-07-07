SHELL := /bin/sh
COMPOSE ?= docker compose
.PHONY: up down build logs ps migrate seed demo-data test lint lint-hardcode config clean
up:
	$(COMPOSE) up -d --build
down:
	$(COMPOSE) down
build:
	$(COMPOSE) build
logs:
	$(COMPOSE) logs -f --tail=200
ps:
	$(COMPOSE) ps
migrate:
	$(COMPOSE) exec api alembic upgrade head
seed: migrate
	$(COMPOSE) exec api python -m app.seed
demo-data:
	$(COMPOSE) exec api python -m app.seed --demo
test:
	$(COMPOSE) run --rm api pytest
	$(COMPOSE) run --rm web npm test -- --runInBand
lint:
	$(COMPOSE) run --rm api ruff check .
	$(COMPOSE) run --rm api mypy app
	$(COMPOSE) run --rm web npm run lint
	$(COMPOSE) run --rm web npm run typecheck
lint-hardcode:
	@if grep -rniE 'вагон|животновод|wagons|agroanimal' backend/app frontend \
		--include='*.py' --include='*.ts' --include='*.tsx' \
		--exclude-dir=seed --exclude-dir=node_modules --exclude-dir=.next 2>/dev/null; then \
		exit 1; \
	else \
		echo "OK"; \
	fi
config:
	$(COMPOSE) config --quiet
clean:
	$(COMPOSE) down --remove-orphans
