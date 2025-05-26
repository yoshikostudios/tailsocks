"""Pytest fixtures for tailsocks tests."""

import logging
import os
import shutil
import tempfile
from unittest.mock import MagicMock

import pytest

from tailsocks.manager import TailscaleProxyManager, get_all_profiles


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield tmpdirname


@pytest.fixture
def mock_manager(mocker):
    """Create a mocked TailscaleProxyManager instance."""
    # Mock the logger setup
    mock_logger = mocker.MagicMock(spec=logging.Logger)
    mocker.patch("tailsocks.logger.setup_logger", return_value=mock_logger)

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
    mocker.patch.object(manager, "_save_state", return_value=True)
    mocker.patch.object(manager, "_save_config", return_value=True)

    # Set up state and config
    manager.state = {}
    manager.config = {}

    yield manager

    # Clean up
    try:
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


@pytest.fixture(autouse=True)
def cleanup_test_profiles():
    """Clean up any test profiles created during testing.

    This fixture runs automatically at the end of the test session
    to ensure all test profiles are removed, regardless of whether tests pass or fail.
    """
    try:
        # Setup - nothing to do before tests
        yield
    finally:
        # Teardown - clean up all test profiles
        # This block will always execute, even if tests fail
        print("Running test profile cleanup...")
        profiles = get_all_profiles()

        # Specific profiles to clean up
        specific_profiles = ["test_profile1", "test_profile2", "test_profile3"]

        for profile in profiles:
            profile_name = profile.get("profile_name", "")
            # Clean up specific profiles and any test profiles
            if (
                profile_name in specific_profiles
                or profile_name.startswith("test_")
                or "_test_" in profile_name
            ):
                try:
                    # Create a manager for this profile
                    manager = TailscaleProxyManager(profile_name)

                    # Stop any running services
                    if profile.get("server_running", False):
                        try:
                            manager.stop_server()
                        except Exception as e:
                            print(f"Error stopping server for {profile_name}: {str(e)}")

                    # Remove the profile directories
                    if os.path.exists(manager.config_dir):
                        shutil.rmtree(manager.config_dir, ignore_errors=True)
                    if os.path.exists(manager.cache_dir):
                        shutil.rmtree(manager.cache_dir, ignore_errors=True)

                    print(f"Cleaned up test profile: {profile_name}")
                except Exception as e:
                    print(f"Error cleaning up test profile {profile_name}: {str(e)}")
