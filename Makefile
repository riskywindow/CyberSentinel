# CyberSentinel Makefile
SEED ?= 42
SHELL := /bin/sh
NEO4J_URI ?= bolt://localhost:7687
NEO4J_USER ?= neo4j
NEO4J_PASSWORD ?= test-password

DOCKER_COMPOSE := $(shell command -v docker-compose >/dev/null 2>&1 && echo docker-compose || echo docker compose)

.PHONY: help dev seed replay eval test clean proto install-deps wait-neo4j rag-index rag-eval test-rag-quality vector-parity-test test-tenancy stream-smoke stream-load test-jetstream

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

wait-neo4j: ## Wait for Neo4j to become healthy
	@echo "Waiting for Neo4j to become healthy..."
	@while ! docker compose exec -T neo4j cypher-shell -u neo4j -p test-password "RETURN 1;" >/dev/null 2>&1; do echo "Waiting for Neo4j..."; sleep 2; done
	@echo "Neo4j is ready"

dev: ## Bring up development environment (ClickHouse, Neo4j, API services, UI)
	@echo "Starting CyberSentinel development environment..."
	docker compose up -d clickhouse neo4j nats redis
	$(MAKE) wait-neo4j
	@echo "Installing database schemas..."
	NEO4J_URI=$(NEO4J_URI) NEO4J_USER=$(NEO4J_USER) NEO4J_PASSWORD=$(NEO4J_PASSWORD) \
	python -c "from storage import ClickHouseClient, Neo4jClient; ch = ClickHouseClient(); ch.connect(); ch.install_schema(); ch.disconnect(); neo = Neo4jClient(); neo.connect(); neo.install_schema(); neo.disconnect()"
	@echo "Development environment ready!"
	@echo "ClickHouse: http://localhost:8123"
	@echo "Neo4j Browser: http://localhost:7474"
	@echo "NATS: nats://localhost:4222"

seed: ## Load full ATT&CK + CVE/Sigma demo slices (OFFLINE=1 for fixture-only)
	@echo "Seeding knowledge corpus…"
ifdef OFFLINE
	PYTHONPATH=. python -m knowledge.corpora.attack_stix \
		--offline tests/fixtures/attack_stix/enterprise_attack_bundle.json \
		--force --cache-dir knowledge/corpora/cache
else
	PYTHONPATH=. python -m knowledge.corpora.attack_stix --force --cache-dir knowledge/corpora/cache
endif
	@echo "Seed complete."

replay: ## Run replay harness on sample scenarios
	@echo "Running log replay scenarios..."
	PYTHONPATH=. python eval/harness.py --scenarios eval/suite/scenarios.yml --output eval/reports/ --seed $(SEED)
	@echo "Replay completed!"

eval: ## Full benchmark, emit scorecard.json and HTML report
	@echo "Running full evaluation benchmark..."
	PYTHONPATH=. python eval/harness.py --full-eval --scenarios eval/suite/scenarios.yml --output eval/reports/ --seed $(SEED)
	PYTHONPATH=. python eval/scorecard.py --input eval/reports/ --output eval/scorecard.json --html eval/reports/index.html
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
	docker compose down -v
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
	docker compose down

logs: ## Show logs from all services
	docker compose logs -f

status: ## Show status of all services
	docker compose ps
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
	docker compose exec clickhouse clickhouse-client

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

# RL adversary training targets
rl-clean: ## Clean RL outputs
	rm -rf eval/rl/*
	mkdir -p eval/rl

rl-train-pg: ## Train RL adversary with Policy Gradient
	PYTHONPATH=. python rl/train_adversary.py --algo pg --seed $${SEED:-42} --episodes 200 --steps-per-episode 12

rl-train-ppo: ## Train RL adversary with PPO
	PYTHONPATH=. python rl/train_adversary.py --algo ppo --seed $${SEED:-42} --episodes 200 --steps-per-episode 12

rl-eval: ## Evaluate trained RL adversary
	PYTHONPATH=. python rl/eval_adversary.py --seed $${SEED:-42} --compare-random

rl-plot: ## Plot RL learning curves
	PYTHONPATH=. python rl/plot_rl.py

rl-smoke: ## Run full RL smoke test (PG, 50 episodes, stub detector)
	$(MAKE) rl-clean
	PYTHONPATH=. python rl/train_adversary.py --algo pg --seed $${SEED:-42} --episodes 50 --steps-per-episode 12
	PYTHONPATH=. python rl/eval_adversary.py --seed $${SEED:-42}
	PYTHONPATH=. python rl/plot_rl.py
	@echo "RL smoke test complete! Check eval/rl/ for outputs."

rl-smoke-ppo: ## Run PPO smoke test (200 episodes)
	$(MAKE) rl-clean
	PYTHONPATH=. python rl/train_adversary.py --algo ppo --seed $${SEED:-42} --episodes 200 --steps-per-episode 12
	PYTHONPATH=. python rl/eval_adversary.py --seed $${SEED:-42}
	PYTHONPATH=. python rl/plot_rl.py
	@echo "RL PPO smoke test complete! Check eval/rl/ for outputs."

test-rl: ## Run RL unit tests
	python -m pytest tests/rl/ -v

test-attack-ingest: ## Run ATT&CK STIX ingest tests (offline, no network)
	PYTHONPATH=. python -m pytest tests/test_attack_ingest.py -v

# ---------------------------------------------------------------------------
# RAG quality targets
# ---------------------------------------------------------------------------

rag-index: ## Incremental RAG index build (uses env-resolved embeddings)
	@echo "Building RAG index (incremental)..."
	PYTHONPATH=. python -c "\
from knowledge.rag_index import RAGIndexManager; \
mgr = RAGIndexManager(); \
mgr.load_existing_index(); \
docs = mgr.corpus.load_all_demo_slices(); \
stats = mgr.builder.update_documents(docs); \
print('Index stats:', stats)"
	@echo "RAG index build complete."

rag-eval: ## Run RAG evaluation, emit eval/rag/report.json (CI gate)
	@echo "Running RAG evaluation..."
	PYTHONPATH=. python eval/rag/eval_rag.py \
		--embedding-provider $${EMBEDDINGS_PROVIDER:-mock} \
		--reranker $${RERANKER:-mock}
	@echo "RAG evaluation complete. See eval/rag/report.json"

test-rag-quality: ## Run RAG quality unit + eval tests
	PYTHONPATH=. python -m pytest tests/test_rag_quality.py -v

vector-parity-test: ## Run vector store unit + parity tests (FAISS vs Pinecone)
	PYTHONPATH=. python -m pytest tests/test_vector_stores.py -v

# ---------------------------------------------------------------------------
# API targets
# ---------------------------------------------------------------------------

api-dev: ## Start API dev server with hot-reload
	PYTHONPATH=. uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

api-test: ## Run API unit tests
	PYTHONPATH=. python -m pytest tests/api/ -v

# ---------------------------------------------------------------------------
# Multi-tenancy & query safety
# ---------------------------------------------------------------------------

test-tenancy: ## Run multi-tenancy isolation and query safety tests
	PYTHONPATH=. python -m pytest tests/test_tenancy.py -v

# ---------------------------------------------------------------------------
# JetStream / streaming targets
# ---------------------------------------------------------------------------

RATE ?= 500
COUNT ?= 1000

test-jetstream: ## Run JetStream unit tests
	PYTHONPATH=. python -m pytest tests/test_jetstream.py -v

stream-smoke: ## Smoke test: publish+consume 100 msgs via JetStream (needs NATS)
	PYTHONPATH=. python -m pytest integration_tests/test_jetstream_integration.py -v
	PYTHONPATH=. python tools/stream_load.py --count 100 --rate 200 --output eval/reports/stream_smoke.json
	@echo "Smoke test passed. Report: eval/reports/stream_smoke.json"

stream-load: ## Load test JetStream (RATE=msg/s COUNT=total) e.g. make stream-load RATE=2000 COUNT=5000
	PYTHONPATH=. python tools/stream_load.py --count $(COUNT) --rate $(RATE) --output eval/reports/stream_load.json
	@echo "Load test complete. Report: eval/reports/stream_load.json"