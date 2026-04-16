"""
Simple test script to validate ProcessPoolExecutor implementation.
This tests the basic functionality of the new PYTHON_PROCESS_COUNT setting.
"""
import os
import sys
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

# Add the runtimes/v2 directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'runtimes', 'v2'))

from azure_functions_runtime.utils import threadpool


def test_default_thread_pool():
    """Test that ThreadPoolExecutor is used by default"""
    print("\n=== Test 1: Default ThreadPoolExecutor ===")
    
    # Ensure no PYTHON_PROCESS_COUNT is set
    if 'PYTHON_PROCESS_COUNT' in os.environ:
        del os.environ['PYTHON_PROCESS_COUNT']
    
    threadpool.start_threadpool_executor()
    executor = threadpool.get_threadpool_executor()
    
    assert executor is not None, "Executor should not be None"
    assert isinstance(executor, ThreadPoolExecutor), \
        f"Expected ThreadPoolExecutor, got {type(executor)}"
    assert not isinstance(executor, ProcessPoolExecutor), \
        "Should not be a ProcessPoolExecutor"
    
    print(f"✓ Got ThreadPoolExecutor (id={id(executor)})")
    
    threadpool.stop_threadpool_executor()
    assert threadpool.get_threadpool_executor() is None, \
        "Executor should be None after stopping"
    
    print("✓ Successfully stopped executor")


def test_process_pool_with_count():
    """Test that ProcessPoolExecutor is used when PYTHON_PROCESS_COUNT is set"""
    print("\n=== Test 2: ProcessPoolExecutor with PYTHON_PROCESS_COUNT=2 ===")
    
    # Set PYTHON_PROCESS_COUNT
    os.environ['PYTHON_PROCESS_COUNT'] = '2'
    
    threadpool.start_threadpool_executor()
    executor = threadpool.get_threadpool_executor()
    
    assert executor is not None, "Executor should not be None"
    assert isinstance(executor, ProcessPoolExecutor), \
        f"Expected ProcessPoolExecutor, got {type(executor)}"
    
    print(f"✓ Got ProcessPoolExecutor (id={id(executor)})")
    
    threadpool.stop_threadpool_executor()
    assert threadpool.get_threadpool_executor() is None, \
        "Executor should be None after stopping"
    
    print("✓ Successfully stopped executor")
    
    # Clean up
    del os.environ['PYTHON_PROCESS_COUNT']


def test_invalid_process_count():
    """Test that invalid PYTHON_PROCESS_COUNT falls back to ThreadPoolExecutor"""
    print("\n=== Test 3: Invalid PYTHON_PROCESS_COUNT (falls back to ThreadPoolExecutor) ===")
    
    # Set invalid PYTHON_PROCESS_COUNT
    os.environ['PYTHON_PROCESS_COUNT'] = 'invalid'
    
    threadpool.start_threadpool_executor()
    executor = threadpool.get_threadpool_executor()
    
    assert executor is not None, "Executor should not be None"
    assert isinstance(executor, ThreadPoolExecutor), \
        f"Expected ThreadPoolExecutor (fallback), got {type(executor)}"
    
    print(f"✓ Fell back to ThreadPoolExecutor (id={id(executor)})")
    
    threadpool.stop_threadpool_executor()
    
    # Clean up
    del os.environ['PYTHON_PROCESS_COUNT']


def test_out_of_range_process_count():
    """Test that out-of-range PYTHON_PROCESS_COUNT falls back to ThreadPoolExecutor"""
    print("\n=== Test 4: Out of range PYTHON_PROCESS_COUNT=99 (falls back) ===")
    
    # Set out-of-range PYTHON_PROCESS_COUNT
    os.environ['PYTHON_PROCESS_COUNT'] = '99'  # Max is 32
    
    threadpool.start_threadpool_executor()
    executor = threadpool.get_threadpool_executor()
    
    assert executor is not None, "Executor should not be None"
    assert isinstance(executor, ThreadPoolExecutor), \
        f"Expected ThreadPoolExecutor (fallback), got {type(executor)}"
    
    print(f"✓ Fell back to ThreadPoolExecutor (id={id(executor)})")
    
    threadpool.stop_threadpool_executor()
    
    # Clean up
    del os.environ['PYTHON_PROCESS_COUNT']


def test_process_pool_single_worker():
    """Test ProcessPoolExecutor with single worker (process isolation use case)"""
    print("\n=== Test 5: ProcessPoolExecutor with PYTHON_PROCESS_COUNT=1 ===")
    
    # Set PYTHON_PROCESS_COUNT to 1
    os.environ['PYTHON_PROCESS_COUNT'] = '1'
    
    threadpool.start_threadpool_executor()
    executor = threadpool.get_threadpool_executor()
    
    assert executor is not None, "Executor should not be None"
    assert isinstance(executor, ProcessPoolExecutor), \
        f"Expected ProcessPoolExecutor, got {type(executor)}"
    
    print(f"✓ Got ProcessPoolExecutor with 1 worker (id={id(executor)})")
    
    threadpool.stop_threadpool_executor()
    
    # Clean up
    del os.environ['PYTHON_PROCESS_COUNT']


def _simple_task(x):
    """Module-level function for ProcessPoolExecutor testing (must be picklable)"""
    return x * 2


def test_process_pool_execution():
    """Test that ProcessPoolExecutor can actually execute tasks"""
    print("\n=== Test 6: ProcessPoolExecutor execution test ===")
    
    # Set PYTHON_PROCESS_COUNT
    os.environ['PYTHON_PROCESS_COUNT'] = '2'
    
    threadpool.start_threadpool_executor()
    executor = threadpool.get_threadpool_executor()
    
    assert executor is not None, "Executor should not be None"
    assert isinstance(executor, ProcessPoolExecutor), \
        f"Expected ProcessPoolExecutor, got {type(executor)}"
    
    # Submit a simple task (using module-level function for picklability)
    future = executor.submit(_simple_task, 5)
    result = future.result(timeout=5)
    
    assert result == 10, f"Expected 10, got {result}"
    print(f"✓ Successfully executed task in ProcessPoolExecutor: 5 * 2 = {result}")
    
    threadpool.stop_threadpool_executor()
    
    # Clean up
    del os.environ['PYTHON_PROCESS_COUNT']


def main():
    """Run all tests"""
    print("=" * 60)
    print("ProcessPoolExecutor Prototype Tests")
    print("=" * 60)
    
    tests = [
        test_default_thread_pool,
        test_process_pool_with_count,
        test_invalid_process_count,
        test_out_of_range_process_count,
        test_process_pool_single_worker,
        test_process_pool_execution,
    ]
    
    failed = 0
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"✗ FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {len(tests) - failed}/{len(tests)} tests passed")
    print("=" * 60)
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
