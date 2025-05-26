#!/usr/bin/env python3
"""
Unit tests for the CLI interface.
"""

import unittest
from unittest.mock import patch, MagicMock
import argparse
import sys

from tailsocks.cli import main, show_status


class TestCLI(unittest.TestCase):
    """Tests for the CLI interface."""

    @patch('argparse.ArgumentParser.parse_args')
    @patch('tailsocks.cli.show_status')
    def test_status_command(self, mock_show_status, mock_parse_args):
        """Test the status command."""
        # Configure mock
        args = argparse.Namespace()
        args.command = 'status'
        args.profile = None
        args.version = False
        mock_parse_args.return_value = args
        
        # Call the function
        result = main()
        
        # Verify the result
        self.assertEqual(result, 0)
        mock_show_status.assert_called_once_with(args)

    @patch('argparse.ArgumentParser.parse_args')
    @patch('tailsocks.cli.TailscaleProxyManager')
    def test_start_server_command(self, mock_manager_class, mock_parse_args):
        """Test the start-server command."""
        # Configure mocks
        args = argparse.Namespace()
        args.command = 'start-server'
        args.profile = 'test_profile'
        args.version = False
        mock_parse_args.return_value = args
        
        mock_manager = MagicMock()
        mock_manager.start_server.return_value = True
        mock_manager_class.return_value = mock_manager
        
        # Call the function
        result = main()
        
        # Verify the result
        self.assertEqual(result, 0)
        mock_manager_class.assert_called_once_with('test_profile')
        mock_manager.start_server.assert_called_once()

    @patch('tailsocks.cli.get_all_profiles')
    @patch('builtins.print')
    def test_show_status_all_profiles(self, mock_print, mock_get_all_profiles):
        """Test showing status for all profiles."""
        # Configure mock
        mock_get_all_profiles.return_value = [
            {
                'profile_name': 'profile1',
                'server_running': True,
                'session_up': True,
                'socks5_port': 1080,
                'ip_address': '100.100.100.100',
                'config_dir': '/path/to/config1',
                'cache_dir': '/path/to/cache1'
            },
            {
                'profile_name': 'profile2',
                'server_running': False,
                'session_up': False,
                'socks5_port': 1081,
                'ip_address': 'N/A',
                'config_dir': '/path/to/config2',
                'cache_dir': '/path/to/cache2'
            }
        ]
        
        # Call the function
        args = argparse.Namespace()
        args.profile = None
        show_status(args)
        
        # Verify print was called with expected information
        self.assertTrue(mock_print.called)
        
        # Convert all print calls to strings for easier checking
        printed_lines = []
        for call_args in mock_print.call_args_list:
            if call_args[0]:
                printed_lines.append(str(call_args[0][0]))
        
        # Join all printed lines into a single string for easier searching
        all_output = "\n".join(printed_lines)
        
        # Check that profile names were included in the output
        self.assertIn("profile1", all_output)
        self.assertIn("profile2", all_output)


if __name__ == '__main__':
    unittest.main()
