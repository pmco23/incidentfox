.PHONY: help install test lint format clean docker-build docker-run deploy

help:
	@echo "AI Agent System V2 - Available commands:"
	@echo "  make install      - Install dependencies"
	@echo "  make test         - Run tests"
	@echo "  make lint         - Run linters"
	@echo "  make format       - Format code"
	@echo "  make clean        - Clean temporary files"
	@echo "  make docker-build - Build Docker image"
	@echo "  make docker-run   - Run Docker container"
	@echo "  make deploy       - Deploy to AWS"

install:
	poetry install

test:
	poetry run pytest -v

test-cov:
	poetry run pytest --cov=src --cov-report=html --cov-report=term

lint:
	poetry run ruff check src/ tests/
	poetry run mypy src/

format:
	poetry run black src/ tests/
	poetry run ruff check --fix src/ tests/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	rm -rf htmlcov/ .coverage

docker-build:
	docker build -t ai-agent:latest .

docker-run:
	docker run --env-file .env ai-agent:latest

terraform-plan:
	cd infra/terraform && terraform plan -var="aws_profile=playground"

terraform-apply:
	cd infra/terraform && terraform apply -var="aws_profile=playground"

deploy: docker-build
	@echo "Building and pushing to ECR..."
	./scripts/deploy.sh

