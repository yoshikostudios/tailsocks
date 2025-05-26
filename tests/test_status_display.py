import unittest
from unittest.mock import MagicMock, patch

from tailsocks.cli import show_status


class TestStatusDisplay(unittest.TestCase):
    """Tests for the status display functionality."""

    @patch("tailsocks.cli.TailscaleProxyManager")
    @patch("argparse.ArgumentParser.parse_args")
    @patch("builtins.print")
    def test_cli_start_server_with_bind_updates_status(
        self, mock_print, mock_parse_args, mock_manager_class
    ):
        """Test that starting a server with a custom bind address shows correctly in status."""
        # Setup mock manager
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager
        mock_manager._parse_bind_address.return_value = ("192.168.1.1", 8080)

        # First call start-server with a custom bind
        start_args = MagicMock()
        start_args.command = "start-server"
        start_args.profile = "test-profile"
        start_args.bind = "192.168.1.1:8080"
        mock_parse_args.return_value = start_args

        # Import and call the main function
        from tailsocks.cli import main

        main()

        # Verify config was updated
        mock_manager.config.__setitem__.assert_called_with("bind", "192.168.1.1:8080")
        mock_manager._save_config.assert_called_once()

        # Now setup for status check
        mock_status = {
            "profile_name": "test-profile",
            "server_running": True,
            "session_up": False,
            "bind": "192.168.1.1:8080",
            "ip_address": "N/A",
            "config_dir": "/path/to/config",
            "cache_dir": "/path/to/cache",
        }
        mock_manager.get_status.return_value = mock_status

        # Call status command
        status_args = MagicMock()
        status_args.command = "status"
        status_args.profile = "test-profile"
        mock_parse_args.return_value = status_args

        main()

        # Verify status shows the correct bind address
        mock_print.assert_any_call("  Bind address: 192.168.1.1:8080")

    @patch("tailsocks.cli.TailscaleProxyManager")
    @patch("builtins.print")
    def test_show_status_with_profile_displays_bind_address(
        self, mock_print, mock_manager_class
    ):
        """Test that show_status correctly displays the bind address from status."""
        # Setup mock manager and status
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager

        # Test with a custom bind address
        mock_status = {
            "profile_name": "test-profile",
            "server_running": True,
            "session_up": True,
            "bind": "192.168.1.1:8080",  # Custom bind address
            "ip_address": "100.100.100.100",
            "config_dir": "/path/to/config",
            "cache_dir": "/path/to/cache",
        }
        mock_manager.get_status.return_value = mock_status

        # Call show_status with a profile
        args = MagicMock()
        args.profile = "test-profile"
        show_status(args)

        # Verify print was called with the correct bind address
        mock_print.assert_any_call("  Bind address: 192.168.1.1:8080")

    @patch("tailsocks.cli.get_all_profiles")
    @patch("builtins.print")
    def test_show_status_all_profiles_displays_bind_address(
        self, mock_print, mock_get_all_profiles
    ):
        """Test that show_status correctly displays the bind address for all profiles."""
        # Setup mock profiles with custom bind addresses
        mock_profiles = [
            {
                "profile_name": "profile1",
                "server_running": True,
                "session_up": True,
                "bind": "192.168.1.1:8080",  # Custom bind address
                "ip_address": "100.100.100.100",
                "config_dir": "/path/to/config1",
                "cache_dir": "/path/to/cache1",
            },
            {
                "profile_name": "profile2",
                "server_running": False,
                "session_up": False,
                "bind": "0.0.0.0:1081",  # Another custom bind address
                "ip_address": "N/A",
                "config_dir": "/path/to/config2",
                "cache_dir": "/path/to/cache2",
            },
        ]
        mock_get_all_profiles.return_value = mock_profiles

        # Call show_status without a profile to show all profiles
        args = MagicMock()
        args.profile = None
        show_status(args)

        # Verify print was called with the correct bind addresses
        mock_print.assert_any_call("  Bind address: 192.168.1.1:8080")
        mock_print.assert_any_call("  Bind address: 0.0.0.0:1081")
