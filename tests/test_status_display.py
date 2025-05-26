import unittest
from unittest.mock import patch, MagicMock
from tailsocks.cli import show_status
from tailsocks.manager import TailscaleProxyManager

class TestStatusDisplay(unittest.TestCase):
    """Tests for the status display functionality."""

    @patch('tailsocks.cli.TailscaleProxyManager')
    @patch('builtins.print')
    def test_show_status_with_profile_displays_bind_address(self, mock_print, mock_manager_class):
        """Test that show_status correctly displays the bind address from status."""
        # Setup mock manager and status
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager
        
        mock_status = {
            'profile_name': 'test-profile',
            'server_running': True,
            'session_up': True,
            'bind': 'localhost:1080',
            'ip_address': '100.100.100.100',
            'config_dir': '/path/to/config',
            'cache_dir': '/path/to/cache'
        }
        mock_manager.get_status.return_value = mock_status
        
        # Call show_status with a profile
        args = MagicMock()
        args.profile = 'test-profile'
        show_status(args)
        
        # Verify print was called with the correct bind address
        mock_print.assert_any_call("  Bind address: localhost:1080")
        
    @patch('tailsocks.cli.get_all_profiles')
    @patch('builtins.print')
    def test_show_status_all_profiles_displays_bind_address(self, mock_print, mock_get_all_profiles):
        """Test that show_status correctly displays the bind address for all profiles."""
        # Setup mock profiles
        mock_profiles = [
            {
                'profile_name': 'profile1',
                'server_running': True,
                'session_up': True,
                'bind': 'localhost:1080',
                'ip_address': '100.100.100.100',
                'config_dir': '/path/to/config1',
                'cache_dir': '/path/to/cache1'
            },
            {
                'profile_name': 'profile2',
                'server_running': False,
                'session_up': False,
                'bind': 'localhost:1081',
                'ip_address': 'N/A',
                'config_dir': '/path/to/config2',
                'cache_dir': '/path/to/cache2'
            }
        ]
        mock_get_all_profiles.return_value = mock_profiles
        
        # Call show_status without a profile to show all profiles
        args = MagicMock()
        args.profile = None
        show_status(args)
        
        # Verify print was called with the correct bind addresses
        mock_print.assert_any_call("  Bind address: localhost:1080")
        mock_print.assert_any_call("  Bind address: localhost:1081")
