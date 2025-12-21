.PHONY: install dev run worker test lint format

install:
	uv sync

dev:
	uvicorn src.app.main:app --reload --port 8000

run:
	uvicorn src.app.main:app --host 0.0.0.0 --port 8000

worker:
	celery -A src.workers.celery_app worker --loglevel=info

test:
	pytest tests/ -v

lint:
	ruff check src/

format:
	ruff format src/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
