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
def test_use_worker_dependencies(mock_logger, mock_worker, mock_cx_dir,
                                 mock_cx_deps):
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

    assert any(
        "Finished prioritize_customer_dependencies" in str(call[0][0])
        for call in mock_logger.info.call_args_list
    )


@patch.dict(os.environ, {"AZURE_WEBJOBS_SCRIPT_ROOT": "/home/site/wwwroot"})
@patch("proxy_worker.utils.dependency.logger")
def test_get_cx_deps_path_with_matching_prefix(mock_logger):
    """Test _get_cx_deps_path returns customer path when prefix matches."""
    with patch("proxy_worker.utils.dependency.sys.path", [
        "/home/site/wwwroot/.python_packages/lib/site-packages",
        "/usr/local/lib/python3.11/site-packages",
        "/home/site/wwwroot"
    ]):
        result = DependencyManager._get_cx_deps_path()

        assert result == "/home/site/wwwroot/.python_packages/lib/site-packages"
        mock_logger.info.assert_any_call(
            "Customer dependencies path candidates: %s. Default: %s",
            ["/home/site/wwwroot/.python_packages/lib/site-packages"],
            "/home/site/wwwroot/.python_packages/lib/site-packages"
        )


@patch.dict(os.environ, {"AZURE_WEBJOBS_SCRIPT_ROOT": "/home/site/wwwroot"})
@patch("proxy_worker.utils.dependency.logger")
def test_get_cx_deps_path_no_matching_prefix_returns_default(mock_logger):
    """Test _get_cx_deps_path returns first site-packages when no prefix match."""
    with patch("proxy_worker.utils.dependency.sys.path", [
        "/usr/local/lib/python3.11/site-packages",
        "/some/other/path",
        "/home/site/wwwroot"
    ]):
        result = DependencyManager._get_cx_deps_path()

        assert result == "/usr/local/lib/python3.11/site-packages"
        mock_logger.info.assert_any_call(
            "Customer dependencies path candidates: %s. Default: %s",
            [],
            "/usr/local/lib/python3.11/site-packages"
        )
        mock_logger.info.assert_any_call(
            "No customer dependencies path found, using default: %s",
            "/usr/local/lib/python3.11/site-packages"
        )


@patch.dict(os.environ, {}, clear=True)
@patch("proxy_worker.utils.dependency.logger")
def test_get_cx_deps_path_no_prefix_env_returns_default(mock_logger):
    """Test _get_cx_deps_path returns first site-packages when no env var set."""
    with patch("proxy_worker.utils.dependency.sys.path", [
        "/usr/local/lib/python3.11/site-packages",
        "/some/other/path"
    ]):
        result = DependencyManager._get_cx_deps_path()

        assert result == "/usr/local/lib/python3.11/site-packages"
        mock_logger.info.assert_any_call(
            "Customer dependencies path candidates: %s. Default: %s",
            [],
            "/usr/local/lib/python3.11/site-packages"
        )
        mock_logger.info.assert_any_call(
            "No customer dependencies path found, using default: %s",
            "/usr/local/lib/python3.11/site-packages"
        )


@patch.dict(os.environ, {"AZURE_WEBJOBS_SCRIPT_ROOT": "/home/site/wwwroot"})
@patch("proxy_worker.utils.dependency.logger")
def test_get_cx_deps_path_no_site_packages_returns_empty(mock_logger):
    """Test _get_cx_deps_path returns empty string when no site-packages found."""
    with patch("proxy_worker.utils.dependency.sys.path", [
        "/home/site/wwwroot",
        "/some/other/path"
    ]):
        result = DependencyManager._get_cx_deps_path()

        assert result == ""
        mock_logger.info.assert_any_call(
            "Customer dependencies path candidates: %s. Default: %s",
            [],
            ""
        )
        mock_logger.info.assert_any_call(
            "No customer dependencies path found, using default: %s",
            ""
        )


@patch.dict(os.environ, {"AZURE_WEBJOBS_SCRIPT_ROOT": "/home/site/wwwroot"})
@patch("proxy_worker.utils.dependency.logger")
def test_get_cx_deps_path_multiple_matches_returns_first(mock_logger):
    """Test _get_cx_deps_path returns first match when multiple cx paths exist."""
    with patch("proxy_worker.utils.dependency.sys.path", [
        "/home/site/wwwroot/.python_packages/lib/site-packages",
        "/home/site/wwwroot/venv/lib/site-packages",
        "/usr/local/lib/python3.11/site-packages"
    ]):
        result = DependencyManager._get_cx_deps_path()

        assert result == "/home/site/wwwroot/.python_packages/lib/site-packages"
        # Verify that both paths matching the prefix were found
        call_args = mock_logger.info.call_args_list[0]
        assert len(call_args[0][1]) == 2  # Two paths should match
