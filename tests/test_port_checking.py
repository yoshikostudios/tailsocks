import unittest
from unittest.mock import patch, MagicMock
import socket
from tailsocks.manager import TailscaleProxyManager

class TestPortChecking(unittest.TestCase):
    """Tests for the port checking logic in TailscaleProxyManager."""

    def setUp(self):
        # Create a patch for socket.socket.connect_ex to simulate port availability
        self.socket_patcher = patch('socket.socket')
        self.mock_socket = self.socket_patcher.start()
        self.mock_socket_instance = MagicMock()
        self.mock_socket.return_value.__enter__.return_value = self.mock_socket_instance

    def tearDown(self):
        self.socket_patcher.stop()

    def test_init_does_not_check_port(self):
        """Test that __init__ doesn't check if ports are in use."""
        # Initialize the manager
        manager = TailscaleProxyManager(profile_name="test_profile")
        
        # Verify that connect_ex was not called during initialization
        self.mock_socket_instance.connect_ex.assert_not_called()
        
        # Verify the port is set to the default value
        self.assertEqual(manager.port, 1080)

    @patch('tailsocks.manager.TailscaleProxyManager._is_server_running')
    def test_start_server_checks_port(self, mock_is_server_running):
        """Test that start_server checks if the port is in use."""
        # Set up the mock to indicate server is not running
        mock_is_server_running.return_value = False
        
        # Set up socket.connect_ex to simulate port 1080 is in use
        self.mock_socket_instance.connect_ex.side_effect = lambda addr: 0 if addr[1] == 1080 else 1
        
        # Initialize the manager and start the server
        manager = TailscaleProxyManager(profile_name="test_profile")
        
        # Reset the mock to clear any calls during initialization
        self.mock_socket_instance.connect_ex.reset_mock()
        
        # Start the server
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Process is running
        mock_process.communicate.return_value = ('', '')  # Return empty stdout and stderr
        
        with patch('subprocess.Popen', return_value=mock_process):  # Prevent actual process creation
            manager.start_server()
        
        # Verify connect_ex was called during start_server
        self.mock_socket_instance.connect_ex.assert_called()
        
        # Verify the port was incremented
        self.assertEqual(manager.port, 1081)

    @patch('tailsocks.manager.TailscaleProxyManager._is_server_running')
    def test_start_server_with_configured_port(self, mock_is_server_running):
        """Test that start_server respects explicitly configured ports."""
        # Set up the mock to indicate server is not running
        mock_is_server_running.return_value = False
        
        # Set up socket.connect_ex to simulate port is in use
        self.mock_socket_instance.connect_ex.return_value = 0  # Port is in use
        
        # Initialize the manager with a specific port in config
        with patch('tailsocks.manager.TailscaleProxyManager._load_config') as mock_load_config:
            mock_load_config.return_value = {'socks5_port': 2000}
            manager = TailscaleProxyManager(profile_name="test_profile")
        
        # Reset the mock to clear any calls during initialization
        self.mock_socket_instance.connect_ex.reset_mock()
        
        # Start the server
        with patch('subprocess.Popen'):  # Prevent actual process creation
            result = manager.start_server()
        
        # Verify connect_ex was called during start_server
        self.mock_socket_instance.connect_ex.assert_called()
        
        # Verify the server failed to start due to port being in use
        self.assertFalse(result)

    @patch('tailsocks.manager.TailscaleProxyManager._is_server_running')
    def test_start_session_does_not_check_port(self, mock_is_server_running):
        """Test that start_session doesn't check if ports are in use."""
        # Set up the mock to indicate server is running
        mock_is_server_running.return_value = True
        
        # Initialize the manager
        manager = TailscaleProxyManager(profile_name="test_profile")
        
        # Reset the mock to clear any calls during initialization
        self.mock_socket_instance.connect_ex.reset_mock()
        
        # Start a session
        with patch('subprocess.run'):  # Prevent actual process execution
            manager.start_session()
        
        # Verify connect_ex was not called during start_session
        self.mock_socket_instance.connect_ex.assert_not_called()
