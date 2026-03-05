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


@patch.dict(os.environ, {"AzureWebJobsScriptRoot": "/home/site/wwwroot"})
def test_get_cx_deps_path_with_matching_prefix():
    """Test _get_cx_deps_path returns customer path when prefix matches."""
    original_sys_path = sys.path.copy()
    try:
        sys.path = [
            "/home/site/wwwroot/.python_packages/lib/site-packages",
            "/usr/local/lib/python3.11/site-packages",
            "/home/site/wwwroot"
        ]
        result = DependencyManager._get_cx_deps_path()

        assert result == "/home/site/wwwroot/.python_packages/lib/site-packages"
    finally:
        sys.path = original_sys_path


@patch.dict(os.environ, {"AzureWebJobsScriptRoot": "/home/site/wwwroot"})
def test_get_cx_deps_path_no_matching_prefix_returns_empty():
    """Test _get_cx_deps_path returns empty string when no prefix match."""
    original_sys_path = sys.path.copy()
    try:
        sys.path = [
            "/usr/local/lib/python3.11/site-packages",
            "/some/other/path",
            "/home/site/wwwroot"
        ]
        result = DependencyManager._get_cx_deps_path()

        # When no cx_paths match, return empty string (not the first site-packages)
        assert result == ""
    finally:
        sys.path = original_sys_path


@patch.dict(os.environ, {}, clear=True)
def test_get_cx_deps_path_no_prefix_env_returns_empty():
    """Test _get_cx_deps_path returns empty string when no env var set."""
    original_sys_path = sys.path.copy()
    try:
        sys.path = [
            "/usr/local/lib/python3.11/site-packages",
            "/some/other/path"
        ]
        result = DependencyManager._get_cx_deps_path()

        # When env var is not set, prefix is None and cx_paths is empty
        assert result == ""
    finally:
        sys.path = original_sys_path


@patch.dict(os.environ, {"AzureWebJobsScriptRoot": "/home/site/wwwroot"})
def test_get_cx_deps_path_no_site_packages_returns_empty():
    """Test _get_cx_deps_path returns empty string when no site-packages found."""
    original_sys_path = sys.path.copy()
    try:
        sys.path = [
            "/home/site/wwwroot",
            "/some/other/path"
        ]
        result = DependencyManager._get_cx_deps_path()

        # When no paths with site-packages match the prefix, return empty string
        assert result == ""
    finally:
        sys.path = original_sys_path


@patch.dict(os.environ, {"AzureWebJobsScriptRoot": "/home/site/wwwroot"})
def test_get_cx_deps_path_multiple_matches_returns_first():
    """Test _get_cx_deps_path returns first match when multiple cx paths exist."""
    original_sys_path = sys.path.copy()
    try:
        sys.path = [
            "/home/site/wwwroot/.python_packages/lib/site-packages",
            "/home/site/wwwroot/venv/lib/site-packages",
            "/usr/local/lib/python3.11/site-packages"
        ]
        result = DependencyManager._get_cx_deps_path()

        # When multiple paths match, return the first one
        expected_path = "/home/site/wwwroot/.python_packages/lib/site-packages"
        assert result == expected_path
    finally:
        sys.path = original_sys_path


@patch(
    "proxy_worker.utils.dependency.DependencyManager."
    "_clear_path_importer_cache_and_modules"
)
def test_add_cx_deps_to_sys_path_adds_to_first(mock_clear):
    """Test _add_cx_deps_to_sys_path adds path to first position."""
    sys.path = ["/original/path", "/another/path"]

    DependencyManager._add_cx_deps_to_sys_path(
        "/new/cx/path", add_to_first=True
    )

    assert sys.path[0] == "/new/cx/path"
    assert "/original/path" in sys.path
    mock_clear.assert_called_once_with("/new/cx/path")


@patch(
    "proxy_worker.utils.dependency.DependencyManager."
    "_clear_path_importer_cache_and_modules"
)
def test_add_cx_deps_to_sys_path_appends_to_end(mock_clear):
    """Test _add_cx_deps_to_sys_path appends path to end."""
    sys.path = ["/original/path", "/another/path"]

    DependencyManager._add_cx_deps_to_sys_path(
        "/new/cx/path", add_to_first=False
    )

    assert sys.path[-1] == "/new/cx/path"
    assert sys.path[0] == "/original/path"
    mock_clear.assert_called_once_with("/new/cx/path")


def test_add_cx_deps_to_sys_path_no_duplicate():
    """Test _add_cx_deps_to_sys_path does not add duplicate paths."""
    sys.path = ["/existing/path", "/another/path"]
    original_length = len(sys.path)

    DependencyManager._add_cx_deps_to_sys_path(
        "/existing/path", add_to_first=True
    )

    # Path should not be added again
    assert len(sys.path) == original_length
    assert sys.path.count("/existing/path") == 1


@patch("proxy_worker.utils.dependency.is_azure_environment",
       return_value=False)
@patch("proxy_worker.utils.dependency.logger")
def test_add_cx_deps_to_sys_path_empty_path_with_default(
    mock_logger, mock_is_azure
):
    """Test _add_cx_deps_to_sys_path uses default when path is empty
    in local environment."""
    sys.path = ["/usr/local/lib/python3.11/site-packages", "/original/path"]

    DependencyManager._add_cx_deps_to_sys_path("", add_to_first=True)

    # Should insert the first site-packages path to position 0
    assert sys.path[0] == "/usr/local/lib/python3.11/site-packages"
    mock_logger.info.assert_called_once_with(
        "No customer dependencies path found, using default: %s",
        "/usr/local/lib/python3.11/site-packages"
    )
    mock_is_azure.assert_called_once()


@patch("proxy_worker.utils.dependency.is_azure_environment",
       return_value=False)
@patch("proxy_worker.utils.dependency.logger")
def test_add_cx_deps_to_sys_path_empty_path_no_site_packages(
    mock_logger, mock_is_azure
):
    """Test _add_cx_deps_to_sys_path handles empty path with no
    site-packages in local environment."""
    sys.path = ["/some/path", "/another/path"]

    DependencyManager._add_cx_deps_to_sys_path("", add_to_first=True)

    # Should insert empty string at position 0 when no site-packages found
    assert sys.path[0] == ""
    mock_logger.info.assert_called_once_with(
        "No customer dependencies path found, using default: %s",
        ""
    )
    mock_is_azure.assert_called_once()


@patch("proxy_worker.utils.dependency.is_azure_environment",
       return_value=True)
@patch("proxy_worker.utils.dependency.logger")
def test_add_cx_deps_to_sys_path_empty_path_in_azure(
    mock_logger, mock_is_azure
):
    """Test _add_cx_deps_to_sys_path takes no action when path is empty
    in Azure environment."""
    sys.path = ["/usr/local/lib/python3.11/site-packages", "/original/path"]
    original_sys_path = sys.path.copy()

    DependencyManager._add_cx_deps_to_sys_path("", add_to_first=True)

    # sys.path should remain unchanged in Azure environment
    assert sys.path == original_sys_path
    mock_logger.info.assert_not_called()
    mock_is_azure.assert_called_once()


@patch("proxy_worker.utils.dependency.is_azure_environment",
       return_value=True)
@patch(
    "proxy_worker.utils.dependency.DependencyManager."
    "_clear_path_importer_cache_and_modules"
)
def test_add_cx_deps_to_sys_path_none_path_no_action(
    mock_clear, mock_is_azure
):
    """Test _add_cx_deps_to_sys_path takes no action for None path
    in Azure environment."""
    sys.path = ["/original/path"]
    original_sys_path = sys.path.copy()

    DependencyManager._add_cx_deps_to_sys_path(None, add_to_first=True)

    # sys.path should remain unchanged
    assert sys.path == original_sys_path
    mock_clear.assert_not_called()
    mock_is_azure.assert_called_once()
