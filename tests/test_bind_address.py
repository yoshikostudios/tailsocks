#!/usr/bin/env python3
"""
Unit tests for the bind address and port functionality in TailscaleProxyManager.
"""

import tempfile
import unittest
from unittest.mock import MagicMock, patch

from tailsocks.manager import TailscaleProxyManager


class TestBindAddress(unittest.TestCase):
    """Tests for the bind address and port functionality."""

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

    def tearDown(self):
        """Clean up after tests."""
        self.expanduser_patcher.stop()
        self.socket_patcher.stop()
        self.temp_dir.cleanup()

    def test_parse_bind_address_with_address_and_port(self):
        """Test parsing a bind string with both address and port."""
        manager = TailscaleProxyManager(self.profile_name)
        address, port = manager._parse_bind_address("192.168.1.1:8080")

        self.assertEqual(address, "192.168.1.1")
        self.assertEqual(port, 8080)

    def test_parse_bind_address_with_port_only(self):
        """Test parsing a bind string with only port."""
        manager = TailscaleProxyManager(self.profile_name)
        address, port = manager._parse_bind_address("8080")

        self.assertEqual(address, "localhost")
        self.assertEqual(port, 8080)

    def test_parse_bind_address_with_invalid_port(self):
        """Test parsing a bind string with invalid port."""
        manager = TailscaleProxyManager(self.profile_name)
        address, port = manager._parse_bind_address("invalid")

        self.assertEqual(address, "localhost")
        self.assertEqual(port, 1080)  # Default port

    def test_parse_bind_address_with_invalid_port_in_address(self):
        """Test parsing a bind string with invalid port in address:port format."""
        manager = TailscaleProxyManager(self.profile_name)
        address, port = manager._parse_bind_address("192.168.1.1:invalid")

        self.assertEqual(address, "192.168.1.1")
        self.assertEqual(port, 1080)  # Default port

    @patch("subprocess.Popen")
    @patch("builtins.print")
    def test_start_server_command_uses_correct_bind_address(
        self, mock_print, mock_popen
    ):
        """Test that start_server uses the correct bind address in the command."""
        # Configure mock
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Process is running
        mock_popen.return_value = mock_process

        # Create manager with custom bind address
        with patch(
            "tailsocks.manager.TailscaleProxyManager._load_config"
        ) as mock_load_config:
            mock_load_config.return_value = {"bind": "192.168.1.1:8080"}
            manager = TailscaleProxyManager(self.profile_name)

        # Patch _is_server_running to return False
        with patch.object(manager, "_is_server_running", return_value=False):
            # Call the method
            manager.start_server()

        # Verify the command contains the correct bind address
        cmd = mock_popen.call_args[0][0]
        self.assertIn("--socks5-server", cmd)
        self.assertIn("192.168.1.1:8080", cmd)

        # Verify that the config was updated and saved
        self.assertEqual(manager.config["bind"], "192.168.1.1:8080")

    @patch("subprocess.Popen")
    @patch("builtins.print")
    def test_start_server_output_message(self, mock_print, mock_popen):
        """Test that start_server prints the correct bind address and port."""
        # Configure mock
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Process is running
        mock_popen.return_value = mock_process

        # Create manager with custom bind address
        with patch(
            "tailsocks.manager.TailscaleProxyManager._load_config"
        ) as mock_load_config:
            mock_load_config.return_value = {"bind": "192.168.1.1:8080"}
            manager = TailscaleProxyManager(self.profile_name)

        # Patch _is_server_running to return False
        with patch.object(manager, "_is_server_running", return_value=False):
            # Call the method
            manager.start_server()

        # Check that the print function was called with the correct message
        found_message = False
        for call in mock_print.call_args_list:
            if (
                call[0]
                and "SOCKS5 proxy will be available at 192.168.1.1:8080" in call[0][0]
            ):
                found_message = True
                break

        self.assertTrue(
            found_message,
            "Did not find the expected output message with correct bind address and port",
        )

    @patch("tailsocks.manager.TailscaleProxyManager._save_config")
    @patch("tailsocks.cli.TailscaleProxyManager")
    def test_cli_start_server_updates_config(
        self, mock_manager_class, mock_save_config
    ):
        """Test that the CLI start-server command updates the config with the bind address."""
        # Setup mock manager
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager
        mock_manager._parse_bind_address.return_value = ("192.168.1.1", 8080)

        # Setup mock args
        args = MagicMock()
        args.command = "start-server"
        args.profile = "test_profile"
        args.bind = "192.168.1.1:8080"

        # Import and call the main function with mocked args
        from tailsocks.cli import main

        with patch("argparse.ArgumentParser.parse_args", return_value=args):
            main()

        # Verify that the bind address was updated in the manager
        mock_manager._parse_bind_address.assert_called_once_with("192.168.1.1:8080")
        mock_manager.config.__setitem__.assert_called_with("bind", "192.168.1.1:8080")
        mock_manager._save_config.assert_called_once()


if __name__ == "__main__":
    unittest.main()
