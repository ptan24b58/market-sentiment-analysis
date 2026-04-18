.PHONY: help install test test-unit test-integration test-e2e lint format pipeline sentinel ablation reports ui-dev ui-build ui-serve clean

help:
	@echo "Hook'em Hacks 2026 — Persona Sentiment Simulator"
	@echo ""
	@echo "Setup:"
	@echo "  install          Install Python deps + UI deps"
	@echo ""
	@echo "Test:"
	@echo "  test             Run all Python tests (unit+integration+e2e, mocked)"
	@echo "  test-unit        Unit tests only"
	@echo "  test-integration Integration tests (mocked external services)"
	@echo "  test-e2e         End-to-end tests with synthetic data"
	@echo "  lint             Ruff lint pass"
	@echo "  format           Ruff format"
	@echo ""
	@echo "Pipeline (requires AWS Bedrock credentials in .env):"
	@echo "  sentinel         Run H+4 sentinel gate (3 events x 300 personas)"
	@echo "  pipeline         Full pipeline: events -> AR -> baselines -> personas -> dynamics"
	@echo "  ablation         Compute 5-way ablation table from existing signals"
	@echo "  reports          Generate methodology.md + poster + pitch from ablation_results.json"
	@echo ""
	@echo "UI:"
	@echo "  ui-dev           Start Next.js dev server (localhost:3000)"
	@echo "  ui-build         Static export for offline booth laptop"
	@echo "  ui-serve         Serve the built static site locally"
	@echo ""
	@echo "Ops:"
	@echo "  clean            Remove build artifacts, caches, stale .parquet files"

install:
	pip install -r requirements.txt
	cd ui && npm install

test:
	pytest tests/ -q

test-unit:
	pytest tests/unit -q

test-integration:
	pytest tests/integration -q -m "not bedrock"

test-e2e:
	pytest tests/e2e -q

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

sentinel:
	python -m scripts.run_sentinel

pipeline:
	python -m scripts.run_full_pipeline

ablation:
	python -m scripts.run_ablation

reports:
	python -m scripts.generate_reports

ui-dev:
	cd ui && npm run dev

ui-build:
	cd ui && npm run build

ui-serve:
	cd ui && npx serve out/

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache
	rm -rf ui/.next ui/out ui/node_modules/.cache
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
