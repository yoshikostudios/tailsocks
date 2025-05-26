#!/usr/bin/env python3
"""
Unit tests for the TailscaleProxyManager class.
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import yaml

from tailsocks.manager import TailscaleProxyManager, get_all_profiles


class TestTailscaleProxyManager(unittest.TestCase):
    """Tests for the TailscaleProxyManager class."""

    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for test config files
        self.temp_dir = tempfile.TemporaryDirectory()

        # Patch os.path.expanduser to use our temp directory
        self.expanduser_patcher = patch("os.path.expanduser")
        self.mock_expanduser = self.expanduser_patcher.start()
        self.mock_expanduser.side_effect = lambda path: path.replace(
            "~", self.temp_dir.name
        )

        # Patch socket.socket.connect_ex to simulate port availability
        self.socket_patcher = patch("socket.socket.connect_ex")
        self.mock_connect_ex = self.socket_patcher.start()
        self.mock_connect_ex.return_value = 1  # Port is available

        # Create test profile
        self.profile_name = "test_profile"
        self.manager = TailscaleProxyManager(self.profile_name)

    def tearDown(self):
        """Clean up after tests."""
        self.expanduser_patcher.stop()
        self.socket_patcher.stop()
        self.temp_dir.cleanup()

    def test_init_creates_directories(self):
        """Test that initialization creates necessary directories."""
        config_dir = os.path.join(
            self.temp_dir.name, f".config/tailscale-{self.profile_name}"
        )
        cache_dir = os.path.join(
            self.temp_dir.name, f".cache/tailscale-{self.profile_name}"
        )

        self.assertTrue(os.path.exists(config_dir))
        self.assertTrue(os.path.exists(cache_dir))

    def test_init_creates_default_config(self):
        """Test that initialization creates a default config file."""
        config_path = os.path.join(
            self.temp_dir.name, f".config/tailscale-{self.profile_name}/config.yaml"
        )
        self.assertTrue(os.path.exists(config_path))

        # Verify config content
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        self.assertIn("tailscaled_path", config)
        self.assertIn("tailscale_path", config)
        self.assertIn("socket_path", config)

    def test_random_profile_name_generation(self):
        """Test that random profile names are generated correctly."""
        # Create a manager without specifying a profile name
        with patch("glob.glob", return_value=[]):  # No existing profiles
            manager = TailscaleProxyManager()

            # Check that a name was generated
            self.assertIsNotNone(manager.profile_name)

            # Check format (adjective_animal)
            parts = manager.profile_name.split("_")
            self.assertGreaterEqual(len(parts), 2)

    @patch("subprocess.Popen")
    def test_start_server(self, mock_popen):
        """Test starting the tailscaled server."""
        # Configure mock
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Process is running
        mock_popen.return_value = mock_process

        # Call the method
        result = self.manager.start_server()

        # Verify the result
        self.assertTrue(result)
        mock_popen.assert_called_once()

        # Verify command contains expected arguments
        cmd = mock_popen.call_args[0][0]
        self.assertIn("--state", cmd)
        self.assertIn("--socket", cmd)
        self.assertIn("--socks5-server", cmd)

    @patch("subprocess.run")
    def test_start_session(self, mock_run):
        """Test starting a tailscale session."""
        # Configure mock
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_run.return_value = mock_process

        # Patch _is_server_running to return True
        with patch.object(self.manager, "_is_server_running", return_value=True):
            # Call the method
            result = self.manager.start_session()

            # Verify the result
            self.assertTrue(result)
            mock_run.assert_called_once()

            # Verify command contains expected arguments
            cmd = mock_run.call_args[0][0]
            self.assertIn("up", cmd)
            self.assertIn("--socket", cmd)

    @patch("subprocess.run")
    def test_get_status(self, mock_run):
        """Test getting status information."""
        # Configure mock for subprocess.run
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = (
            '{"BackendState": "Running", "Self": {"TailscaleIPs": ["100.100.100.100"]}}'
        )
        mock_run.return_value = mock_process

        # Patch _is_server_running to return True
        with patch.object(self.manager, "_is_server_running", return_value=True):
            # Call the method
            status = self.manager.get_status()

            # Verify the result
            self.assertEqual(status["profile_name"], self.profile_name)
            self.assertTrue(status["server_running"])
            self.assertTrue(status["session_up"])
            self.assertEqual(status["ip_address"], "100.100.100.100")


class TestGetAllProfiles(unittest.TestCase):
    """Tests for the get_all_profiles function."""

    @patch("glob.glob")
    @patch("tailsocks.manager.TailscaleProxyManager")
    def test_get_all_profiles(self, mock_manager_class, mock_glob):
        """Test getting all profiles."""
        # Configure mocks
        mock_glob.side_effect = [
            [
                "/home/user/.config/tailscale-profile1",
                "/home/user/.config/tailscale-profile2",
            ],
            [
                "/home/user/.cache/tailscale-profile1",
                "/home/user/.cache/tailscale-profile3",
            ],
        ]

        # Mock manager instances
        mock_manager1 = MagicMock()
        mock_manager1.get_status.return_value = {"profile_name": "profile1"}

        mock_manager2 = MagicMock()
        mock_manager2.get_status.return_value = {"profile_name": "profile2"}

        mock_manager3 = MagicMock()
        mock_manager3.get_status.return_value = {"profile_name": "profile3"}

        mock_manager_class.side_effect = [mock_manager1, mock_manager2, mock_manager3]

        # Call the function
        profiles = get_all_profiles()

        # Verify the result
        self.assertEqual(len(profiles), 3)
        self.assertEqual(profiles[0]["profile_name"], "profile1")
        self.assertEqual(profiles[1]["profile_name"], "profile2")
        self.assertEqual(profiles[2]["profile_name"], "profile3")


if __name__ == "__main__":
    unittest.main()
