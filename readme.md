# AI-Powered Incident Reporting System

An end-to-end, production-grade system that ingests real SF 311 public complaints, classifies them with GPT-4o, and surfaces everything through a **human-in-the-loop governance dashboard** — built with enterprise-grade AI governance and security baked in from day one.

---

## AI Governance Framework

Most AI projects skip this entirely. This system treats governance as a **first-class feature**, not an afterthought.

### Governance Pillars

| Pillar | Component | What It Proves |
|--------|-----------|----------------|
| 🧠 **AI Reasoning** | Every decision includes `ai_reasoning` field | Transparency — the "why" behind every classification |
| 📋 **Prompt Registry** | `PromptRegistry` class with versioned prompts (`v1.0.0`, `v1.1.0`...) | Version control — full auditable history of AI instructions |
| 🛡️ **Confidence Guardrails** | Auto-flags incidents where confidence < 0.8 | Risk mitigation — catches uncertain AI decisions early |
| 📊 **Performance Stats** | `/api/incidents/performancestats` — AI accuracy vs human ground truth per prompt version | Accountability — quantifies AI quality over time |
| ⚖️ **Policy-as-Code** | `PolicyEngine` — deterministic overrides that always run after AI responds | Safety — hard rules for life-safety scenarios that AI cannot override |
| 👤 **Human-in-the-Loop (HITL)** | Approve / Reject / Override from dashboard, logged with actor + timestamp | Verification — final human authority on every label |
| 🔍 **Drift Detection** | `/api/governance/drift_check` — compares earliest 50 vs latest 50 decisions | Reliability — alerts when model accuracy degrades over time |
| 🗺️ **Bias Audit** | `/api/governance/bias_check` — accuracy broken down by zip code | Equity — ensures the AI isn't systematically wrong in specific neighborhoods |
| 🔗 **Data Lineage** | `transformation_log` column records every state change with timestamp + actor | Integrity — proves the origin and full history of every record |

### PolicyEngine — Deterministic Safety Layer

The `PolicyEngine` (`triage_agent/policy_engine.py`) sits **between the AI output and the database**. No matter what GPT-4o returns, these rules always run:

```
AI Response
     │
     ▼
┌─────────────────────────────────────────────┐
│              PolicyEngine                   │
│                                             │
│  Policy A: Safety Keyword Override          │
│  → "fire/gas/explosion/flood/..." → CRITICAL│
│                                             │
│  Policy B: SLA Assignment                  │
│  → CRITICAL=2h, HIGH=4h, MED=24h, LOW=3d  │
│                                             │
│  Policy C: Confidence Guardrail            │
│  → confidence < 0.8 → flag for review      │
└─────────────────────────────────────────────┘
     │
     ▼
  Database Write  (governed_result, not raw AI output)
```

This is the core insight: **probabilistic AI + deterministic policy = safe production system.**

---

## Security Architecture

| Layer | Component | Implementation |
|-------|-----------|----------------|
| 🔐 **Authentication** | JWT Tokens | `/token` endpoint issues signed JWTs on login |
| 🔒 **Authorization** | `get_current_user` dependency | Every protected endpoint verifies the token before execution |
| 🧹 **PII Redaction** | `redact_pii()` in triage agent | Emails and phone numbers stripped **before** data reaches the LLM |
| 📦 **Data Integrity** | Pydantic models | All incoming data validated at the API boundary |
| 🛡️ **Database Safety** | Parameterized SQL only | Zero string formatting in queries — SQL injection not possible |
| 📜 **Auditability** | `transformation_log` column | Every severity change recorded: who changed it, when, and why |
| 🔑 **Secrets Management** | Kubernetes Secrets + file-based reading | No credentials in environment variables or code — mounted as read-only files |

### Audit Trail Example

Every incident carries a full `transformation_log`:
```
[2024-01-15 10:23:01] Initial Severity classified as MEDIUM by AI Agent
[2024-01-15 10:23:01] Policy Override to CRITICAL (Note: Safety Keyword Override)
[2024-01-15 11:45:22] HUMAN_OVERRIDE to MEDIUM by admin (Note: False positive — steam not gas)
```

---

---

## Architecture Overview

```
SF 311 Public API
       │
       ▼
┌─────────────────┐
│  311 Ingestor   │  Polls SF 311 API, downloads images → S3, posts to Client API
└────────┬────────┘
         │ HTTP POST /report
         ▼
┌─────────────────┐
│   Client API    │  FastAPI backend + React-style dashboard (JWT auth)
└────────┬────────┘
         │ MCP/SSE
         ▼
┌──────────────────────┐
│  Escalation Agent    │  Decides escalation level via MCP tool call
└──────────┬───────────┘
           │ MCP/SSE
           ▼
┌──────────────────────┐
│   Triage Agent       │  GPT-4o classification + PolicyEngine + DB write
│   + PolicyEngine     │  (PII redaction, SLA assignment, keyword override)
└──────────────────────┘
           │
           ▼
     PostgreSQL DB
```

**Key features showcased:**
- Multi-agent MCP (Model Context Protocol) communication over SSE
- GPT-4o incident severity classification (LOW / MEDIUM / HIGH / CRITICAL)
- Deterministic `PolicyEngine` overrides probabilistic AI (safety keywords, SLA, confidence guardrails)
- PII redaction before data reaches the LLM
- Human-in-the-loop review: approve, reject, or override AI decisions from the dashboard
- AI governance metrics: prompt versioning, drift detection, geographic bias check
- Kubernetes-native: health/readiness probes, secrets, configmaps, resource limits, sticky sessions
- Prometheus metrics on every agent

---

## Repo Structure

```
incident_reporting/
├── 311_ingestor/
│   ├── ingestor.py          # Polls SF 311 dataset, posts to Client API
│   └── Dockerfile
│
├── client/
│   ├── app.py               # FastAPI backend — REST API + JWT auth
│   ├── requirements.txt
│   ├── Dockerfile
│   └── static/
│       └── index.html       # Governance dashboard (Tailwind CSS)
│
├── escalation_agent/
│   ├── server.py            # MCP server — escalation routing
│   └── Dockerfile
│
├── triage_agent/
│   ├── server.py            # MCP server — GPT-4o classification + DB write
│   ├── policy_engine.py     # Deterministic safety/SLA policy enforcement
│   └── Dockerfile
│
├── k8s/
│   ├── 311_ingestor_deployment.yml
│   ├── client_api_deployment.yml
│   ├── escalation_agent_deployment.yml
│   ├── triage_agent_deployment.yml
│   ├── postgres_db.yml
│   └── create_secrets.sh.example  # Template — fill in your values
│
├── monitoring/
│   └── prometheus.yml       # Prometheus scrape config
│
├── screenshots/
│   ├── kubernetes/          # kubectl get pods, logs screenshots
│   ├── dashboard/           # UI and governance page screenshots
│   └── tests/               # All test result screenshots
│
├── scripts/
│   └── init_db.sql          # PostgreSQL schema
│
├── tests/
│   ├── conftest.py
│   ├── test_policy_engine.py
│   ├── test_integration_e2e.py
│   ├── test_performance_latency.py
│   ├── test_security_tokens.py
│   ├── test_pii_logs.py
│   ├── test_policy_idempotence.py
│   └── test_api_contract.py
│
├── .gitignore
├── docker-compose.yml
├── pytest.ini
├── requirements-test.txt
└── readme.md
```

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Docker | 24+ | [docs.docker.com](https://docs.docker.com/get-docker/) |
| kubectl | 1.28+ | [kubernetes.io](https://kubernetes.io/docs/tasks/tools/) |
| Minikube OR any K8s cluster | latest | [minikube.sigs.k8s.io](https://minikube.sigs.k8s.io/docs/start/) |
| PostgreSQL | 14+ | Any hosted or local instance |
| OpenAI API Key | — | [platform.openai.com](https://platform.openai.com/) |
| AWS Account + S3 Bucket | — | Named `s3-incident-report-bucket` |

---

## Quick Start (under 30 minutes)

### Step 1 — Clone the repo

```bash
git clone https://github.com/<your-username>/incident_reporting.git
cd incident_reporting
```

### Step 2 — Set up the database

Connect to your PostgreSQL instance and run:

```bash
psql -h <your-db-host> -U postgres -f scripts/init_db.sql
```

> Update the `db_admin` password in `init_db.sql` before running.

### Step 3 — Create Kubernetes secrets and config

Copy the example file and fill in your actual values:

```bash
cp k8s/create_secrets.sh.example k8s/create_secrets.sh
chmod +x k8s/create_secrets.sh
./k8s/create_secrets.sh
```

This creates:
- `app-secret` — DB credentials, OpenAI key, AWS keys, JWT secret, admin password
- `app-env-variables` — service URLs (escalation and triage agent internal URLs)

### Step 4 — Build Docker images

```bash
# Start Minikube (skip if using an existing cluster)
minikube start

# Point Docker to Minikube's daemon so images are available in-cluster
eval $(minikube docker-env)

# Build all images
docker build -t 311-ingestor:latest ./311_ingestor
docker build -t client-api:latest ./client
docker build -t triage-agent:latest ./triage_agent
docker build -t escalation-agent:latest ./escalation_agent
```

### Step 5 — Deploy to Kubernetes

```bash
kubectl apply -f k8s/postgres_db.yml
kubectl apply -f k8s/triage_agent_deployment.yml
kubectl apply -f k8s/escalation_agent_deployment.yml
kubectl apply -f k8s/client_api_deployment.yml
kubectl apply -f k8s/311_ingestor_deployment.yml
```

Verify all pods are running:

```bash
kubectl get pods
# All pods should show STATUS: Running
```

### Step 6 — Access the dashboard

```bash
kubectl port-forward service/client-api-service 8000:80
```

Open `http://localhost:8000` in your browser.

**Default login:**
- Username: `admin`
- Password: whatever you set as `ADMIN_PASSWORD` in the secrets

---

## Dashboard Walkthrough

| View | What it shows |
|------|--------------|
| **All Incidents** | Live feed of classified incidents with AI severity + reasoning |
| **Critical Alerts** | Filter to CRITICAL-only incidents |
| **Needs Review** | Incidents the system flagged for human verification |
| **Accuracy Report** | AI accuracy per prompt version vs human ground truth |
| **Drift Check** | Detects if model accuracy is degrading over time |
| **Bias Check** | Flags geographic (zip code) accuracy disparities |

**Human-in-the-loop actions available per incident:**
- ✅ Confirm AI decision
- ❌ Reject (flags for re-review)
- 🔄 Override severity (LOW / MEDIUM / CRITICAL) with notes — logged in `transformation_log`

---

## PolicyEngine Rules

The `PolicyEngine` in `triage_agent/policy_engine.py` enforces three hard rules **after** the AI responds:

| Policy | Trigger | Action |
|--------|---------|--------|
| Safety Keyword Override | Description contains: fire, gas, smoke, explosion, collapsed, flood, earthquake, emergency | Force CRITICAL + flag for human review |
| SLA Assignment | Every incident | Assigns resolution deadline: CRITICAL=2h, HIGH=4h, MEDIUM=24h, LOW=3d |
| Low Confidence Guardrail | AI confidence < 0.8 | Flag for human review regardless of severity |

---

## Prometheus Metrics

Each agent exposes metrics on port `9090`:

| Metric | Agent | Type |
|--------|-------|------|
| `triage_requests_total` | Triage | Counter |
| `triage_classification_seconds` | Triage | Histogram |
| `triage_severity_total{severity}` | Triage | Counter |
| `escalation_requests_total` | Escalation | Counter |
| `decide_escalation_seconds` | Escalation | Histogram |
| `escalation_severity_total{severity}` | Escalation | Counter |

---

## Troubleshooting

**Pods crash on startup:**
```bash
kubectl logs <pod-name>
# Most common cause: secrets not created. Re-run create_secrets.sh
```

**Dashboard returns 503:**
```bash
# DB not reachable — check DB_HOST in your secret matches actual host
kubectl describe secret app-secret
```

**Images not building with `eval $(minikube docker-env)`:**
```bash
# Confirm you're in the right shell session
minikube docker-env
# Re-run eval $(...) in your current terminal
```

**Port-forward drops:**
```bash
# Re-run port-forward — it's a foreground process
kubectl port-forward service/client-api-service 8000:80
```

---

## Running Tests

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run all tests
pytest tests/ -v

# Run a specific test file
pytest tests/test_policy_engine.py -v

# Run with coverage report
pytest tests/ --cov=triage_agent --cov-report=term-missing
```

### Test Suite

| # | Test File | Tests | What It Verifies |
|---|-----------|-------|-----------------|
| 1 | `test_policy_engine.py` | 32 | All 3 PolicyEngine rules: safety keyword override, SLA deadlines, confidence guardrails, edge cases and combined scenarios |
| 2 | `test_integration_e2e.py` | 2 | Full pipeline end-to-end: PII redaction, policy override to CRITICAL, JWT security gate — against live Kubernetes cluster |
| 3 | `test_performance_latency.py` | 2 | Report endpoint response time and client timeout handling against live system |
| 4 | `test_security_tokens.py` | 2 | Expired tokens and malformed tokens both correctly rejected with 401 — JWT gate is locked |
| 5 | `test_pii_logs.py` | 1 | PII (emails, phone numbers) never appears in logs or reaches the LLM |
| 6 | `test_policy_idempotence.py` | 1 | Same input always produces same output — PolicyEngine is stateless and deterministic |
| 7 | `test_api_contract.py` | 1 | Incident API returns correct schema with all required fields and correct data types |

**Total: 41 tests across 7 files covering unit, integration, performance, security, and contract layers.**

### Why these tests matter

The PolicyEngine is the safety-critical layer of this system — it enforces rules that override AI decisions in life-safety scenarios. The integration tests verify the full pipeline works end to end against a live Kubernetes cluster, not mocks. The PII test proves sensitive data never reaches the LLM. Together these tests cover every layer of the system from individual rules to full pipeline behaviour.

---

## Tech Stack

`Python 3.11` · `FastAPI` · `FastMCP` · `OpenAI GPT-4o` · `PostgreSQL` · `psycopg2` · `Docker` · `Kubernetes` · `AWS S3` · `Prometheus` · `Tailwind CSS` · `JWT Auth`
