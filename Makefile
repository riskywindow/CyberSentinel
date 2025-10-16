# CyberSentinel Makefile

.PHONY: help dev seed replay eval test clean proto install-deps

# Default target
help: ## Show this help message
	@echo "CyberSentinel - End-to-end purple-team cyber-defense lab"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

install-deps: ## Install Python dependencies
	pip install -e .
	pip install -r requirements-dev.txt

proto: ## Compile protobuf schemas
	python bus/proto/compile.py

dev: ## Bring up development environment (ClickHouse, Neo4j, API services, UI)
	@echo "Starting CyberSentinel development environment..."
	docker-compose up -d clickhouse neo4j nats redis
	@echo "Waiting for services to be ready..."
	sleep 10
	@echo "Installing database schemas..."
	python -c "from storage import ClickHouseClient, Neo4jClient; ch = ClickHouseClient(); ch.connect(); ch.install_schema(); ch.disconnect(); neo = Neo4jClient(); neo.connect(); neo.install_schema(); neo.disconnect()"
	@echo "Development environment ready!"
	@echo "ClickHouse: http://localhost:8123"
	@echo "Neo4j Browser: http://localhost:7474"
	@echo "NATS: nats://localhost:4222"

seed: ## Load ATT&CK/CVE demo slices + example logs
	@echo "Loading demo knowledge base and datasets..."
	python scripts/seed_data.py
	@echo "Demo data loaded successfully!"

replay: ## Run replay harness on sample scenarios
	@echo "Running log replay scenarios..."
	python eval/harness.py --scenarios eval/suite/scenarios.yml --output eval/reports/
	@echo "Replay completed!"

eval: ## Full benchmark, emit scorecard.json and HTML report
	@echo "Running full evaluation benchmark..."
	python eval/harness.py --full-eval --scenarios eval/suite/scenarios.yml --output eval/reports/
	python eval/scorecard.py --input eval/reports/ --output eval/scorecard.json --html eval/reports/index.html
	@echo "Evaluation completed! Check eval/reports/index.html"

test: ## Run all unit/integration tests
	@echo "Running unit tests..."
	python -m pytest tests/ -v
	@echo "Running integration tests..."
	python -m pytest integration_tests/ -v
	@echo "Running detection precision tests..."
	python -m pytest detections/sigma/tests/ -v
	@echo "All tests completed!"

test-unit: ## Run unit tests only
	python -m pytest tests/ -v

test-integration: ## Run integration tests only  
	python -m pytest integration_tests/ -v

test-detections: ## Run detection precision tests only
	python -m pytest detections/sigma/tests/ -v

lint: ## Run linting and formatting
	ruff check .
	ruff format --check .
	mypy .

format: ## Format code
	ruff format .
	ruff check --fix .

ui-dev: ## Start UI development server
	cd ui && npm run dev

ui-build: ## Build UI for production
	cd ui && npm run build

ui-install: ## Install UI dependencies
	cd ui && npm install

clean: ## Clean up generated files and stop services
	docker-compose down -v
	rm -rf data/faiss_index
	rm -rf eval/reports/*
	rm -rf .pytest_cache
	rm -rf __pycache__
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} +

clean-data: ## Clean up data directories only
	rm -rf data/faiss_index
	rm -rf eval/reports/*
	@echo "Data directories cleaned"

stop: ## Stop all Docker services
	docker-compose down

logs: ## Show logs from all services
	docker-compose logs -f

status: ## Show status of all services
	docker-compose ps
	@echo ""
	@echo "Service URLs:"
	@echo "  ClickHouse: http://localhost:8123"
	@echo "  Neo4j Browser: http://localhost:7474 (neo4j/password)"
	@echo "  NATS: nats://localhost:4222"

reset: ## Reset everything (clean + dev)
	$(MAKE) clean
	$(MAKE) dev
	$(MAKE) seed

quick-test: ## Quick smoke test
	@echo "Running quick smoke test..."
	python -c "from storage import ClickHouseClient, Neo4jClient, FAISSStore; print('Storage clients imported successfully')"
	python -c "from bus import Bus, BusConfig; print('Bus components imported successfully')"
	@echo "Basic imports working!"

# Development shortcuts
db: ## Connect to ClickHouse client
	docker-compose exec clickhouse clickhouse-client

neo4j: ## Open Neo4j browser
	@echo "Opening Neo4j browser at http://localhost:7474"
	@echo "Username: neo4j, Password: password"

# Scenario-specific targets  
scenario-lateral: ## Run lateral movement scenario
	python eval/harness.py --scenario lateral_move_ssh

scenario-cred: ## Run credential dump scenario  
	python eval/harness.py --scenario cred_dump_windows

# Red team targets
red-baseline: ## Run baseline red team agent
	python agents/red/agent_baseline.py

red-rl: ## Run RL red team agent
	python agents/red/agent_rl.py

# Agent testing
test-scout: ## Test scout agent
	python -m pytest tests/agents/test_scout.py -v

test-analyst: ## Test analyst agent
	python -m pytest tests/agents/test_analyst.py -v

test-responder: ## Test responder agent
	python -m pytest tests/agents/test_responder.py -v