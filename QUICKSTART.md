# ProcessPoolExecutor Prototype - Quick Start Guide

A quick reference for using the new ProcessPoolExecutor feature in Azure Functions Python Worker.

---

## TL;DR

**Problem:** Python's GIL limits CPU-bound Azure Functions to use only one core, even on multi-core instances.

**Solution:** Set `PYTHON_PROCESS_COUNT` to use ProcessPoolExecutor for true parallel execution.

```bash
# Default (I/O-bound workloads)
# No configuration needed - uses ThreadPoolExecutor

# CPU-bound workloads on multi-core instances
PYTHON_PROCESS_COUNT=2  # For 2-core instance (4GB)
PYTHON_PROCESS_COUNT=4  # For 4-core instance (8GB)
```

---

## When to Use ProcessPoolExecutor

### ✅ Use ProcessPoolExecutor (Set PYTHON_PROCESS_COUNT)

**CPU-bound workloads:**
- Image/video processing
- Data transformations
- Cryptographic operations
- ML model inference
- Scientific computations
- Compression/decompression

**Indicators:**
- High CPU usage (>80%)
- GIL contention
- Multi-core instance with low CPU utilization
- Synchronous, compute-heavy operations

### ❌ Don't Use ProcessPoolExecutor (Use Default)

**I/O-bound workloads:**
- API calls
- Database queries
- File I/O
- Network operations
- Async/await operations

**Indicators:**
- Low CPU usage (<20%)
- Waiting on external services
- High latency, low throughput
- Async functions

---

## Configuration

### App Setting: `PYTHON_PROCESS_COUNT`

| Value | Behavior | Use Case |
|-------|----------|----------|
| Not set | ThreadPoolExecutor (default) | I/O-bound workloads |
| `1` | ProcessPoolExecutor, 1 worker | Process isolation |
| `2` | ProcessPoolExecutor, 2 workers | CPU-bound, 2-core instance |
| `4` | ProcessPoolExecutor, 4 workers | CPU-bound, 4-core instance |
| `8` | ProcessPoolExecutor, 8 workers | CPU-bound, 8-core instance |

**Recommendations:**
- Match process count to instance cores
- For 4GB instances (2 cores): `PYTHON_PROCESS_COUNT=2`
- For 8GB instances (4 cores): `PYTHON_PROCESS_COUNT=4`

---

## How to Set

### Local Development (local.settings.json)
```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "...",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "PYTHON_PROCESS_COUNT": "2"
  }
}
```

### Azure Portal
1. Go to your Function App
2. Settings → Configuration
3. Application settings → New application setting
4. Name: `PYTHON_PROCESS_COUNT`, Value: `2`
5. Save and restart

### Azure CLI
```bash
az functionapp config appsettings set \
  --name <function-app-name> \
  --resource-group <resource-group> \
  --settings PYTHON_PROCESS_COUNT=2
```

### PowerShell
```powershell
$env:PYTHON_PROCESS_COUNT="2"
func start
```

---

## Verification

### Check Logs
Look for one of these messages when the worker starts:

**ThreadPoolExecutor (default):**
```
[INFO] Started ThreadPoolExecutor (id=...) with max_workers=...
```

**ProcessPoolExecutor:**
```
[INFO] Started ProcessPoolExecutor (id=...) with 2 worker processes
```

### Monitor Performance
- **CPU Utilization:** Should increase from ~50% to ~100% on 2-core instance
- **Throughput:** Should approximately double for CPU-bound workloads
- **Latency:** Per-request latency should remain similar

---

## Example: Before and After

### Before (ThreadPoolExecutor)

```python
# function_app.py
import azure.functions as func

app = func.FunctionApp()

@app.route(route="process_image")
def process_image(req: func.HttpRequest) -> func.HttpResponse:
    # CPU-intensive image processing
    result = heavy_image_processing(req.get_body())
    return func.HttpResponse(result)
```

**Configuration:** None (default)

**Performance:**
- 2-core instance
- CPU: ~50% (one core maxed, one idle)
- Throughput: X requests/sec
- Concurrent requests blocked by GIL

### After (ProcessPoolExecutor)

```python
# function_app.py
# Same code - no changes needed!
import azure.functions as func

app = func.FunctionApp()

@app.route(route="process_image")
def process_image(req: func.HttpRequest) -> func.HttpResponse:
    # CPU-intensive image processing
    result = heavy_image_processing(req.get_body())
    return func.HttpResponse(result)
```

**Configuration:** `PYTHON_PROCESS_COUNT=2`

**Performance:**
- 2-core instance
- CPU: ~100% (both cores utilized)
- Throughput: ~2X requests/sec
- True parallel execution

**Result:** 2x throughput improvement with zero code changes! 🚀

---

## Important Notes

### Serialization

Functions executed in ProcessPoolExecutor must have **picklable** inputs and outputs.

**✅ Picklable (works fine):**
- Strings, numbers, booleans
- Lists, dicts, tuples
- JSON-serializable objects
- Azure Functions built-in types (HttpRequest, HttpResponse, etc.)

**❌ Not Picklable (will fail):**
- Lambda functions
- Local functions
- Database connections
- File handles
- Thread locks

**Solution:** Use module-level functions and simple data types.

### Memory Usage

Each process consumes additional memory:
- Python interpreter: ~10-30 MB
- Imported modules: ~10-50 MB
- Worker state: ~5-10 MB

**Example (2 processes):**
- Base memory: ~50 MB
- Additional per process: ~30-50 MB
- Total overhead: ~60-100 MB

**Acceptable for most instances:** 4GB+ instances can easily handle 2-4 processes.

### Cold Start

ProcessPoolExecutor startup is slightly slower than ThreadPoolExecutor:
- ThreadPoolExecutor: <100ms
- ProcessPoolExecutor: ~200-500ms (process spawn time)

**Impact:** Minor increase in cold start time, negligible in most cases.

---

## Testing Your Configuration

### 1. Create Test Function

```python
import azure.functions as func
import time

app = func.FunctionApp()

@app.route(route="cpu_test")
def cpu_test(req: func.HttpRequest) -> func.HttpResponse:
    # CPU-intensive work
    start = time.time()
    result = sum(i * i for i in range(10000000))
    elapsed = time.time() - start
    
    return func.HttpResponse(
        f"Result: {result}, Time: {elapsed:.3f}s",
        status_code=200
    )
```

### 2. Test with ThreadPoolExecutor

```bash
# No PYTHON_PROCESS_COUNT
func start

# Send 2 concurrent requests
curl http://localhost:7071/api/cpu_test &
curl http://localhost:7071/api/cpu_test &
```

**Observe:** Requests processed serially (GIL contention)

### 3. Test with ProcessPoolExecutor

```bash
# Set PYTHON_PROCESS_COUNT
export PYTHON_PROCESS_COUNT=2  # or $env:PYTHON_PROCESS_COUNT="2" in PowerShell
func start

# Send 2 concurrent requests
curl http://localhost:7071/api/cpu_test &
curl http://localhost:7071/api/cpu_test &
```

**Observe:** Requests processed in parallel (separate processes)

---

## Troubleshooting

### Issue: Function fails with pickle error

**Error:**
```
PicklingError: Can't pickle <object>
```

**Solution:**
- Ensure all inputs/outputs are picklable
- Use module-level functions
- Avoid complex objects (connections, locks, etc.)

### Issue: High memory usage

**Symptom:** Out of memory errors

**Solution:**
- Reduce `PYTHON_PROCESS_COUNT`
- Consider instance size vs process count
- Monitor memory usage

### Issue: No performance improvement

**Possible Causes:**
1. Workload is I/O-bound (use ThreadPoolExecutor)
2. `PYTHON_PROCESS_COUNT` not set correctly
3. Single function execution (not concurrent)

**Solution:**
- Verify workload is CPU-bound
- Check logs for executor type
- Test with concurrent requests

---

## FAQ

**Q: Do I need to change my code?**  
A: No! Just set `PYTHON_PROCESS_COUNT`. The worker handles everything.

**Q: Will this work with Durable Functions?**  
A: Should work, but needs testing. Orchestrators maintain state, so test carefully.

**Q: What about async functions?**  
A: Async functions run on the event loop (not in executor), so ProcessPoolExecutor won't affect them.

**Q: Can I use both ThreadPoolExecutor and ProcessPoolExecutor?**  
A: Not simultaneously in this prototype. You choose one for the entire app.

**Q: What's the optimal PYTHON_PROCESS_COUNT?**  
A: Match your instance cores. For 2-core: 2, for 4-core: 4. Test and adjust based on memory.

**Q: Does this work on Linux?**  
A: Yes! Works on Windows, Linux, and macOS (uses 'spawn' multiprocessing context).

---

## Resources

- **Design Document:** `docs/process-pool-executor-design.md`
- **Implementation Summary:** `IMPLEMENTATION_SUMMARY.md`
- **Demo App:** `demo_process_pool/`
- **Tests:** `test_process_pool_prototype.py`

---

**Quick Start Version:** 1.0  
**Last Updated:** April 16, 2026  
**Status:** Prototype - Ready for Testing
