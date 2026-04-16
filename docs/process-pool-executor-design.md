# Process Pool Executor Design - Solving "The Two Core Problem"

**Date:** April 16, 2026  
**Status:** Design Proposal  
**Target:** Azure Functions Flex Consumption Plan

---

## 1. Problem Overview

### The Two Core Problem

Azure Functions Flex Consumption plan supports instances with multiple cores (e.g., 2 cores for 4GB instances, 4 cores for 8GB instances). However, the current Python worker architecture cannot effectively utilize these additional cores for CPU-bound workloads due to Python's Global Interpreter Lock (GIL).

### Current Architecture

- The Python worker uses `ThreadPoolExecutor` for concurrent function execution
- Threads share the same Python interpreter and are subject to the GIL
- **Result:** Only one thread can execute Python bytecode at a time
- **Impact:** Second core remains idle for CPU-bound workloads

### Real-World Impact

**Customer Scenario:**
- 4GB Flex instance (2 cores)
- Durable Functions workflow: HTTP → Orchestrator → Activity
- CPU-bound activities (data processing, computations)
- Multiple concurrent HTTP requests

**Current Behavior:**
- All functions execute in threads within a single process
- CPU-bound work serialized by GIL
- Second core sits idle (~50% total CPU utilization)
- Cannot handle concurrent CPU-bound requests efficiently

**Desired Behavior:**
- Two function executions run in parallel on separate cores
- Full CPU utilization across all cores
- Better throughput for CPU-bound workloads

### Why Previous Solutions Were Removed

**`FUNCTIONS_WORKER_PROCESS_COUNT` (Premium/Dedicated Plans):**
- App setting that spawned multiple worker processes at the host level
- **Problems:**
  - Increased complexity in host-worker communication
  - Resource management challenges
  - Unpredictable behavior in scaling scenarios
  - Configuration complexity for customers
  - **Removed for Flex Consumption due to these issues**

### Why User-Level Solutions Don't Work

**Customers cannot use `multiprocessing`/`ProcessPoolExecutor` in their code because:**
1. They don't control when functions are invoked (external triggers: HTTP, queue, timer)
2. The host dispatches invocations to the worker's thread pool
3. User code runs after the thread is already assigned
4. Process-level parallelism must be at the worker level, not user code level

---

## 2. Proposed Solutions

### Solution 1: Configurable ProcessPoolExecutor (Recommended)

Replace or augment `ThreadPoolExecutor` with `ProcessPoolExecutor` based on an app setting.

**Implementation:**
```
PYTHON_PROCESS_COUNT=2  # Use ProcessPoolExecutor with 2 worker processes
```

**How It Works:**
- When `PYTHON_PROCESS_COUNT` is set, worker creates `ProcessPoolExecutor` instead of `ThreadPoolExecutor`
- The value specifies the number of worker processes
- Each function invocation is dispatched to a separate process
- Each process has its own Python interpreter and GIL
- CPU-bound functions can truly run in parallel
- If not set or set to 0, falls back to default `ThreadPoolExecutor`

### Solution 2: Hybrid Executor

Maintain both executors and allow per-function configuration.

**Implementation:**
- Worker maintains both `ThreadPoolExecutor` and `ProcessPoolExecutor`
- Functions could declare preference via decorator or configuration
- Default to threads for backward compatibility

### Solution 3: Python Sub-Interpreters (PEP 554)

Use Python 3.12+ sub-interpreters with per-interpreter GIL.

**Implementation:**
- Each sub-interpreter gets its own GIL (Python 3.12+)
- Lower overhead than full processes
- Better resource sharing

---

## 3. Pros and Cons Analysis

### Solution 1: Configurable ProcessPoolExecutor

#### Pros
✅ **Solves the core problem** - True parallelism for CPU-bound workloads  
✅ **Simple configuration** - Single app setting to enable  
✅ **Backward compatible** - Default behavior unchanged (ThreadPoolExecutor)  
✅ **Customer control** - Opt-in based on workload characteristics  
✅ **Process isolation** - Crashes in one function don't affect others  
✅ **No host changes required** - Implementation entirely in worker  
✅ **Proven technology** - `ProcessPoolExecutor` is mature and stable  

#### Cons
❌ **Serialization overhead** - All inputs/outputs must be picklable  
❌ **Memory overhead** - Each process duplicates modules and worker state  
❌ **Slower cold start** - Process creation slower than thread creation  
❌ **State isolation** - Cannot share global state, connections, caches between processes  
❌ **Context propagation** - Logging, tracing, context may need extra work  
❌ **Resource usage** - Higher memory consumption per process  

#### Mitigation Strategies
- Pre-spawn processes during worker initialization (reduce cold start)
- Document serialization requirements clearly
- Implement proper context propagation for logging/tracing
- Monitor memory usage and adjust worker count accordingly
- Provide migration guide for customers moving from threads to processes

### Solution 2: Hybrid Executor

#### Pros
✅ **Maximum flexibility** - Different functions can use different executors  
✅ **Gradual migration** - Can migrate function-by-function  
✅ **Optimal performance** - I/O-bound uses threads, CPU-bound uses processes  

#### Cons
❌ **Increased complexity** - Managing two executor pools  
❌ **Configuration burden** - Customers must understand and configure per-function  
❌ **Resource allocation** - Harder to balance thread vs process workers  
❌ **Testing complexity** - More code paths to test and validate  

### Solution 3: Python Sub-Interpreters

#### Pros
✅ **Lower memory overhead** - Lighter than full processes  
✅ **Faster startup** - Quicker than process creation  
✅ **Modern approach** - Designed for this use case  

#### Cons
❌ **Immature technology** - Only stable in Python 3.13+  
❌ **Limited adoption** - Ecosystem not ready  
❌ **Minimum version** - Requires Python 3.12+ (would break existing apps)  
❌ **Still requires serialization** - Similar constraints to processes  
❌ **Unknown issues** - Not battle-tested in production at scale  
❌ **Delayed timeline** - Cannot implement until Python 3.12+ is minimum version  

---

## 4. Design Overview (Solution 1: Configurable ProcessPoolExecutor)

### 4.1 Architecture Changes

#### Current Architecture
```
Azure Functions Host
    ↓ (gRPC)
Python Worker (Single Process)
    ↓
ThreadPoolExecutor
    ↓ (Thread 1, Thread 2, ..., Thread N)
User Functions (subject to GIL)
```

#### Proposed Architecture
```
Azure Functions Host
    ↓ (gRPC)
Python Worker (Main Process)
    ↓
ProcessPoolExecutor [if PYTHON_USE_PROCESS_POOL=true]
    ↓ (Process 1, Process 2, ..., Process N)
User Functions (separate GILs - true parallelism)

OR

ThreadPoolExecutor [default]
    ↓ (Thread 1, Thread 2, ..., Thread N)
User Functions (shared GIL - I/O-bound optimized)
```

### 4.2 Configuration

#### New App Setting: `PYTHON_PROCESS_COUNT`
- **Name:** `PYTHON_PROCESS_COUNT`
- **Type:** Integer (positive number)
- **Default:** Not set (uses ThreadPoolExecutor)
- **Purpose:** Enable process-based execution with specified number of worker processes
- **Behavior:**
  - **Not set or 0:** Uses default `ThreadPoolExecutor` (backward compatible)
  - **1:** Uses `ProcessPoolExecutor` with 1 worker process (useful for process isolation)
  - **2+:** Uses `ProcessPoolExecutor` with N worker processes (parallel execution)
- **Validation:**
  - Minimum: 1 (if enabling process pool)
  - Maximum: Recommended to match or not exceed core count (e.g., 32)
  - Invalid values log warning and fall back to ThreadPoolExecutor

#### Existing App Setting: `PYTHON_THREADPOOL_THREAD_COUNT`
- **Name:** `PYTHON_THREADPOOL_THREAD_COUNT`
- **Purpose:** Controls thread count when using ThreadPoolExecutor (default mode)
- **Behavior:** Only applies when `PYTHON_PROCESS_COUNT` is not set
- **Note:** These settings are mutually exclusive - use one or the other, not both

#### Configuration Examples

**I/O-Bound Workload (Default - ThreadPoolExecutor):**
```bash
# No configuration needed - uses ThreadPoolExecutor
# Or explicitly configure thread count:
PYTHON_THREADPOOL_THREAD_COUNT=10  # 10 threads
```

**CPU-Bound Workload (ProcessPoolExecutor):**
```bash
# For 2-core instance:
PYTHON_PROCESS_COUNT=2  # 2 worker processes

# For 4-core instance:
PYTHON_PROCESS_COUNT=4  # 4 worker processes
```

**Process Isolation (Single Process):**
```bash
PYTHON_PROCESS_COUNT=1  # Single worker process (isolation without parallelism)
```

### 4.3 Implementation Plan

#### Phase 1: Core Implementation

**1. Refactor `threadpool.py` → `executor.py`**
- Rename module to reflect dual-purpose
- Add executor type detection logic
- Implement ProcessPoolExecutor creation
- Maintain backward compatibility

**2. Add Configuration**
```python
# New constants
PYTHON_PROCESS_COUNT = 'PYTHON_PROCESS_COUNT'
PYTHON_PROCESS_COUNT_MIN = 1
PYTHON_PROCESS_COUNT_MAX = 32  # Reasonable upper limit

# Add validation for process count
def _validate_process_count(value: str) -> bool:
    try:
        int_value = int(value)
    except ValueError:
        logger.warning('%s must be an integer', PYTHON_PROCESS_COUNT)
        return False
    
    if int_value < PYTHON_PROCESS_COUNT_MIN or int_value > PYTHON_PROCESS_COUNT_MAX:
        logger.warning(
            '%s must be between %s and %s. Falling back to ThreadPoolExecutor.',
            PYTHON_PROCESS_COUNT,
            PYTHON_PROCESS_COUNT_MIN,
            PYTHON_PROCESS_COUNT_MAX,
        )
        return False
    return True
```

**3. Modify Executor Creation**
```python
def start_executor() -> None:
    """Start thread or process pool executor based on configuration"""
    global _executor
    
    # Check if process pool is requested
    process_count_str = get_app_setting(
        setting=PYTHON_PROCESS_COUNT,
        validator=_validate_process_count,
    )
    
    if process_count_str:
        # Use ProcessPoolExecutor
        process_count = int(process_count_str)
        _executor = ProcessPoolExecutor(
            max_workers=process_count,
            mp_context=multiprocessing.get_context('spawn')  # Windows-compatible
        )
        logger.info(
            'Started ProcessPoolExecutor with %s worker processes',
            process_count
        )
    else:
        # Use ThreadPoolExecutor (default)
        max_workers = _get_max_workers()  # Uses PYTHON_THREADPOOL_THREAD_COUNT
        _executor = ThreadPoolExecutor(max_workers=max_workers)
        logger.info(
            'Started ThreadPoolExecutor with %s threads',
            max_workers if max_workers else 'default count'
        )
```

**4. Context Propagation**
- Ensure logging context flows to child processes
- Propagate tracing/correlation IDs
- Pass environment variables
- Handle Application Insights context

#### Phase 2: Serialization & Data Handling

**1. Validate Picklability**
- Test function inputs/outputs serialization
- Document requirements for customers
- Provide helpful error messages if serialization fails

**2. Handle Common Cases**
```python
# Ensure these are picklable:
# - HTTP request/response objects
# - Queue messages
# - Timer triggers
# - Durable Functions contexts
```

#### Phase 3: Testing & Validation

**1. Unit Tests**
- Test executor creation for both modes
- Test configuration validation
- Test graceful shutdown

**2. Integration Tests**
- CPU-bound function execution
- Concurrent invocations
- Memory usage
- Performance benchmarks

**3. End-to-End Tests**
- HTTP triggers with CPU-bound work
- Durable Functions workflows
- Mixed workloads (I/O + CPU)

#### Phase 4: Documentation & Migration

**1. Customer Documentation**
- When to use ProcessPoolExecutor vs ThreadPoolExecutor
- Performance characteristics
- Serialization requirements
- Migration guide

**2. Monitoring & Diagnostics**
- Add telemetry for executor type
- Track process vs thread usage
- Memory consumption metrics

### 4.4 Technical Considerations

#### Serialization Requirements

**Must Be Picklable:**
- Function inputs (HTTP request bodies, queue messages, etc.)
- Function outputs (response objects)
- Trigger metadata

**Azure Functions Objects:**
- `HttpRequest` - Already serializable (JSON-based)
- `HttpResponse` - Already serializable
- `QueueMessage` - Already serializable
- Context objects - May need special handling

#### Process Context (`mp_context`)

**Windows Considerations:**
- Must use `spawn` context (Windows doesn't support `fork`)
- Child processes start fresh (import modules, initialize worker)
- Slower startup but required for Windows compatibility

```python
mp_context = multiprocessing.get_context('spawn')
executor = ProcessPoolExecutor(max_workers=N, mp_context=mp_context)
```

#### Memory Management

**Per-Process Overhead:**
- Python interpreter: ~10-30 MB
- Imported modules: ~10-50 MB (depends on dependencies)
- Worker state: ~5-10 MB

**Example (2 Processes):**
- Base: 1 main process + 2 worker processes = 3 processes
- Memory: ~90-270 MB total overhead
- **Acceptable** for 4GB instances (2 cores)

#### Graceful Shutdown

**Process Pool Cleanup:**
```python
def stop_executor() -> None:
    global _executor
    if _executor is not None:
        try:
            _executor.shutdown(wait=True, cancel_futures=False)
            logger.info('Stopped executor')
        finally:
            _executor = None
```

### 4.5 Performance Expectations

#### CPU-Bound Workload (2 Core Instance)

**Before (ThreadPoolExecutor):**
- Throughput: X requests/second
- CPU utilization: ~50% (1 core)
- Latency: Y ms

**After (ProcessPoolExecutor):**
- Throughput: ~2X requests/second
- CPU utilization: ~100% (2 cores)
- Latency: Y ms (similar per-request, but higher throughput)

#### I/O-Bound Workload

**Before (ThreadPoolExecutor):**
- Throughput: X requests/second
- CPU utilization: Low
- Memory: Baseline

**After (ProcessPoolExecutor) - Not Recommended:**
- Throughput: Similar or slightly worse (overhead)
- CPU utilization: Similar
- Memory: Higher (multiple processes)
- **Conclusion:** Use ThreadPoolExecutor for I/O-bound

### 4.6 Migration Path

#### For Existing Apps (No Changes Required)

```bash
# Default behavior - no configuration
# Uses ThreadPoolExecutor as before
```

#### For CPU-Bound Apps (Opt-In)

**Step 1: Set Process Count**
```bash
# Match to instance cores
PYTHON_PROCESS_COUNT=2  # For 4GB (2-core) instance
PYTHON_PROCESS_COUNT=4  # For 8GB (4-core) instance
```

**Step 2: Remove Thread Pool Configuration (if present)**
```bash
# Remove or comment out PYTHON_THREADPOOL_THREAD_COUNT
# These settings are mutually exclusive
```

**Step 3: Test & Validate**
- Monitor memory usage
- Validate performance improvements
- Check for serialization issues

**Step 4: Monitor & Tune**
- Adjust worker count based on actual workload
- Monitor Application Insights metrics

---

## 5. Risks & Mitigation

### Risk 1: Serialization Failures

**Risk:** Customer functions use non-picklable objects  
**Probability:** Medium  
**Impact:** High (function execution fails)

**Mitigation:**
- Clear documentation on serialization requirements
- Helpful error messages with troubleshooting steps
- Validate common Azure Functions objects are serializable
- Provide examples and best practices

### Risk 2: Memory Exhaustion

**Risk:** Multiple processes consume too much memory  
**Probability:** Low-Medium  
**Impact:** High (OOM crashes)

**Mitigation:**
- Document memory overhead per process
- Provide sizing guidance (cores vs memory)
- Monitor memory usage in telemetry
- Conservative default worker counts
- Allow customers to tune based on instance size

### Risk 3: Performance Regression

**Risk:** Process overhead makes I/O-bound apps slower  
**Probability:** Low (only if enabled)  
**Impact:** Medium

**Mitigation:**
- Default to ThreadPoolExecutor (no regression for existing apps)
- Document use cases clearly (CPU-bound vs I/O-bound)
- Provide performance benchmarks
- Easy rollback (change app setting)

### Risk 4: Context Loss

**Risk:** Logging/tracing context not propagated to child processes  
**Probability:** Medium  
**Impact:** Medium (observability gaps)

**Mitigation:**
- Implement context propagation early
- Test with Application Insights
- Validate distributed tracing works
- Monitor for gaps in telemetry

### Risk 5: Incompatibility with Existing Features

**Risk:** Process pool breaks existing worker features  
**Probability:** Low  
**Impact:** High

**Mitigation:**
- Comprehensive integration testing
- Test with all trigger types
- Validate Durable Functions compatibility
- Beta testing with early customers

---

## 6. Success Metrics

### Performance Metrics
- **CPU Utilization:** Target >90% on multi-core instances for CPU-bound workloads
- **Throughput:** 2x improvement for CPU-bound workloads on 2-core instances
- **Latency:** No regression in per-request latency

### Adoption Metrics
- **Opt-In Rate:** Track % of apps enabling process pool
- **Satisfaction:** Customer feedback and support tickets
- **Stability:** Error rate, crash rate

### Resource Metrics
- **Memory Usage:** Monitor per-process overhead
- **Cold Start:** Track initialization time impact

---

## 7. Future Enhancements

### 7.1 Automatic Workload Detection

**Concept:** Automatically switch between thread and process pool based on workload

**Approach:**
- Monitor GIL contention during execution
- Track CPU vs I/O time ratios
- Dynamically switch executor type (requires restart)

**Benefits:**
- Zero configuration for customers
- Optimal performance automatically

**Challenges:**
- Complexity in detection logic
- Executor switch requires coordination
- May be unpredictable

**Timeline:** Post-MVP (requires data from initial rollout)

### 7.2 Per-Function Executor Configuration

**Concept:** Different functions use different executors

**Example:**
```python
@app.route('cpu-intensive', executor='process')
def heavy_computation(req):
    # Runs in ProcessPoolExecutor
    pass

@app.route('io-bound', executor='thread')
def fetch_data(req):
    # Runs in ThreadPoolExecutor
    pass
```

**Benefits:**
- Optimal performance per function
- Mixed workload support

**Challenges:**
- API design complexity
- Resource management (balancing two pools)
- Customer configuration burden

**Timeline:** Future consideration (based on customer demand)

### 7.3 Sub-Interpreters (Python 3.13+)

**Concept:** Switch to sub-interpreters when Python 3.13+ is minimum version

**Benefits:**
- Lower memory overhead
- Faster startup
- Better resource sharing

**Timeline:** 2027+ (when Python 3.13+ adoption is sufficient)

---

## 8. Rollout Plan

### Phase 1: Internal Testing (4 weeks)
- Implement core functionality
- Unit and integration tests
- Internal dogfooding
- Performance benchmarks

### Phase 2: Private Preview (6 weeks)
- Select early adopter customers
- Documentation and migration guides
- Collect feedback
- Fix issues

### Phase 3: Public Preview (8 weeks)
- Announce feature
- Broader customer testing
- Monitor telemetry
- Iterate based on feedback

### Phase 4: GA (General Availability)
- Final validation
- Complete documentation
- Support readiness
- Official announcement

---

## 9. Open Questions

1. **Should we recommend specific worker counts per instance size?**
   - E.g., "For 4GB instances, use 2 processes; for 8GB, use 4 processes"

2. **How do we handle mixed workloads (some CPU-bound, some I/O-bound)?**
   - Current proposal: Customer must choose one executor type
   - Future: Hybrid executor approach?

3. **What's the impact on cold start times?**
   - Need to measure process spawn overhead
   - Can we pre-spawn processes during worker initialization?

4. **Should we provide automatic detection of CPU-bound workloads?**
   - Or rely on customer configuration?

5. **How do we handle Durable Functions with process pools?**
   - Orchestrators maintain state - process isolation implications?
   - Need to validate compatibility

---

## 10. References

- [Python ProcessPoolExecutor Documentation](https://docs.python.org/3/library/concurrent.futures.html#processpoolexecutor)
- [PEP 554: Multiple Interpreters in the Stdlib](https://peps.python.org/pep-0554/)
- [Real Python: Concurrency in Python](https://realpython.com/python-concurrency/)
- Azure Functions Flex Consumption Plan Documentation
- Customer feedback and support tickets

---

## Appendix A: Code Changes Summary

### Files to Modify

1. **`runtimes/v2/azure_functions_runtime/utils/threadpool.py`**
   - Rename to `executor.py` (or keep name for compatibility)
   - Add ProcessPoolExecutor support
   - Add configuration for executor type

2. **`runtimes/v2/azure_functions_runtime/utils/constants.py`**
   - Add `PYTHON_PROCESS_COUNT` constant
   - Add `PYTHON_PROCESS_COUNT_MIN` constant
   - Add `PYTHON_PROCESS_COUNT_MAX` constant

3. **`runtimes/v2/azure_functions_runtime/dispatcher.py`** (likely)
   - Update to use new executor API
   - Ensure context propagation

4. **Tests**
   - Add unit tests for executor creation
   - Add integration tests for both modes
   - Add performance benchmarks

### Estimated Code Changes
- New lines: ~200-300
- Modified lines: ~100-150
- Test lines: ~400-500
- Total: ~700-950 lines

---

## Appendix B: Example Configuration Scenarios

### Scenario 1: Data Processing App (CPU-Bound)
```bash
# App: Processes images, performs ML inference
# Instance: 4GB (2 cores)

PYTHON_PROCESS_COUNT=2

# Result: 2 parallel CPU-bound executions, 100% CPU utilization
```

### Scenario 2: API Gateway (I/O-Bound)
```bash
# App: Calls external APIs, database queries
# Instance: 4GB (2 cores)

# No PYTHON_PROCESS_COUNT - uses default ThreadPoolExecutor
# Optionally configure thread count:
PYTHON_THREADPOOL_THREAD_COUNT=10

# Result: 10 concurrent thread-based executions, low CPU, high throughput
```

### Scenario 3: Durable Functions Workflow (CPU-Bound Activities)
```bash
# App: Orchestrator (I/O) + Activities (CPU)
# Instance: 8GB (4 cores)

PYTHON_PROCESS_COUNT=4

# Result: 4 parallel executions
# Note: Need to validate orchestrator state handling
```

### Scenario 4: Process Isolation (Fault Tolerance)
```bash
# App: Unreliable third-party library that might crash
# Instance: Any size

PYTHON_PROCESS_COUNT=1

# Result: Function runs in separate process
# Crashes won't affect the main worker process
```

---

**Document Version:** 1.0  
**Last Updated:** April 16, 2026  
**Next Review:** After prototype implementation
