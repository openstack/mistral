# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Qubership Mistral

Qubership Mistral is a distributed workflow management and execution service, forked from OpenStack Mistral by NetCracker Technology Corp. It lets users define tasks and workflows in YAML and executes them in a distributed, HA environment. Workflows are written using YAQL (`<% %>`) or Jinja2 (`{{ }}`) expressions.

## Architecture

Mistral is a multi-process system where all inter-component communication goes through a message broker (RabbitMQ or Kafka). The components:

```
User/API Client
      │ HTTP REST
      ▼
  API Server (mistral/api/)          ← Pecan WSGI, read-only DB, sends RPC to Engine
      │ RPC
      ▼
  Engine (mistral/engine/)           ← Core orchestration: workflow state machine, task scheduling
      │ RPC / message queue
      ├──▶ Executor (mistral/executors/)     ← Runs actions; no DB access
      ├──▶ Notifier (mistral/notifiers/)     ← Event webhooks/Kafka; no DB access
      └──▶ Monitoring (mistral/monitoring/)  ← Prometheus metrics + recovery jobs (FastAPI)
```

Key constraints:
- **Engine is the only component that writes to the database** (PostgreSQL via SQLAlchemy + Alembic)
- Executor and Notifier have no DB access — they communicate results back to Engine via RPC
- **Scheduler** (`mistral/scheduler/`) manages cron triggers, integrated into Engine process
- **Event Engine** (`mistral/event_engine/`) handles event-driven workflow triggers
- **Recovery jobs** in `mistral/monitoring/jobs/` detect and heal broken executions (delayed calls, idle tasks, named locks, waiting tasks, subworkflows)
- All components are horizontally scalable via distributed locking

### Plugin Architecture

Most subsystems are pluggable via setuptools entry points (defined in `setup.cfg`):

| Entry point | Implementations |
|-------------|-----------------|
| `mistral.rpc.backends` | oslo (default), kombu |
| `mistral.executors` | remote (default), local |
| `mistral.expression.evaluators` | yaql, jinja2 |
| `mistral.auth` | keystone, keycloak |
| `mistral.schedulers` | default, legacy |
| `monitoring.recovery_jobs` | registered recovery job implementations |

### Key Source Directories

| Path | Purpose |
|------|---------|
| `mistral/api/` | REST API controllers (Pecan) |
| `mistral/engine/` | Core orchestration, workflow state machine |
| `mistral/executors/` | Action execution |
| `mistral/notifiers/` | Event notification publishers |
| `mistral/monitoring/` | Metrics (FastAPI/Uvicorn) + recovery jobs |
| `mistral/scheduler/` | Cron trigger management |
| `mistral/event_engine/` | Event-driven execution |
| `mistral/actions/` | Built-in action implementations (HTTP, SSH, etc.) |
| `mistral/expressions/` | YAQL and Jinja2 evaluators |
| `mistral/db/sqlalchemy/` | ORM models + Alembic migrations |
| `mistral/rpc/` | Message broker abstraction (oslo/kombu) |
| `mistral/workflow/` | Workflow/task definitions, data flow, state machine |
| `mistral/auth/` | Keystone and Keycloak auth handlers |
| `mistral/cmd/launch.py` | Main entry point (`mistral-server`) |
| `mistral/config.py` | All configuration options and defaults |

## Kubernetes Operator

The `operator/` directory contains a [Kopf](https://kopf.readthedocs.io/)-based Kubernetes operator that manages the full lifecycle of Mistral in Kubernetes.

### Custom Resource

- **API:** `netcracker.com/v2`, Kind: `MistralService` (short names: `mistral`, `mistrals`)
- CRD: `operator/deploy/crd.yaml` and `operator/deployments/charts/mistral-operator/crds/crd.yaml`

### Operator Components (run as sidecars in the operator pod)

| Container | Purpose |
|-----------|---------|
| `mistral-operator` | Main Kopf reconciliation loop — creates/updates/deletes 5 Mistral deployments |
| `mistral-disaster-recovery` | DR daemon for active/standby/disable mode switchover |
| `bluegreen-agent` | FastAPI service on port 8000 for zero-downtime blue-green migration |

### Operator Reconciliation (operator/src/handler.py)

- **on.create** — validates secret, creates RabbitMQ vhosts/credentials, runs DB migration job, deploys all 5 services
- **on.update** — re-runs migrations, updates all service deployments; respects `operatorId` field to support multiple operator instances in the same cluster
- **on.delete** — removes all deployments, secrets, and config maps
- **on.field (disasterRecovery.mode)** — scales down (standby/disable) or runs DR job + scales up (active)

### Blue-Green Deployments (operator/bluegreen-agent/)

**Deprecated**. The agent migrates workflow definitions between namespaces (blue→green) without downtime:
- `POST /api/bluegreen/warmup` — clones all workflows from source namespace to target (inserts new UUIDs into `workflow_definitions_v2`)
- `POST /api/bluegreen/commit` — deletes all workflows from the old namespace

### HA Mechanisms

- **Pod anti-affinity** — preferred spread across nodes for each service
- **HPA** — `autoscaling/v2` on CPU (default 85%), configurable via `HPA_*` values; disabled by default
- **PodDisruptionBudget** — optional, protects against node drains; disabled by default
- **DR mode** — active/standby failover managed by SiteManager integration
- **Multi-operator coordination** — each operator instance has an `OPERATOR_ID`; update handler skips CR if `operatorId` doesn't match

### Helm Chart (operator/deployments/charts/mistral-operator/)

Key `values.yaml` sections:
- `mistralCommonParams` — DB host/port, RabbitMQ, Kafka, auth settings
- `mistralApi/Engine/Executor/Notifier/Monitoring` — replicas, resources, affinity per service
- `disasterRecovery` — DR mode, image, timeout
- `bluegreenAgent` — enable/disable, image
- `mistral.tls` — TLS for all service connections (API, monitoring, PostgreSQL, RabbitMQ, Kafka)
- `secrets` — DB, RabbitMQ, Kafka, IDP credentials (passed as Kubernetes Secret)

## Commands

### Testing

```bash
tox -e py3                     # Unit tests
tox -e unit-postgresql         # Unit tests with PostgreSQL
tox -e unit-sqlite             # Unit tests with SQLite
tox -e pep8                    # Lint (flake8 + doc8)
tox                            # Full suite (py3 + pep8)
tox -e cover                   # Coverage report
```

Run a single test:
```bash
stestr run tests/unit/path/to/test_file.py
stestr run -- tests/unit/path/to/test_file.py::TestClass::test_method
```

### Development Setup

```bash
pip install -r requirements.txt -r test-requirements.txt -r nc_requirements.txt
python setup.py develop
```

### Database Migrations

```bash
mistral-db-manage --config-file mistral.conf upgrade
```

### Running Services Locally

```bash
# All components in one process
mistral-server --server all --config-file mistral.conf

# Individual components
mistral-server --server api|engine|executor|notifier|event-engine

# Prometheus metrics service (port 9090)
mistral-monitoring --config-file mistral.conf
```

### Docker

```bash
docker build -t qubership-mistral:latest .
# Runtime: SERVER=all|api|engine|executor|notifier|event-engine|monitoring
```

### Config Generation

```bash
tox -e genconfig   # Generate sample mistral.conf
tox -e genpolicy   # Generate sample policy.yaml
```
