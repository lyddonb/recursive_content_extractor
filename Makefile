.PHONY: install test lint format typecheck check clean

install:
	uv sync --extra dev

test:
	uv run pytest -v

lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/

typecheck:
	uv run mypy src/

check: lint typecheck test
	@echo "All checks passed!"

clean:
	rm -rf .venv .mypy_cache .ruff_cache .pytest_cache dist build *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
