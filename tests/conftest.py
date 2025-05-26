"""Pytest fixtures for tailsocks tests."""

import os
import tempfile
from unittest.mock import MagicMock

import pytest

from tailsocks.manager import TailscaleProxyManager


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield tmpdirname


@pytest.fixture
def mock_manager(mocker):
    """Create a mocked TailscaleProxyManager instance."""
    manager = TailscaleProxyManager("test_profile")

    # Mock directory paths to use temporary directories
    temp_config_dir = tempfile.mkdtemp()
    temp_cache_dir = tempfile.mkdtemp()
    manager.config_dir = temp_config_dir
    manager.cache_dir = temp_cache_dir
    manager.config_path = os.path.join(temp_config_dir, "config.yaml")

    # Mock methods that would interact with the system
    mocker.patch.object(manager, "_is_server_running", return_value=False)
    mocker.patch.object(manager, "_is_port_in_use", return_value=False)
    mocker.patch.object(manager, "_find_tailscaled_pid", return_value=None)

    yield manager

    # Clean up
    try:
        import shutil

        shutil.rmtree(temp_config_dir, ignore_errors=True)
        shutil.rmtree(temp_cache_dir, ignore_errors=True)
    except Exception:
        pass


@pytest.fixture
def mock_running_manager(mock_manager, mocker):
    """Create a mocked TailscaleProxyManager instance that appears to be running."""
    mocker.patch.object(mock_manager, "_is_server_running", return_value=True)
    mocker.patch.object(mock_manager, "_find_tailscaled_pid", return_value=12345)

    # Mock the subprocess calls
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout = (
        '{"BackendState": "Running", "Self": {"TailscaleIPs": ["100.100.100.100"]}}'
    )
    mocker.patch("subprocess.run", return_value=mock_process)

    # Mock the Popen process
    mock_popen = MagicMock()
    mock_popen.poll.return_value = None
    mock_popen.pid = 12345
    mocker.patch("subprocess.Popen", return_value=mock_popen)

    return mock_manager


@pytest.fixture
def mock_cli_args():
    """Create a mock for CLI arguments."""

    class Args:
        profile = "test_profile"
        command = None
        bind = None
        auth_token = None

    return Args()
