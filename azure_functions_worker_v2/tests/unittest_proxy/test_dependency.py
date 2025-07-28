import sys
import os
from unittest.mock import patch

from proxy_worker.utils.dependency import DependencyManager


@patch("proxy_worker.utils.dependency.DependencyManager._get_cx_deps_path",
       return_value="/mock/cx/site-packages")
@patch("proxy_worker.utils.dependency.DependencyManager._get_cx_working_dir",
       return_value="/mock/cx")
@patch("proxy_worker.utils.dependency.DependencyManager._get_worker_deps_path",
       return_value="/mock/worker")
@patch("proxy_worker.utils.dependency.logger")
def test_use_worker_dependencies(mock_logger, mock_worker, mock_cx_dir, mock_cx_deps):
    sys.path = ["/mock/cx/site-packages", "/mock/cx", "/original"]

    DependencyManager.initialize()
    DependencyManager.use_worker_dependencies()

    assert sys.path[0] == "/mock/worker"
    assert "/mock/cx/site-packages" not in sys.path
    assert "/mock/cx" not in sys.path

    mock_logger.info.assert_any_call(
        'Applying use_worker_dependencies:'
        ' worker_dependencies: %s,'
        ' customer_dependencies: %s,'
        ' working_directory: %s',
        "/mock/worker", "/mock/cx/site-packages", "/mock/cx"
    )


@patch("proxy_worker.utils.dependency.DependencyManager._get_cx_deps_path",
       return_value="/mock/cx/site-packages")
@patch("proxy_worker.utils.dependency.DependencyManager._get_worker_deps_path",
       return_value="/mock/worker")
@patch("proxy_worker.utils.dependency.DependencyManager._get_cx_working_dir",
       return_value="/mock/cx")
@patch("proxy_worker.utils.dependency.DependencyManager.is_in_linux_consumption",
       return_value=False)
@patch("proxy_worker.utils.dependency.is_envvar_true", return_value=False)
@patch("proxy_worker.utils.dependency.logger")
def test_prioritize_customer_dependencies(mock_logger, mock_env, mock_linux,
                                          mock_cx_dir, mock_worker, mock_cx_deps):
    sys.path = ["/mock/worker", "/some/old/path"]

    DependencyManager.initialize()
    DependencyManager.prioritize_customer_dependencies("/override/cx")

    assert sys.path[0] == "/mock/cx/site-packages"
    assert sys.path[1] == "/mock/worker"
    expected_path = os.path.abspath("/override/cx")
    assert expected_path in sys.path

    # Relaxed log validation: look for matching prefix
    assert any(
        "Applying prioritize_customer_dependencies" in str(call[0][0])
        for call in mock_logger.info.call_args_list
    )

    assert any(
        "Finished prioritize_customer_dependencies" in str(call[0][0])
        for call in mock_logger.info.call_args_list
    )
