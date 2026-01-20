# Log Sampling Design

**Intelligent log sampling to prevent context overflow while maintaining investigation effectiveness.**

## The Problem

Modern observability systems can generate millions of log entries per hour. When an AI agent investigates an incident:

```
❌ Bad Approach:
"Fetch all logs from the last hour"
→ 2 million logs
→ 500MB+ of data
→ Exceeds LLM context window
→ Slow, expensive, ineffective
```

## Our Solution: "Never Load All Data"

IncidentFox implements a partition-first log analysis strategy:

```
✅ Good Approach:
1. Get statistics first (counts, distribution)
2. Use intelligent sampling strategies
3. Progressive drill-down based on findings

→ 50-100 relevant logs
→ ~10KB of data
→ Fits in context
→ Fast, cheap, effective
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Log Analysis Tools                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│   ┌─────────────────┐    ┌─────────────────────────────────┐   │
│   │ get_log_stats() │───▶│         Backend Abstraction      │   │
│   │                 │    │                                   │   │
│   │   sample_logs() │───▶│  ┌────────┐  ┌────────┐        │   │
│   │                 │    │  │Elastic │  │Datadog │  ...    │   │
│   │  search_logs()  │───▶│  │Backend │  │Backend │        │   │
│   └─────────────────┘    │  └────────┘  └────────┘        │   │
│                          └─────────────────────────────────┘   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Supported Backends

| Backend | Implementation | Features |
|---------|----------------|----------|
| **Elasticsearch** | Native ES client | Full aggregations, random sampling |
| **Coralogix** | REST API | Severity distribution, pattern analysis |
| **Datadog** | Logs API | Service filtering, tag-based search |
| **Splunk** | REST API | SPL queries, time-based sampling |
| **CloudWatch** | boto3 | Log groups, filter patterns |

## Tool Workflow

### Step 1: Get Statistics (Always First)

```python
get_log_statistics(
    service="payments-service",
    time_range="1h"
)
```

Returns:
```json
{
  "total_count": 45000,
  "error_count": 234,
  "severity_distribution": {
    "INFO": 38000,
    "WARN": 6500,
    "ERROR": 234,
    "DEBUG": 266
  },
  "top_patterns": [
    {"pattern": "Request processed successfully", "count": 35000},
    {"pattern": "Connection timeout to database", "count": 180},
    {"pattern": "Payment failed: insufficient funds", "count": 54}
  ],
  "recommendation": "Moderate volume (45,000 logs). Sampling recommended."
}
```

### Step 2: Apply Intelligent Sampling

Based on statistics, choose the right strategy:

```python
sample_logs(
    strategy="errors_only",
    service="payments-service",
    time_range="1h",
    sample_size=50
)
```

## Sampling Strategies

### 1. `errors_only` (Default for Incidents)

**Best for:** Incident investigation, root cause analysis

```python
sample_logs(strategy="errors_only", sample_size=50)
```

- Returns only ERROR and CRITICAL level logs
- Most relevant for troubleshooting
- Dramatically reduces volume (typically 99% reduction)

### 2. `around_anomaly`

**Best for:** Correlating events around a specific incident time

```python
sample_logs(
    strategy="around_anomaly",
    anomaly_timestamp="2026-01-19T14:30:00Z",
    window_seconds=60,
    sample_size=100
)
```

- Logs ±60 seconds around the anomaly timestamp
- Captures the exact moment something went wrong
- Useful when you know when the problem started

### 3. `first_last`

**Best for:** Understanding timeline, seeing beginning and end of an issue

```python
sample_logs(strategy="first_last", sample_size=50)
```

- Returns first N/2 and last N/2 logs in the time range
- Shows how the situation evolved
- Good for long-running issues

### 4. `random`

**Best for:** Statistical representation of overall log patterns

```python
sample_logs(strategy="random", sample_size=100)
```

- Random sample across the entire time range
- Unbiased view of what's happening
- Good for understanding baseline behavior

### 5. `stratified`

**Best for:** Balanced view across all severity levels

```python
sample_logs(strategy="stratified", sample_size=100)
```

- Samples proportionally from each severity level
- Ensures you see INFO, WARN, ERROR, etc.
- Good when you need complete picture

## Progressive Drill-Down Pattern

The recommended investigation pattern:

```
1. Statistics → Understand the volume and distribution
       │
       ▼
2. Error Sample → See the actual error messages
       │
       ▼
3. Pattern Search → Find specific error patterns
       │
       ▼
4. Around Anomaly → Zoom into specific timeframes
       │
       ▼
5. Context Fetch → Get logs around specific entries
```

### Example Investigation

```python
# Step 1: What are we dealing with?
stats = get_log_statistics(service="checkout", time_range="1h")
# → 50,000 logs, 500 errors, pattern "Connection refused" appearing 300 times

# Step 2: Get the errors
errors = sample_logs(strategy="errors_only", service="checkout", sample_size=50)
# → 50 error logs, mostly "Connection refused to payment-gateway:5432"

# Step 3: When did this start?
pattern_logs = search_logs_by_pattern(
    pattern="Connection refused",
    service="checkout",
    time_range="1h"
)
# → First occurrence at 14:23:45

# Step 4: What happened at that moment?
context = sample_logs(
    strategy="around_anomaly",
    anomaly_timestamp="2026-01-19T14:23:45Z",
    window_seconds=30,
    sample_size=100
)
# → Shows payment-gateway restarting at 14:23:40
```

## Configuration

### Default Sample Sizes

| Use Case | Recommended Size | Rationale |
|----------|------------------|-----------|
| Quick triage | 20-30 | Fast overview |
| Standard investigation | 50 | Good balance |
| Deep analysis | 100-200 | More context |
| Pattern search | 50 | With context lines |

### Time Range Guidelines

| Situation | Recommended Range |
|-----------|-------------------|
| Immediate alert | 15m |
| Recent incident | 1h |
| Slow degradation | 6h-24h |
| Trend analysis | 7d (with heavy sampling) |

## Implementation Details

### Backend Abstraction

Each backend implements the `LogBackend` interface:

```python
class LogBackend(ABC):
    @abstractmethod
    def get_statistics(self, service, start_time, end_time, **kwargs) -> dict:
        """Get aggregated statistics without raw logs."""
        pass

    @abstractmethod
    def sample_logs(self, strategy, service, start_time, end_time, sample_size, **kwargs) -> dict:
        """Sample logs using specified strategy."""
        pass

    @abstractmethod
    def search_by_pattern(self, pattern, service, start_time, end_time, max_results, **kwargs) -> dict:
        """Search logs by pattern."""
        pass

    @abstractmethod
    def get_logs_around_time(self, timestamp, window_before, window_after, service, **kwargs) -> dict:
        """Get logs around a specific timestamp."""
        pass
```

### Auto-Detection

The `log_source="auto"` parameter automatically detects which backend to use based on configured integrations:

```python
def _get_backend(log_source: str = "auto") -> LogBackend:
    if log_source == "auto":
        # Check which integrations are configured
        if has_config("elasticsearch"):
            return ElasticsearchBackend()
        elif has_config("coralogix"):
            return CoralogixLogBackend()
        elif has_config("datadog"):
            return DatadogLogBackend()
        # ...
```

## Pattern Analysis

Sampled logs automatically include pattern analysis:

```json
{
  "logs": [...],
  "pattern_summary": [
    {"pattern": "Connection refused to payment-ga...", "count_in_sample": 15},
    {"pattern": "Timeout waiting for response fro...", "count_in_sample": 8},
    {"pattern": "Successfully processed payment f...", "count_in_sample": 5}
  ]
}
```

This helps agents quickly identify the most common log patterns without reading every entry.

## Best Practices

### For Agent Developers

1. **Always start with statistics** - Never jump straight to raw logs
2. **Use appropriate sample sizes** - More isn't always better
3. **Match strategy to investigation phase** - Use `errors_only` for triage, `around_anomaly` for deep dives
4. **Leverage pattern analysis** - Let the tool identify common patterns

### For Configuration

1. **Set reasonable defaults** - 50 logs is usually enough
2. **Enable multiple backends** - Allow fallback options
3. **Configure service mappings** - Help the tool filter effectively

## Performance Characteristics

| Operation | Typical Latency | Data Transfer |
|-----------|-----------------|---------------|
| `get_log_statistics` | 100-500ms | ~1KB |
| `sample_logs` (50 logs) | 200-800ms | ~10KB |
| `search_by_pattern` | 300-1000ms | ~15KB |

Compare to fetching all logs:
- 1 million logs: 30-60 seconds, 100MB+

## Related Documentation

- [Tools Catalog](TOOLS_CATALOG.md) - Complete list of all tools
- [Integrations](INTEGRATIONS.md) - Backend configuration
- [RAPTOR Knowledge Base](../../knowledge_base/README.md) - For historical log patterns
