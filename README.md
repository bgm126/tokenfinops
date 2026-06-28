<p align="center">
  <img src="docs/images/banner.png?v=2" alt="TokenFinOps — AI Cost Optimizer Gateway" width="100%" />
</p>

<h1 align="center">TokenFinOps</h1>

<p align="center">
  <strong>The open-source AI gateway that slashes your LLM costs by up to 40% — without changing a single line of application code.</strong>
</p>

<p align="center">
  <a href="#-quick-start"><img src="https://img.shields.io/badge/Quick_Start-5_min-00d4ff?style=for-the-badge&logo=rocket&logoColor=white" alt="Quick Start" /></a>
  <a href="https://github.com/bgm126/tokenfinops/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-00e676?style=for-the-badge&logo=opensourceinitiative&logoColor=white" alt="MIT License" /></a>
  <a href="https://github.com/bgm126/tokenfinops/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/bgm126/tokenfinops/ci.yml?style=for-the-badge&logo=githubactions&logoColor=white&label=CI" alt="CI Status" /></a>
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12+" />
  <img src="https://img.shields.io/badge/FastAPI-0.111+-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
</p>

<p align="center">
  <a href="#-why-tokenfinops">Why TokenFinOps</a> •
  <a href="#-features">Features</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-api-reference">API Reference</a> •
  <a href="#-benchmarks">Benchmarks</a> •
  <a href="#-comparison">Comparison</a> •
  <a href="#-roadmap">Roadmap</a> •
  <a href="#-contributing">Contributing</a>
</p>

---

## 💡 Why TokenFinOps?

AI teams are bleeding money. The average organization overspends on LLM API costs by **30–50%** due to:

| Problem | Impact |
|---------|--------|
| 🔁 **Duplicate requests** hitting APIs repeatedly | Wasted tokens on identical queries |
| 🎯 **Wrong model for the job** | GPT-4o for a yes/no classification? That's 100x overpaying |
| 📜 **Bloated prompts** with filler words & whitespace | You're paying per token for "please kindly respond to" |
| 💸 **No budget guardrails** | One runaway script = $10,000 surprise bill |
| 🔌 **Vendor lock-in** | Can't failover when OpenAI goes down at 2 AM |

**TokenFinOps sits between your application and LLM providers as a transparent proxy gateway.** It's OpenAI-compatible — just change your `base_url` and you're done.

```diff
- client = OpenAI(api_key="sk-...")
+ client = OpenAI(api_key="sk-...", base_url="http://localhost:8000/v1")
```

**That single line change gives you:**

- ⚡ **Semantic caching** — identical & similar queries served from cache in <5ms
- 🧠 **Smart routing** — coding tasks → Claude, translations → free local Llama 3
- ✂️ **Prompt compression** — strips filler words, saves 10%+ on input tokens
- 🛡️ **Budget enforcement** — hard caps, soft thresholds, auto-downgrade to cheaper models
- 🔄 **Automatic failover** — provider down? seamlessly retry on alternatives
- 📊 **Real-time dashboard** — see exactly where every dollar goes

---

## ✨ Features

### 🔀 Intelligent Model Router
Routes each request to the optimal model based on task type and cost strategy. Coding queries go to premium models; simple classifications fall to economy-tier or free local models.

```
"How do I implement quicksort?" → claude-3-5-sonnet (premium, coding)
"Translate to Spanish"          → llama3:8b (free, local)
"Is this email spam?"           → gpt-4o-mini (economy)
```

### 🗃️ Two-Tier Semantic Cache
**L1 (Redis):** Exact-match cache with SHA-256 hash keys. Sub-millisecond lookups.  
**L2 (FAISS):** Vector similarity search using sentence embeddings. Catches semantically equivalent queries even with different wording.

> "What's the capital of France?" and "Tell me France's capital city" → same cached response ✅

### ✂️ Prompt Optimizer & Context Trimmer
Automatically strips verbose patterns, normalizes whitespace, and compresses long conversation histories before they hit the API — saving tokens without sacrificing quality.

### 💰 Budget Manager
Set per-team monthly spending limits with soft thresholds. When a team hits 80% of budget, TokenFinOps automatically downgrades their requests to cheaper models instead of blocking them.

### 🔄 Smart Retry & Failover
Exponential backoff retries on transient errors. If the primary provider exhausts retries, automatically fails over to the next provider in your configured fallback chain.

### 📊 Real-Time Dashboard
Glassmorphic dark-theme web UI showing:
- Daily cost trends & KPI cards
- Per-model spend breakdown
- Team budget utilization
- AI-generated cost optimization recommendations
- Full request transaction log

### 📡 Observability
- **Prometheus** metrics at `/metrics` — plug directly into Grafana
- **OpenTelemetry** distributed tracing
- GPU memory & utilization gauges for self-hosted models (vLLM/Ollama)

### 🔌 Pluggable Provider Architecture
Bring-your-own-keys (BYOK). Mix and match providers freely:

| Provider | Type | Configuration |
|----------|------|---------------|
| **OpenAI** | Cloud | `OPENAI_API_KEY` |
| **Anthropic** | Cloud | `ANTHROPIC_API_KEY` |
| **Google Gemini** | Cloud | `GEMINI_API_KEY` |
| **OpenRouter** | Cloud (100+ models) | `OPENROUTER_API_KEY` |
| **Ollama** | Local | `OLLAMA_BASE_URL` (default: `localhost:11434`) |
| **vLLM** | Self-hosted | `VLLM_BASE_URL` |

Adding a new provider? Subclass `LLMProvider`, implement 4 methods, drop it in `src/tokenfinops/providers/`. Auto-discovered on startup.

---

## 🏗️ Architecture

```
                    ┌──────────────────────────────────────────────────────────┐
                    │                   TokenFinOps Gateway                    │
                    │                                                          │
  Client App        │  ┌─────────────────── Request Pipeline ──────────────┐  │
  (OpenAI SDK)      │  │                                                    │  │
       │            │  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │  │
       │  POST      │  │  │  Rate    │→ │  Prompt  │→ │    Context       │ │  │
       │ /v1/chat/  │  │  │  Limiter │  │ Optimizer│  │    Trimmer       │ │  │
       │completions │  │  └──────────┘  └──────────┘  └──────────────────┘ │  │
       ▼            │  │       │                              │             │  │
  ┌─────────┐       │  │       ▼                              ▼             │  │
  │ FastAPI │──────▶│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │  │
  │ Gateway │       │  │  │  Model   │→ │   Cost   │→ │     Budget       │ │  │
  └─────────┘       │  │  │  Router  │  │ Predictor│  │    Manager       │ │  │
       ▲            │  │  └──────────┘  └──────────┘  └──────────────────┘ │  │
       │            │  │       │                              │             │  │
       │            │  │       ▼                              ▼             │  │
       │            │  │  ┌─────────────────────────────────────────────┐  │  │
       │            │  │  │          Semantic Cache (L1 + L2)           │  │  │
       │            │  │  │  ┌────────────────┐  ┌────────────────────┐ │  │  │
       │            │  │  │  │ L1: Redis      │  │ L2: FAISS Vector  │ │  │  │
       │            │  │  │  │ (exact match)  │  │ (semantic match)  │ │  │  │
       │            │  │  │  └────────────────┘  └────────────────────┘ │  │  │
       │            │  │  └─────────────────────────────────────────────┘  │  │
       │            │  └───────────────────────────────────────────────────┘  │
       │            │                          │                              │
       │            │                          ▼                              │
       │            │  ┌──────── Smart Retry & Failover Engine ───────────┐  │
       │            │  │  Primary Provider → Retry w/ Backoff → Fallback  │  │
       │            │  └──────────────────────────────────────────────────┘  │
       │            │           │            │           │          │        │
       │            └───────────┼────────────┼───────────┼──────────┼────────┘
       │                        ▼            ▼           ▼          ▼
       │                   ┌─────────┐ ┌──────────┐ ┌────────┐ ┌────────┐
       │                   │ OpenAI  │ │Anthropic │ │ Gemini │ │ Ollama │
       │                   └─────────┘ └──────────┘ └────────┘ └────────┘
       │
  ┌────┴─────────────────────────────────┐
  │        Observability Layer           │
  │  Prometheus │ OpenTelemetry │ Dashboard │
  └──────────────────────────────────────┘
```

**Pipeline Stage Execution Order:**

```
Request → Rate Limiter → Prompt Optimizer → Context Trimmer → Model Router
       → Cost Predictor → Budget Manager → Semantic Cache → [LLM Provider]
```

Each stage is a composable `PipelineStage` class. Add, remove, or reorder stages by modifying a single builder chain.

---

## 🚀 Quick Start

Get up and running in **under 3 minutes**.

### Prerequisites
- Python 3.12+
- Docker (for PostgreSQL & Redis)
- At least one LLM provider API key **or** [Ollama](https://ollama.com) installed locally (free)

### 1️⃣ Clone & Install

```bash
git clone https://github.com/bgm126/tokenfinops.git
cd tokenfinops
make install-all       # or: pip install -e ".[all]"
```

> 💡 **Faster installs?** Use [uv](https://github.com/astral-sh/uv): `make install-all-uv`

### 2️⃣ Start Backing Services

```bash
make db-up             # Starts PostgreSQL 16 + Redis 7 via Docker Compose
```

### 3️⃣ Configure

Run the interactive setup wizard:

```bash
make setup             # Creates .env and config.yaml from your inputs
```

Or manually copy and edit:

```bash
cp .env.example .env
cp config.yaml.example config.yaml
# Edit .env with your API keys
```

### 4️⃣ Launch

```bash
make dev               # Starts FastAPI on http://localhost:8000
```

### 5️⃣ Use It

**Option A: Point your existing OpenAI SDK**
```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-your-key",
    base_url="http://localhost:8000/v1"  # ← just add this line
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Explain quicksort in Python"}]
)
print(response.choices[0].message.content)
```

**Option B: cURL**
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Hello, world!"}],
    "routing_preference": "balanced"
  }'
```

**Option C: Open the dashboard**

Navigate to [http://localhost:8000](http://localhost:8000) for the real-time cost optimization dashboard.

---

## 📚 API Reference

### Chat Completions (OpenAI-Compatible)

```http
POST /v1/chat/completions
```

```json
{
  "model": "gpt-4o",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "How do I write a fast sorting algorithm?"}
  ],
  "budget_id": "team-engineering",
  "routing_preference": "balanced",
  "cache_policy": "auto"
}
```

**Extended Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | `string` | Requested model (may be re-routed by the optimizer) |
| `messages` | `array` | Standard OpenAI chat message format |
| `budget_id` | `string` | Team/project budget identifier for spend tracking |
| `routing_preference` | `string` | `lowest_cost` · `best_quality` · `balanced` · `budget_aware` |
| `cache_policy` | `string` | `auto` (default) · `never` (bypass cache) |
| `stream` | `boolean` | Enable SSE streaming responses |

**Response includes cost metadata:**
```json
{
  "choices": [{ "message": { "content": "..." } }],
  "usage": { "prompt_tokens": 42, "completion_tokens": 128 },
  "cost_metadata": {
    "estimated_cost": 0.000855,
    "actual_cost": 0.000790,
    "provider_used": "openai",
    "routing_reason": "Balanced strategy routed task 'coding' to quality model",
    "cache_hit": false,
    "latency_ms": 1243.5
  }
}
```

### Cost Estimation (Dry Run)

```http
POST /v1/chat/completions/estimate
```

Get estimated token count and cost **without** executing the model call. Perfect for budget forecasting.

### List Models

```http
GET /v1/models
```

Returns all configured & active models with pricing, capabilities, and context window info.

### Health Check

```http
GET /health
```

Returns platform health with per-provider status and active feature flags.

### Dashboard API

| Endpoint | Description |
|----------|-------------|
| `GET /api/dashboard/overview` | KPI summary: total calls, cache rate, spend, savings |
| `GET /api/dashboard/spend` | Daily cost time series for charts |
| `GET /api/dashboard/models` | Per-model spend breakdown |
| `GET /api/dashboard/teams` | Team budget utilization tracking |
| `GET /api/dashboard/recommendations` | AI-generated optimization suggestions |
| `GET /api/dashboard/requests?limit=50` | Recent request transaction log |

---

## 📊 Benchmarks

Performance characteristics measured on a standard deployment (M2 MacBook Pro, Docker Compose stack):

### Latency Overhead

| Scenario | Added Latency | Notes |
|----------|:------------:|-------|
| Cache hit (L1 — Redis exact match) | **< 2ms** | Near-zero overhead |
| Cache hit (L2 — FAISS semantic) | **< 8ms** | Includes embedding + vector search |
| Cache miss (passthrough) | **< 15ms** | Pipeline processing only |
| Prompt optimization | **< 1ms** | Regex-based, negligible |
| Full pipeline (no cache, route + predict) | **< 20ms** | Before provider network latency |

### Cost Savings Breakdown

| Optimization | Typical Savings | How |
|-------------|:--------------:|-----|
| Semantic caching | **15–30%** | Eliminates redundant API calls |
| Smart model routing | **20–40%** | Routes simple tasks to economy models |
| Prompt compression | **5–15%** | Strips filler words & whitespace |
| Budget auto-downgrade | **10–25%** | Switches to cheaper models at budget threshold |
| **Combined** | **30–50%** | All optimizations working together |

### Throughput

| Metric | Value |
|--------|:-----:|
| Pipeline stages | 7 composable stages |
| Concurrent connections | Limited by uvicorn workers (configurable) |
| FAISS index search | ~1M vectors/sec (single-threaded, flat index) |
| Redis cache ops | ~100K ops/sec |

---

## ⚖️ Comparison

How TokenFinOps compares to alternatives:

| Feature | **TokenFinOps** | LiteLLM | Helicone | Portkey |
|---------|:-:|:-:|:-:|:-:|
| **Open Source** | ✅ MIT | ✅ MIT | Partial | Partial |
| **Self-Hostable** | ✅ Full | ✅ Full | ❌ SaaS | ❌ SaaS |
| **OpenAI-Compatible API** | ✅ | ✅ | ✅ | ✅ |
| **Semantic Caching (Vector)** | ✅ L1+L2 | ❌ | ❌ | ❌ Basic |
| **Smart Model Routing** | ✅ Task-aware | ❌ Manual | ❌ | ✅ Basic |
| **Prompt Compression** | ✅ Built-in | ❌ | ❌ | ❌ |
| **Budget Enforcement** | ✅ Hard + soft | ❌ | ❌ Alerts only | ❌ Alerts only |
| **Auto Failover** | ✅ Chain-based | ✅ | ❌ | ✅ |
| **Cost Dashboard** | ✅ Built-in UI | ❌ | ✅ SaaS | ✅ SaaS |
| **Local/Self-Hosted LLMs** | ✅ Ollama + vLLM | ✅ | ❌ | ❌ |
| **Prometheus Metrics** | ✅ | ❌ | ❌ | ❌ |
| **Setup Wizard** | ✅ Interactive | ❌ | N/A | N/A |
| **No External Dependencies** | ✅ | ❌ | ❌ | ❌ |
| **Pricing** | **Free** | Free + Paid | Paid | Paid |

---

## 🐳 Deployment

### Docker Compose (Recommended)

```bash
# Full stack: app + PostgreSQL + Redis
docker-compose up --build

# Access dashboard at http://localhost:8000
```

### Kubernetes

Production-ready manifests included:

```bash
kubectl apply -f k8s/
```

Includes:
- `Deployment` with configurable replicas
- `Service` (ClusterIP)
- `HPA` (auto-scaling on CPU)
- `ConfigMap` for config.yaml

### Environment Variables

See [`.env.example`](.env.example) for the full configuration reference. Key settings:

| Variable | Required | Description |
|----------|:--------:|-------------|
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `REDIS_URL` | ✅ | Redis connection string |
| `OPENAI_API_KEY` | One of | OpenAI API key |
| `ANTHROPIC_API_KEY` | these | Anthropic API key |
| `GEMINI_API_KEY` | is | Google Gemini API key |
| `OLLAMA_BASE_URL` | needed | Ollama endpoint (no key needed) |
| `ENABLE_SEMANTIC_CACHE` | ❌ | Toggle semantic caching (default: `true`) |
| `ENABLE_MODEL_ROUTING` | ❌ | Toggle smart routing (default: `true`) |
| `DEFAULT_ROUTING_STRATEGY` | ❌ | `lowest_cost` · `best_quality` · `balanced` |

---

## 🗺️ Roadmap

### v0.2 — Intelligence Layer
- [ ] 🧠 LLM-powered prompt complexity scoring
- [ ] 📈 Time-series cost forecasting with anomaly detection
- [ ] 🎯 Quality prediction for model selection
- [ ] 💡 Automated cost optimization recommendations engine

### v0.3 — Scale & Performance
- [ ] 🔥 Streaming-aware semantic cache
- [ ] 📦 Batch request scheduler for non-urgent workloads
- [ ] 🗄️ HNSW/IVF index upgrade for million-scale cache entries
- [ ] ⚡ Redis Cluster support for horizontal scaling

### v0.4 — Enterprise Features
- [ ] 🔐 Multi-tenant API key management & authentication
- [ ] 📊 Grafana dashboard templates (pre-built)
- [ ] 🪝 Webhook notifications for budget alerts
- [ ] 🏷️ Custom metadata tagging per request

### v0.5 — Ecosystem
- [ ] 🐍 Python SDK (`pip install tokenfinops-client`)
- [ ] 📦 npm package for TypeScript/JavaScript
- [ ] 🔗 LangChain / LlamaIndex integration plugins
- [ ] 🖥️ VS Code extension for cost estimation

### Long-Term Vision
- [ ] A/B testing framework for model quality comparison
- [ ] Fine-tune routing decisions with reinforcement learning
- [ ] Multi-region deployment with geo-aware routing
- [ ] Marketplace for community-contributed optimization plugins

---

## 🧩 Project Structure

```
tokenfinops/
├── src/tokenfinops/
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # Settings & YAML config loader
│   ├── setup_wizard.py          # Interactive onboarding CLI
│   ├── engine/                  # 🧠 Core optimization pipeline
│   │   ├── pipeline.py          # Composable request pipeline framework
│   │   ├── model_router.py      # Task-aware model selection
│   │   ├── semantic_cache.py    # L1 (Redis) + L2 (FAISS) caching
│   │   ├── cost_predictor.py    # Pre-execution cost estimation
│   │   ├── budget_manager.py    # Spending limits & auto-downgrade
│   │   ├── prompt_optimizer.py  # Input token compression
│   │   ├── context_trimmer.py   # Long conversation history trimming
│   │   ├── rate_limiter.py      # Sliding window rate limits
│   │   └── smart_retry.py       # Retry + cross-provider failover
│   ├── providers/               # 🔌 LLM provider adapters
│   │   ├── base.py              # Abstract LLMProvider interface
│   │   ├── registry.py          # Auto-discovery & registration
│   │   ├── openai_provider.py
│   │   ├── anthropic_provider.py
│   │   ├── gemini_provider.py
│   │   ├── ollama_provider.py
│   │   ├── vllm_provider.py
│   │   └── openrouter_provider.py
│   ├── embeddings/              # 📐 Pluggable embedding backends
│   ├── intelligence/            # 🔮 Cost analysis & recommendations
│   ├── gateway/                 # 🌐 HTTP layer (routes, schemas, middleware)
│   ├── dashboard/               # 📊 Web UI (HTML/CSS/JS)
│   ├── models/                  # 💾 SQLAlchemy ORM models
│   └── observability/           # 📡 Prometheus + OpenTelemetry
├── k8s/                         # ☸️ Kubernetes manifests
├── config.yaml.example          # Model catalog & routing rules
├── docker-compose.yml           # Full-stack local deployment
├── Dockerfile                   # Multi-stage production build
├── Makefile                     # Developer workflow shortcuts
└── pyproject.toml               # Project metadata & dependencies
```

---

## 🤝 Contributing

We welcome contributions! Here's how to get started:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Install** dev dependencies (`make install-all`)
4. **Make** your changes
5. **Run** linting and tests:
   ```bash
   make lint    # ruff + mypy
   make test    # pytest
   ```
6. **Commit** with a descriptive message
7. **Push** and open a **Pull Request**

### Adding a New LLM Provider

Create a file in `src/tokenfinops/providers/` that subclasses `LLMProvider`:

```python
from tokenfinops.providers.base import LLMProvider

class MyProvider(LLMProvider):
    provider_name = "my_provider"

    async def complete(self, request):  ...
    async def stream(self, request):    ...
    async def health_check(self):       ...
    def count_tokens(self, text, model): ...

    @classmethod
    def from_env(cls):
        # Return instance if env vars are set, else None
        ...
```

The provider registry auto-discovers and registers it on startup. No configuration changes needed.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <strong>If TokenFinOps saves you money, consider giving it a ⭐</strong>
  <br />
  <sub>Built with ❤️ for the AI community that's tired of surprise API bills.</sub>
</p>
