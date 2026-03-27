# AI-Powered Incident Reporting System

An end-to-end, production-grade system that ingests real SF 311 public complaints, classifies them with GPT-4o, and surfaces everything through a **human-in-the-loop governance dashboard** — built with enterprise-grade AI governance, security, observability, and alerting baked in from day one.

![Python](https://img.shields.io/badge/Python-3.11-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-latest-green) ![Kubernetes](https://img.shields.io/badge/Kubernetes-live-blue) ![GPT-4o](https://img.shields.io/badge/GPT--4o-OpenAI-orange) ![Prometheus](https://img.shields.io/badge/Prometheus-metrics-red) ![Grafana](https://img.shields.io/badge/Grafana-dashboards-yellow) ![Tests](https://img.shields.io/badge/Tests-41%20passing-brightgreen)

---

## Why This Project Exists

Most GenAI projects don't fail during development. They fail after deployment — not because of the model, but because nobody knows what's happening in production.

This system is built to answer the questions that matter:
- Why did cost suddenly spike?
- Is latency coming from the model or the API?
- Are we silently failing and retrying?
- Is the model's behavior drifting over time?
- Are we being alerted **before** users notice a problem?

---

## AI Governance Framework

Most AI projects skip this entirely. This system treats governance as a **first-class feature**, not an afterthought.

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
│  Policy B: SLA Assignment                   │
│  → CRITICAL=2h, HIGH=4h, MED=24h, LOW=3d   │
│                                             │
│  Policy C: Confidence Guardrail             │
│  → confidence < 0.8 → flag for review       │
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

## LLM Observability & Monitoring

Built using Prometheus for metrics collection and Grafana for visualization, integrated with the live multi-agent system.

### Dashboards

![LLM Observability Dashboard](screenshots/dashboard/grafana_observability.png)

**1. Cost Intelligence**
- Cost per request, per second, projected daily cost
- Token usage patterns over time

**2. Latency & SLOs**
- HTTP vs LLM latency (p95)
- Availability tracking — currently at 100%

**3. Reliability Signals**
- Error rates and retry behavior *(in progress)*

**4. Anomaly Detection**
- Traffic drops, token spikes, latency anomalies

**5. Model Drift Monitoring**
- Severity distribution over time
- Entropy-based drift indicator (current: 0.639)

### Prometheus Metrics

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

## Alerting System

A production-grade alerting layer sits on top of Prometheus, firing Grafana alerts when the system crosses critical thresholds. Alerts are scoped to real operational signals — not just infrastructure health, but **AI-specific failure modes** like confidence degradation and LLM latency spikes.

### Alert Categories

#### 🤖 AI / LLM Alerts

| Alert | Severity | Trigger Condition | What It Means |
|-------|----------|-------------------|---------------|
| `LowClassificationConfidence` | ⚠️ Warning | Confidence drops below **0.8** | The AI is uncertain — human review needed before acting on the label |
| `HighLLMLatency` | 🔴 Critical | P95 LLM latency exceeds **5 seconds** for 2 minutes | Model response time has degraded; downstream SLAs are at risk |

#### ☸️ Kubernetes Infrastructure Alerts

| Alert | Severity | Trigger Condition | What It Means |
|-------|----------|-------------------|---------------|
| `PodCrashLooping` | ⚠️ Warning | Pod restarts **> 3 times** in 15 minutes | A service is repeatedly failing — likely a config or dependency issue |
| `KubeDeploymentReplicasMismatch` | ⚠️ Warning | Deployment replica count mismatches desired state for **> 15 minutes** | Kubernetes cannot schedule the expected number of pods |
| `HighMemoryUsage` | ⚠️ Warning | Memory usage exceeds **500MB** | A pod is approaching its memory limit — risk of OOM termination |

### Live Alert Examples

**LowClassificationConfidence** — fires when the triage agent's confidence falls below the 0.8 threshold, directly linking to the PolicyEngine's confidence guardrail:

```
Alert:       LowClassificationConfidence
Severity:    warning
Summary:     Classification confidence dropped below 0.8
Description: AI model classification confidence has dropped below acceptable
             threshold. Current confidence: 0.6.
Instance:    10.244.2.177:9090
Pod:         triage-agent-deployment-5b9df7cdf5-hcbch
```

**HighLLMLatency** — fires when GPT-4o response times spike beyond the 5-second SLO, surfacing model-side degradation before it reaches users:

```
Alert:       HighLLMLatency
Severity:    critical
Summary:     LLM Latency is too high
Description: P95 latency is 6.25s, which is above the 5s threshold
             for 2 minutes.
Instance:    10.244.2.176:9090
```

**PodCrashLooping** — fires when the 311 ingestor pod enters a crash loop, catching infrastructure instability early:

```
Alert:       PodCrashLooping
Severity:    warning
Summary:     Pod is crash looping
Description: Pod ingestor-311-deployment-6cb7b85fcc-pnrp7 has restarted more
             than 3 times in the last 15 minutes.
Instance:    10.244.2.138:8080
```

### Triage Agent Log — End-to-End Trace

The triage agent emits structured JSON logs at each pipeline stage, making every classification fully traceable by `trace_id` and `incident_id`:

```
INFO: Received incident for classification
INFO: Sending request to LLM
INFO: Parsing LLM response
INFO: Final severity after policy enforcement
INFO: Inserting incident into DB
INFO: Classification complete
```

Each log entry carries `{"timestamp", "level", "logger", "message", "module", "func_name", "trace_id", "incident_id"}` — enabling log-based alerting and full request tracing.

### Alert Design Philosophy

The alerting layer is built around two principles:

**1. AI-aware alerts, not just infra alerts** — standard Kubernetes monitoring watches pods and memory. This system adds AI-specific signals (confidence scores, LLM latency) that generic infrastructure tools miss entirely.

**2. Alerts map directly to governance guardrails** — `LowClassificationConfidence` fires at the same 0.8 threshold enforced by the `PolicyEngine`. The alert and the safety rule share a single source of truth.

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
           │
           ▼
     Prometheus → Grafana → Alertmanager
```

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
│   ├── prometheus.yml       # Prometheus scrape config
	├──alert_rules.yml		 # Grafana alert rules (LLM + infra)
│   └──alertmanager.yml              
│
├── screenshots/
│   ├── kubernetes/          # kubectl get pods, logs screenshots
│   ├── dashboard/           # UI and governance page screenshots
│   ├── alerts/              # Grafana alert firing screenshots
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
git clone https://github.com/moni0811/Incident_Reporting.git
cd Incident_Reporting
```

### Step 2 — Set up the database

```bash
psql -h <your-db-host> -U postgres -f scripts/init_db.sql
```

### Step 3 — Create Kubernetes secrets

```bash
cp k8s/create_secrets.sh.example k8s/create_secrets.sh
chmod +x k8s/create_secrets.sh
./k8s/create_secrets.sh
```

### Step 4 — Build Docker images

```bash
minikube start
eval $(minikube docker-env)

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

kubectl get pods  # All pods should show STATUS: Running
```

### Step 6 — Access the dashboard

```bash
kubectl port-forward service/client-api-service 8000:80
```

Open `http://localhost:8000` — default login is `admin` / your `ADMIN_PASSWORD` secret.

---

## Dashboard Walkthrough

| View | What it shows |
|------|---------------|
| **All Incidents** | Live feed of classified incidents with AI severity + reasoning |
| **Critical Alerts** | Filter to CRITICAL-only incidents |
| **Needs Review** | Incidents flagged for human verification |
| **Accuracy Report** | AI accuracy per prompt version vs human ground truth |
| **Drift Check** | Detects if model accuracy is degrading over time |
| **Bias Check** | Flags geographic (zip code) accuracy disparities |

Human-in-the-loop actions per incident: ✅ Confirm · ❌ Reject · 🔄 Override severity with notes

---

## Running Tests

```bash
pip install -r requirements-test.txt
pytest tests/ -v
pytest tests/ --cov=triage_agent --cov-report=term-missing
```

### Test Suite

| # | Test File | Tests | What It Verifies |
|---|-----------|-------|------------------|
| 1 | `test_policy_engine.py` | 32 | All 3 PolicyEngine rules: safety keywords, SLA deadlines, confidence guardrails |
| 2 | `test_integration_e2e.py` | 2 | Full pipeline end-to-end against live Kubernetes cluster |
| 3 | `test_performance_latency.py` | 2 | Response time and timeout handling |
| 4 | `test_security_tokens.py` | 2 | Expired and malformed tokens rejected with 401 |
| 5 | `test_pii_logs.py` | 1 | PII never appears in logs or reaches the LLM |
| 6 | `test_policy_idempotence.py` | 1 | Same input always produces same output |
| 7 | `test_api_contract.py` | 1 | Correct schema, required fields, data types |

**Total: 41 tests — unit, integration, performance, security, and contract layers. All passing against a live Kubernetes cluster.**

---

## Tech Stack

`Python 3.11` · `FastAPI` · `FastMCP` · `OpenAI GPT-4o` · `PostgreSQL` · `Docker` · `Kubernetes` · `Prometheus` · `Grafana` · `Alertmanager` · `AWS S3` · `Tailwind CSS` · `JWT Auth`

---

## Publications / Innovation

- **Invention Disclosure:** Deterministic Text-to-SQL Architecture for Enterprise Databases

---

## What's Next

- Migration to AWS EKS with IRSA for secure AWS access
- Horizontal Pod Autoscaling
- RBAC and NetworkPolicies for cluster security
- OpenTelemetry distributed tracing
- AI-Ops module for automated root cause analysis
- Accuracy evaluation metrics and human feedback loop integration
- Slack integration for alert routing
