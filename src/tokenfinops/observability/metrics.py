from prometheus_client import Counter, Histogram, Gauge

# Request counter
requests_total = Counter(
    "tokenfinops_requests_total",
    "Total number of chat completions requested",
    ["model", "provider", "cache_hit", "status"]
)

# Cost counter
cost_dollars = Counter(
    "tokenfinops_cost_dollars_total",
    "Total dollars spent on model completion requests",
    ["model", "provider"]
)

# Token counter
tokens_total = Counter(
    "tokenfinops_tokens_total",
    "Total tokens processed",
    ["model", "provider", "direction"]  # direction: input or output
)

# Token savings counter
tokens_saved_total = Counter(
    "tokenfinops_tokens_saved_total",
    "Total tokens saved by caching or prompt optimizations",
    ["optimization_type"]  # caching or prompt_optimization
)

# Latency histogram
request_latency_seconds = Histogram(
    "tokenfinops_request_latency_seconds",
    "Time spent processing chat completion requests",
    ["model", "provider"],
    buckets=(0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, 30.0, 60.0)
)

# Active Provider state (1 for active, 0 for inactive/unconfigured)
provider_active_status = Gauge(
    "tokenfinops_provider_active",
    "Active state of configured LLM providers",
    ["provider"]
)

# Budget Remaining gauge
budget_utilization_ratio = Gauge(
    "tokenfinops_budget_utilization_ratio",
    "Utilization ratio of team budget quotas",
    ["team_id"]
)

class MetricsCollector:
    """Helper class to record metrics across the RequestPipeline stages."""

    @staticmethod
    def record_request(model: str, provider: str, input_tokens: int, output_tokens: int, cost: float, latency_ms: float, cache_hit: bool, status: str):
        hit_str = "true" if cache_hit else "false"
        
        requests_total.labels(model=model, provider=provider, cache_hit=hit_str, status=status).inc()
        cost_dollars.labels(model=model, provider=provider).inc(cost)
        
        tokens_total.labels(model=model, provider=provider, direction="input").inc(input_tokens)
        tokens_total.labels(model=model, provider=provider, direction="output").inc(output_tokens)
        
        latency_sec = latency_ms / 1000.0
        request_latency_seconds.labels(model=model, provider=provider).observe(latency_sec)

    @staticmethod
    def record_savings(saved_tokens: int, optimization_type: str):
        if saved_tokens > 0:
            tokens_saved_total.labels(optimization_type=optimization_type).inc(saved_tokens)

# GPU metrics for self-hosted execution monitoring
gpu_memory_used_bytes = Gauge(
    "tokenfinops_gpu_memory_used_bytes",
    "GPU memory consumption in bytes",
    ["gpu_id"]
)

gpu_utilization_ratio = Gauge(
    "tokenfinops_gpu_utilization_ratio",
    "GPU engine execution utilization percentage",
    ["gpu_id"]
)

class GPUMetricsCollector:
    @staticmethod
    def record_gpu_metrics(gpu_id: str, memory_bytes: int, utilization: float):
        gpu_memory_used_bytes.labels(gpu_id=gpu_id).set(memory_bytes)
        gpu_utilization_ratio.labels(gpu_id=gpu_id).set(utilization)
