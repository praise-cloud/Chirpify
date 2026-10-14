.PHONY: help install dev test docker-build up down logs lint clean

help:
	@echo "Chirpify Analytics Platform — Developer Commands"
	@echo "------------------------------------------------"
	@echo "  make install       Install local Python dependencies"
	@echo "  make dev           Run FastAPI ingestion service locally"
	@echo "  make test          Run pytest test suite"
	@echo "  make docker-build  Build production multi-stage Docker image"
	@echo "  make up            Start local microservices stack (Docker Compose)"
	@echo "  make down          Stop local stack and remove volumes"
	@echo "  make logs          View aggregated logs from Docker Compose"
	@echo "  make lint          Check code style and quality with ruff"
	@echo "  make floci-start   Launch local Floci cloud emulator (AWS on 4566)"
	@echo "  make floci-stop    Stop local Floci cloud emulator"
	@echo "  make tf-init       Initialize Terraform modules and providers"
	@echo "  make tf-validate   Validate Terraform configuration syntax"
	@echo "  make tf-plan       Run Terraform plan against Floci or AWS"
	@echo "  make clean         Remove cache and temporary build files"

install:
	pip install -r requirements.txt

dev:
	python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

test:
	python -m pytest tests/ -v

docker-build:
	docker build -f docker/Dockerfile.api -t chirpify-api:latest .

up:
	docker compose up -d

down:
	docker compose down -v

logs:
	docker compose logs -f

lint:
	python -m ruff check src/ tests/

floci-start:
	floci start

floci-stop:
	floci stop

tf-init:
	powershell -NoProfile -Command "cd terraform/environments/dev; terraform init"

tf-validate:
	powershell -NoProfile -Command "cd terraform/environments/dev; terraform validate"

tf-plan:
	powershell -NoProfile -Command "cd terraform/environments/dev; terraform plan"

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
