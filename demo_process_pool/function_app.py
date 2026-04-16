"""
Demo Azure Function App - ProcessPoolExecutor Prototype

This demo showcases the difference between ThreadPoolExecutor (default) 
and ProcessPoolExecutor (PYTHON_PROCESS_COUNT) for CPU-bound workloads.
"""
import azure.functions as func
import time
import os

app = func.FunctionApp()


def is_prime(n):
    """Check if a number is prime (CPU-intensive)"""
    if n < 2:
        return False
    if n == 2:
        return True
    if n % 2 == 0:
        return False
    for i in range(3, int(n ** 0.5) + 1, 2):
        if n % i == 0:
            return False
    return True


def compute_primes(start, end):
    """Compute prime numbers in a range (CPU-bound workload)"""
    primes = []
    for num in range(start, end):
        if is_prime(num):
            primes.append(num)
    return primes


@app.route(route="cpu_bound_work", methods=["GET"])
def cpu_bound_work(req: func.HttpRequest) -> func.HttpResponse:
    """
    Demo function with CPU-bound workload.
    
    Query params:
    - iterations: Number of iterations (default: 100000)
    - range_start: Start of prime search range (default: 1)
    - range_end: End of prime search range (default: 10000)
    """
    start_time = time.time()
    
    # Get parameters
    iterations = int(req.params.get('iterations', '100000'))
    range_start = int(req.params.get('range_start', '1'))
    range_end = int(req.params.get('range_end', '10000'))
    
    # Log executor type (from environment)
    process_count = os.environ.get('PYTHON_PROCESS_COUNT', 'Not set')
    executor_type = 'ProcessPoolExecutor' if process_count != 'Not set' else 'ThreadPoolExecutor'
    
    # Perform CPU-intensive work
    results = []
    for i in range(iterations // 10000):
        primes = compute_primes(range_start, range_end)
        results.append(len(primes))
    
    elapsed_time = time.time() - start_time
    
    response = {
        'message': 'CPU-bound work completed',
        'executor_type': executor_type,
        'process_count': process_count,
        'iterations': iterations,
        'prime_range': f'{range_start}-{range_end}',
        'prime_counts': results[:5],  # First 5 results
        'total_iterations': len(results),
        'elapsed_time_seconds': round(elapsed_time, 3),
        'tips': {
            'thread_pool': 'Default behavior - uses ThreadPoolExecutor (limited by GIL for CPU-bound)',
            'process_pool': 'Set PYTHON_PROCESS_COUNT=2 (or N cores) for ProcessPoolExecutor',
        }
    }
    
    return func.HttpResponse(
        body=str(response),
        status_code=200,
        mimetype='application/json'
    )


@app.route(route="health", methods=["GET"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Simple health check endpoint"""
    process_count = os.environ.get('PYTHON_PROCESS_COUNT', 'Not set')
    executor_type = 'ProcessPoolExecutor' if process_count != 'Not set' else 'ThreadPoolExecutor'
    
    return func.HttpResponse(
        body=f"OK - Using {executor_type} (PYTHON_PROCESS_COUNT={process_count})",
        status_code=200
    )


@app.route(route="io_bound_work", methods=["GET"])
def io_bound_work(req: func.HttpRequest) -> func.HttpResponse:
    """
    Demo function with I/O-bound workload (for comparison).
    This should use ThreadPoolExecutor even if PYTHON_PROCESS_COUNT is set.
    """
    import asyncio
    
    async def async_sleep(duration):
        await asyncio.sleep(duration)
        return f"Slept for {duration}s"
    
    start_time = time.time()
    sleep_duration = float(req.params.get('duration', '0.1'))
    
    # Simulate I/O-bound work
    result = asyncio.run(async_sleep(sleep_duration))
    
    elapsed_time = time.time() - start_time
    process_count = os.environ.get('PYTHON_PROCESS_COUNT', 'Not set')
    
    return func.HttpResponse(
        body=f"I/O-bound work: {result}, elapsed: {elapsed_time:.3f}s (PYTHON_PROCESS_COUNT={process_count})",
        status_code=200
    )
