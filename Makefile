.PHONY: up down logs test lint backup restore demo

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

test:
	ADMIN_DATABASE_URL=postgresql://postgres:$${POSTGRES_PASSWORD:-postgres}@127.0.0.1:5433/busbooking_test \
	API_KEY=test-key \
	pytest

lint:
	ruff check .
	ruff format --check .

backup:
	./ops/backup.sh

restore:
	./ops/restore.sh $(FILE)

demo:
	./ops/acceptance.sh
