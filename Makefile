.PHONY: install dev worker test lint typecheck evaluate up down

install:
	uv sync --all-extras

dev:
	uv run uvicorn app.main:app --reload

worker:
	uv run celery -A app.tasks.celery_app worker -l INFO

test:
	uv run pytest -q

lint:
	uv run ruff check .

typecheck:
	uv run mypy app

evaluate:
	uv run python scripts/evaluate.py --dataset datasets/eval.jsonl

up:
	docker compose up --build

down:
	docker compose down
