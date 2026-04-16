# ProcessPoolExecutor Prototype - Demo Function App

This directory contains a simple demo function app to showcase the ProcessPoolExecutor feature.

## What's Included

- `function_app.py` - Demo Azure Function with CPU-bound workload
- `README.md` - This file

## How to Test

### 1. Using ThreadPoolExecutor (Default)

No configuration needed. The function will use `ThreadPoolExecutor`:

```bash
# No environment variables set
func start
```

**Expected behavior:**
- Uses ThreadPoolExecutor
- Single-threaded execution (GIL limited)
- ~50% CPU utilization on 2-core instance

### 2. Using ProcessPoolExecutor

Set the `PYTHON_PROCESS_COUNT` environment variable:

```bash
# For 2-core instance
export PYTHON_PROCESS_COUNT=2  # Linux/Mac
# or
$env:PYTHON_PROCESS_COUNT="2"  # PowerShell

func start
```

**Expected behavior:**
- Uses ProcessPoolExecutor with 2 worker processes
- True parallel execution
- ~100% CPU utilization on 2-core instance
- Better throughput for CPU-bound workloads

### 3. Configuration Examples

```bash
# Thread Pool (Default - I/O-bound workloads)
# No configuration needed

# Process Pool - 2 workers (CPU-bound, 2-core instance)
PYTHON_PROCESS_COUNT=2

# Process Pool - 4 workers (CPU-bound, 4-core instance)
PYTHON_PROCESS_COUNT=4

# Process Pool - 1 worker (Process isolation)
PYTHON_PROCESS_COUNT=1
```

## Demo Function

The demo function (`cpu_bound_work`) performs CPU-intensive calculations:
- Computes prime numbers
- Demonstrates CPU-bound workload
- Shows performance difference between ThreadPoolExecutor and ProcessPoolExecutor

### Test the Function

```bash
# Send request
curl http://localhost:7071/api/cpu_bound_work?iterations=1000000
```

**Compare Performance:**

1. Run with ThreadPoolExecutor (default)
   - Send multiple concurrent requests
   - Observe ~50% CPU usage (GIL limitation)

2. Run with ProcessPoolExecutor (`PYTHON_PROCESS_COUNT=2`)
   - Send multiple concurrent requests
   - Observe ~100% CPU usage (true parallelism)

## Validation

Check the logs to see which executor is being used:

```
# ThreadPoolExecutor
[INFO] Started ThreadPoolExecutor (id=...) with max_workers=...

# ProcessPoolExecutor
[INFO] Started ProcessPoolExecutor (id=...) with 2 worker processes
```

## Notes

- **Serialization:** Functions executed in ProcessPoolExecutor must have picklable inputs/outputs
- **Memory:** Each process consumes additional memory (~30-50MB per process)
- **Cold Start:** ProcessPoolExecutor has slightly slower startup than ThreadPoolExecutor
- **Use Cases:**
  - ✅ CPU-bound: Image processing, ML inference, data transformations
  - ❌ I/O-bound: API calls, database queries (use ThreadPoolExecutor)
