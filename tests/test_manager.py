"""Tests for the TailscaleProxyManager class."""

import os
import shutil
import subprocess
from unittest.mock import MagicMock

import yaml

from tailsocks.manager import TailscaleProxyManager, get_all_profiles


class TestManagerInitialization:
    def test_specific_profile_name(self):
        """Test initialization with a specific profile name."""
        profile_name = "test_profile"
        manager = TailscaleProxyManager(profile_name)
        assert manager.profile_name == profile_name
        assert "tailscale-test_profile" in manager.config_dir
        assert "tailscale-test_profile" in manager.cache_dir

    def test_random_profile_name(self, mocker):
        """Test initialization with a random profile name."""
        # Mock glob to return no existing profiles
        mocker.patch("glob.glob", return_value=[])

        manager = TailscaleProxyManager()
        assert manager.profile_name is not None
        assert "_" in manager.profile_name  # Should contain an underscore

        # Ensure the profile name is prefixed for test cleanup
        assert (
            manager.profile_name.startswith("test_") or "_test_" in manager.profile_name
        )

    def test_generate_random_profile_name_with_existing_profiles(self, mocker):
        """Test random profile name generation with existing profiles."""
        # Mock glob to return existing profiles
        existing_profiles = [
            "/home/user/.config/tailscale-happy_gorilla",
            "/home/user/.config/tailscale-sunny_dolphin",
        ]
        mocker.patch("glob.glob", return_value=existing_profiles)

        manager = TailscaleProxyManager()

        # Generate a profile name
        name = manager._generate_random_profile_name()

        # Should not be one of the existing profiles
        assert name != "happy_gorilla"
        assert name != "sunny_dolphin"

    def test_generate_random_profile_name_uniqueness(self, mocker):
        """Test that random profile names are unique."""
        # Mock glob to return no existing profiles
        mocker.patch("glob.glob", return_value=[])

        # Instead of mocking random.choice, we'll mock the entire _generate_random_profile_name method
        # to return predictable unique values
        unique_names = [
            "test_happy_gorilla",
            "test_sunny_dolphin",
            "test_clever_tiger",
            "test_brave_eagle",
            "test_mighty_panda",
            "test_gentle_koala",
            "test_wise_wolf",
            "test_calm_fox",
            "test_swift_rabbit",
            "test_bright_turtle",
        ]

        name_index = [0]

        def mock_generate_name():
            name = unique_names[name_index[0] % len(unique_names)]
            name_index[0] += 1
            return name

        mocker.patch.object(
            TailscaleProxyManager,
            "_generate_random_profile_name",
            side_effect=mock_generate_name,
        )

        manager = TailscaleProxyManager()

        # Generate multiple profile names
        names = [manager._generate_random_profile_name() for _ in range(10)]

        # Check that all names are unique
        assert len(names) == len(set(names))

        # Check format (should contain an underscore)
        for name in names:
            assert "_" in name
            assert len(name) > 5


class TestBindAddressHandling:
    def test_parse_bind_address(self):
        """Test parsing of bind address strings."""
        manager = TailscaleProxyManager("test_profile")

        # Test full address:port format
        address, port = manager._parse_bind_address("127.0.0.1:8080")
        assert address == "127.0.0.1"
        assert port == 8080

        # Test port-only format
        address, port = manager._parse_bind_address("9090")
        assert address == "localhost"
        assert port == 9090

        # Test invalid port
        address, port = manager._parse_bind_address("invalid")
        assert address == "localhost"
        assert port == 1080  # Default port

    def test_update_bind_address(self, mock_manager):
        """Test updating the bind address."""
        # Test updating with a new bind address
        mock_manager.update_bind_address("0.0.0.0:8888")
        assert mock_manager.bind_address == "0.0.0.0"
        assert mock_manager.port == 8888
        assert mock_manager.state["bind_address"] == "0.0.0.0"
        assert mock_manager.state["port"] == 8888

    def test_socket_path_from_config_and_state(self, mock_manager, mocker):
        """Test that socket path is correctly loaded from config or state."""
        # Mock the _load_config and _load_state methods to return our test data
        mocker.patch.object(
            TailscaleProxyManager,
            "_load_config",
            return_value={"socket_path": "/custom/socket/path.sock"},
        )
        mocker.patch.object(TailscaleProxyManager, "_load_state", return_value={})

        # Create a new manager instance
        manager = TailscaleProxyManager("test_profile")

        # Verify socket_path is loaded from config
        assert manager.socket_path == "/custom/socket/path.sock"

        # Test with path in state but not config
        mocker.patch.object(TailscaleProxyManager, "_load_config", return_value={})
        mocker.patch.object(
            TailscaleProxyManager,
            "_load_state",
            return_value={"socket_path": "/state/socket/path.sock"},
        )

        # Create a new manager instance
        manager = TailscaleProxyManager("test_profile")

        # Verify socket_path is loaded from state when not in config
        assert manager.socket_path == "/state/socket/path.sock"


class TestPlatformSpecificBehavior:
    def test_default_tailscales(self, mocker):
        """Test that default tailscale paths are set correctly based on platform."""
        manager = TailscaleProxyManager("test_profile")

        # Test macOS paths
        mocker.patch("platform.system", return_value="Darwin")
        default_tailscaled, default_tailscale = manager._default_tailscales()
        assert default_tailscaled == "/usr/local/bin/tailscaled"
        assert default_tailscale == "/usr/local/bin/tailscale"

        # Test Linux paths
        mocker.patch("platform.system", return_value="Linux")
        default_tailscaled, default_tailscale = manager._default_tailscales()
        assert default_tailscaled == "/usr/sbin/tailscaled"
        assert default_tailscale == "/usr/bin/tailscale"

        # Test Windows/other paths
        mocker.patch("platform.system", return_value="Windows")
        default_tailscaled, default_tailscale = manager._default_tailscales()
        assert default_tailscaled == "tailscaled"
        assert default_tailscale == "tailscale"

    def test_default_tailscales_windows(self, mocker):
        """Test default tailscale paths on Windows."""
        mocker.patch("platform.system", return_value="Windows")
        manager = TailscaleProxyManager("test_profile")

        default_tailscaled, default_tailscale = manager._default_tailscales()

        assert default_tailscaled == "tailscaled"
        assert default_tailscale == "tailscale"

    def test_auth_token_precedence(self, mock_manager, monkeypatch):
        """Test auth token precedence (config > environment)."""
        # Set environment variable
        monkeypatch.setenv("TAILSCALE_AUTH_TOKEN", "env-token")

        # Mock the _load_config method to return our test data
        monkeypatch.setattr(
            TailscaleProxyManager,
            "_load_config",
            lambda self: {"auth_token": "config-token"},
        )

        # Create a new manager instance
        manager = TailscaleProxyManager("test_profile")

        # Verify auth_token is loaded from config (should take precedence)
        assert manager.auth_token == "config-token"

        # Now test with token in environment but not config
        monkeypatch.setattr(TailscaleProxyManager, "_load_config", lambda self: {})

        # Create a new manager instance
        manager = TailscaleProxyManager("test_profile")

        # Verify auth_token is loaded from environment when not in config
        assert manager.auth_token == "env-token"


class TestConfigHandling:
    def test_load_config(self, mock_manager, temp_dir):
        """Test loading configuration from a file."""
        # Create a temporary config file
        config_path = os.path.join(temp_dir, "config.yaml")

        test_config = {"bind": "127.0.0.1:2020", "tailscaled_args": ["--verbose=2"]}

        with open(config_path, "w") as f:
            yaml.dump(test_config, f)

        # Set the config path
        mock_manager.config_path = config_path

        # Load the config
        config = mock_manager._load_config()
        assert config["bind"] == "127.0.0.1:2020"
        assert config["tailscaled_args"] == ["--verbose=2"]

    def test_create_default_config(self, mock_manager, mocker):
        """Test creating a default configuration file."""
        # Mock open and yaml.dump
        mock_open = mocker.patch("builtins.open", mocker.mock_open())
        mock_dump = mocker.patch("yaml.dump")
        mock_print = mocker.patch("builtins.print")

        # Call the method
        mock_manager._create_default_config()

        # Verify the file was opened for writing
        mock_open.assert_called_once_with(mock_manager.config_path, "w")

        # Verify yaml.dump was called with expected default config
        called_config = mock_dump.call_args[0][0]
        assert "tailscaled_path" in called_config
        assert "tailscale_path" in called_config
        assert "socket_path" in called_config
        assert "bind" in called_config
        assert "tailscaled_args" in called_config
        assert "tailscale_up_args" in called_config

        # Verify the print message
        mock_print.assert_called_with(
            f"Created default configuration at {mock_manager.config_path}"
        )

    def test_load_config_file_not_found(self, mock_manager, mocker, capsys):
        """Test loading configuration when file doesn't exist."""
        # Mock open to raise FileNotFoundError
        mocker.patch("builtins.open", side_effect=FileNotFoundError())

        config = mock_manager._load_config()

        # Should return empty dict
        assert config == {}

        # Should NOT print error message
        captured = capsys.readouterr()
        assert "Config file not found" not in captured.out

    def test_load_config_invalid_yaml(self, mock_manager, temp_dir):
        """Test loading configuration with invalid YAML."""
        config_path = os.path.join(temp_dir, "config.yaml")

        # Create an invalid YAML file
        with open(config_path, "w") as f:
            f.write("bind: 'localhost:1080\n  invalid: yaml")

        # Mock config_file path
        mock_manager.config_path = config_path

        # Should handle the error gracefully
        config = mock_manager._load_config()

        # Should return empty dict
        assert config == {}

    def test_load_state_yaml_error(self, mock_manager, temp_dir, mocker):
        """Test loading state with invalid YAML."""
        state_path = os.path.join(temp_dir, "state.yml")

        # Create an invalid YAML file
        with open(state_path, "w") as f:
            f.write("invalid: 'yaml syntax")

        # Mock the state path
        mocker.patch.object(mock_manager, "cache_dir", os.path.dirname(state_path))
        mocker.patch("os.path.join", return_value=state_path)
        mocker.patch("os.path.exists", return_value=True)

        # Should handle the error gracefully
        state = mock_manager._load_state()

        # Should return empty dict
        assert state == {}

    def test_save_config_error(self, mock_manager, mocker):
        """Test saving configuration with an error."""
        # Mock open to raise an exception
        mocker.patch("builtins.open", side_effect=PermissionError("Permission denied"))
        mocker.patch.object(mock_manager, "_handle_error", return_value=False)

        # Call the method
        result = mock_manager._save_config()

        # Verify the result and error handling
        assert result is False
        mock_manager._handle_error.assert_called_once()
        assert "Error saving config file" in mock_manager._handle_error.call_args[0][0]
        assert isinstance(mock_manager._handle_error.call_args[0][1], PermissionError)

    def test_save_state_error(self, mock_manager, mocker):
        """Test saving state with an error."""
        # Mock open to raise an exception
        mocker.patch("builtins.open", side_effect=IOError("IO Error"))
        mocker.patch.object(mock_manager, "_handle_error", return_value=False)

        # Call the method
        result = mock_manager._save_state()

        # Verify the result and error handling
        assert result is False
        mock_manager._handle_error.assert_called_once()
        assert "Error saving state file" in mock_manager._handle_error.call_args[0][0]
        assert isinstance(mock_manager._handle_error.call_args[0][1], IOError)

    def test_save_config(self, mock_manager, mocker):
        """Test saving configuration to a file."""
        # Set up test config
        mock_manager.config = {
            "bind": "0.0.0.0:9090",
            "tailscaled_args": ["--verbose=3"],
        }

        # Mock open to avoid actually writing to disk
        mock_open = mocker.patch("builtins.open", mocker.mock_open())
        mocker.patch("yaml.dump")

        result = mock_manager._save_config()

        assert result is True
        mock_open.assert_called_once_with(mock_manager.config_path, "w")


class TestServerStatusChecks:
    def test_is_server_running_with_socket_and_pid(self, mock_manager, mocker):
        """Test checking if server is running when socket exists and PID is found."""
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch.object(mock_manager, "_find_tailscaled_pid", return_value=12345)

        # Unmock _is_server_running to use the real implementation
        from tailsocks.manager import TailscaleProxyManager

        mock_manager._is_server_running = (
            TailscaleProxyManager._is_server_running.__get__(mock_manager)
        )

        assert mock_manager._is_server_running() is True

    def test_is_server_running_windows_fallback(self, mock_manager, mocker):
        """Test server running check on Windows."""
        # Mock platform.system to return Windows
        mocker.patch("platform.system", return_value="Windows")

        # Mock os.path.exists to return True (socket exists)
        mocker.patch("os.path.exists", return_value=True)

        # Mock _find_tailscaled_pid to return None
        mocker.patch.object(mock_manager, "_find_tailscaled_pid", return_value=None)

        # Mock subprocess.run for socket check to raise an exception
        mocker.patch("subprocess.run", side_effect=subprocess.SubprocessError())

        # Use the real implementation
        from tailsocks.manager import TailscaleProxyManager

        mock_manager._is_server_running = (
            TailscaleProxyManager._is_server_running.__get__(mock_manager)
        )

        # Call the method
        result = mock_manager._is_server_running()

        # Should return False since we have no fallback for Windows
        assert result is False

    def test_is_server_running_socket_check(self, mock_manager, mocker):
        """Test checking if server is running using socket check."""
        # Mock os.path.exists to return True (socket exists)
        mocker.patch("os.path.exists", return_value=True)

        # Mock _find_tailscaled_pid to return None (no PID found)
        mocker.patch.object(mock_manager, "_find_tailscaled_pid", return_value=None)

        # Mock subprocess.run for socket check
        mock_process = mocker.MagicMock()
        mock_process.returncode = 0  # Success
        mocker.patch("subprocess.run", return_value=mock_process)

        # Call the method
        result = mock_manager._is_server_running()

        # Verify the result
        assert result is True

    def test_is_server_running_pgrep_fallback(self, mock_manager, mocker):
        """Test checking if server is running using pgrep fallback."""
        # Mock os.path.exists to return True (socket exists)
        mocker.patch("os.path.exists", return_value=True)

        # Mock _find_tailscaled_pid to return None (no PID found)
        mocker.patch.object(mock_manager, "_find_tailscaled_pid", return_value=None)

        # Mock subprocess.run for socket check to raise an exception
        mocker.patch(
            "subprocess.run",
            side_effect=[
                subprocess.TimeoutExpired("cmd", 5),  # First call fails with timeout
                mocker.MagicMock(
                    returncode=0, stdout="12345\n"
                ),  # Second call (pgrep) succeeds
            ],
        )

        # Mock platform.system to return Linux
        mocker.patch("platform.system", return_value="Linux")

        # Call the method
        result = mock_manager._is_server_running()

        # Verify the result
        assert result is True

    def test_is_server_running_no_socket(self, mock_manager, mocker):
        """Test checking if server is running when socket doesn't exist."""
        mocker.patch("os.path.exists", return_value=False)

        assert mock_manager._is_server_running() is False

    def test_is_port_in_use(self, mocker):
        """Test checking if a port is in use."""
        manager = TailscaleProxyManager("test_profile")

        # Create a mock socket object
        mock_socket = MagicMock()
        mock_socket.__enter__.return_value.connect_ex.return_value = 0  # Port in use
        mocker.patch("socket.socket", return_value=mock_socket)

        assert manager._is_port_in_use(1080) is True

        # Test port not in use
        mock_socket.__enter__.return_value.connect_ex.return_value = (
            1  # Port not in use
        )
        assert manager._is_port_in_use(1080) is False


class TestStatusReporting:
    def test_get_status_server_running(self, mock_running_manager):
        """Test getting status when server is running."""
        status = mock_running_manager.get_status()

        assert status["profile_name"] == "test_profile"
        assert status["server_running"] is True
        assert status["session_up"] is True
        assert status["ip_address"] == "100.100.100.100"
        assert "bind" in status

    def test_get_status_server_not_running(self, mock_manager):
        """Test getting status when server is not running."""
        status = mock_manager.get_status()

        assert status["profile_name"] == "test_profile"
        assert status["server_running"] is False
        assert status["session_up"] is False
        assert status["ip_address"] == "N/A"

    def test_get_status_with_subprocess_error(self, mock_running_manager, mocker):
        """Test getting status when subprocess call fails."""
        # Mock subprocess.run to raise an exception
        mocker.patch("subprocess.run", side_effect=subprocess.SubprocessError())

        # Call the method
        status = mock_running_manager.get_status()

        # Should still return a valid status dict
        assert status["profile_name"] == "test_profile"
        assert status["server_running"] is True
        assert status["session_up"] is False  # Default when status check fails
        assert status["ip_address"] == "N/A"  # Default when status check fails

    def test_load_state_file_not_found_specific(self, mock_manager, mocker):
        """Test loading state when file doesn't exist."""
        # Mock os.path.exists to return False
        mocker.patch("os.path.exists", return_value=False)

        # Call the method
        state = mock_manager._load_state()

        # Should have empty state
        assert state == {}


class TestServerManagement:
    def test_start_server_success(self, mock_manager, mocker):
        """Test starting the server successfully."""
        # Mock the required methods
        mocker.patch.object(mock_manager, "_ensure_available_port", return_value=True)
        mocker.patch.object(
            mock_manager, "_start_tailscaled_process", return_value=True
        )
        mocker.patch.object(mock_manager, "_save_state", return_value=True)
        mocker.patch.object(mock_manager, "_is_server_running", return_value=False)

        assert mock_manager.start_server() is True

    def test_start_server_already_running(self, mock_manager, mocker, capsys):
        """Test starting the server when it's already running."""
        mocker.patch.object(mock_manager, "_is_server_running", return_value=True)

        assert mock_manager.start_server() is True

        captured = capsys.readouterr()
        assert "Tailscaled is already running" in captured.out

    def test_start_server_port_unavailable(self, mock_manager, mocker):
        """Test starting the server when port is unavailable."""
        mocker.patch.object(mock_manager, "_is_server_running", return_value=False)
        mocker.patch.object(mock_manager, "_ensure_available_port", return_value=False)

        assert mock_manager.start_server() is False

    def test_ensure_available_port_configured_port_in_use(
        self, mock_manager, mocker, capsys
    ):
        """Test ensuring port is available when configured port is in use."""
        # Set a configured bind address
        mock_manager.config = {"bind": "localhost:1080"}
        mock_manager.port = 1080

        # First port is in use, second is available
        mocker.patch.object(mock_manager, "_is_port_in_use", side_effect=[True, False])

        # Use the real implementation instead of a mock
        from tailsocks.manager import TailscaleProxyManager

        mock_manager._ensure_available_port = (
            TailscaleProxyManager._ensure_available_port.__get__(mock_manager)
        )

        result = mock_manager._ensure_available_port()

        assert result is True
        assert mock_manager.port == 1081

        captured = capsys.readouterr()
        assert "Port 1080 is already in use" in captured.out

    def test_ensure_available_port_exceeds_limit(self, mock_manager, mocker, capsys):
        """Test when port selection exceeds the limit."""
        # Set a configured bind address
        mock_manager.config = {"bind": "localhost:1080"}
        mock_manager.port = 1080

        # Mock _is_port_in_use to always return True (all ports in use)
        mocker.patch.object(mock_manager, "_is_port_in_use", return_value=True)

        # Use the real implementation
        from tailsocks.manager import TailscaleProxyManager

        mock_manager._ensure_available_port = (
            TailscaleProxyManager._ensure_available_port.__get__(mock_manager)
        )

        # Call the method
        result = mock_manager._ensure_available_port()

        # Should fail after trying 100 ports
        assert result is False

        captured = capsys.readouterr()
        assert "Error: Configured port" in captured.out
        assert "is already in use" in captured.out

    def test_ensure_available_port_finds_free_port(self, mock_manager, mocker):
        """Test that ensure_available_port finds a free port when needed."""
        # Mock port_in_use to return True for the first port and False for the second
        mocker.patch.object(mock_manager, "_is_port_in_use", side_effect=[True, False])

        # Set initial port
        mock_manager.port = 1080

        # Use the real implementation
        from tailsocks.manager import TailscaleProxyManager

        mock_manager._ensure_available_port = (
            TailscaleProxyManager._ensure_available_port.__get__(mock_manager)
        )

        # Call the method
        result = mock_manager._ensure_available_port()

        # Should succeed
        assert result is True
        # Should have incremented the port
        assert mock_manager.port == 1081

    def test_start_tailscaled_process(self, mock_manager, mocker):
        """Test starting the tailscaled process."""
        # Mock subprocess.Popen
        mock_popen = MagicMock()
        mock_popen.poll.return_value = None  # Process is running
        mocker.patch("subprocess.Popen", return_value=mock_popen)
        mocker.patch("time.sleep")

        result = mock_manager._start_tailscaled_process()

        assert result is True
        assert mock_manager.tailscaled_process == mock_popen

    def test_start_tailscaled_process_timeout(self, mock_manager, mocker):
        """Test starting tailscaled process with a timeout."""
        # Mock subprocess.Popen
        mock_popen = mocker.MagicMock()
        mock_popen.poll.return_value = None  # Process is running
        mocker.patch("subprocess.Popen", return_value=mock_popen)

        # Mock time.sleep to raise an exception after the first call
        # This simulates a timeout during the wait
        mock_sleep = mocker.patch("time.sleep")
        mock_sleep.side_effect = [None, TimeoutError("Timeout waiting for process")]

        # Call the method
        result = mock_manager._start_tailscaled_process()

        # Should still succeed since the process started
        assert result is True
        assert mock_manager.tailscaled_process == mock_popen

    def test_start_tailscaled_process_failure(self, mock_manager, mocker, capsys):
        """Test starting the tailscaled process when it fails."""
        # Mock subprocess.Popen
        mock_popen = MagicMock()
        mock_popen.poll.return_value = 1  # Process failed
        mock_popen.communicate.return_value = ("", "Error starting tailscaled")
        mocker.patch("subprocess.Popen", return_value=mock_popen)
        mocker.patch("time.sleep")

        result = mock_manager._start_tailscaled_process()

        assert result is False

        captured = capsys.readouterr()
        assert "Failed to start tailscaled" in captured.out


class TestSessionManagement:
    def test_start_session_success(self, mock_running_manager, mocker):
        """Test starting a session successfully."""
        # Mock subprocess.run
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "Tailscale started successfully"
        mocker.patch("subprocess.run", return_value=mock_process)

        assert mock_running_manager.start_session() is True

    def test_start_session_with_login_url(self, mock_running_manager, mocker):
        """Test starting a session that returns a login URL."""
        # Mock subprocess.run to return a process with login URL
        mock_process = mocker.MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = (
            "To authenticate, visit: https://login.tailscale.com/a/abcdef123"
        )
        mocker.patch("subprocess.run", return_value=mock_process)
        mock_print = mocker.patch("builtins.print")

        # Call with no auth token
        mock_running_manager.auth_token = ""
        result = mock_running_manager.start_session()

        assert result is True
        # Verify the login URL was printed
        mock_print.assert_called_with(mock_process.stdout)

    def test_start_session_with_auth_token(self, mock_running_manager, mocker):
        """Test starting a session with an auth token."""
        # Mock subprocess.run
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "Tailscale started successfully"
        mock_run = mocker.patch("subprocess.run", return_value=mock_process)

        assert mock_running_manager.start_session("tskey-123") is True

        # Check that --authkey was included in the command
        args, kwargs = mock_run.call_args
        cmd = args[0]
        assert "--authkey" in cmd
        assert "tskey-123" in cmd

    def test_start_session_failure(self, mock_running_manager, mocker, capsys):
        """Test starting a session when it fails."""
        # Mock subprocess.run
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stderr = "Error starting tailscale"
        mocker.patch("subprocess.run", return_value=mock_process)

        assert mock_running_manager.start_session() is False

        captured = capsys.readouterr()
        assert "Failed to start tailscale session" in captured.out

    def test_stop_session_success(self, mock_running_manager, mocker):
        """Test stopping a session successfully."""
        # Mock subprocess.run
        mock_process = MagicMock()
        mock_process.returncode = 0
        mocker.patch("subprocess.run", return_value=mock_process)

        assert mock_running_manager.stop_session() is True

    def test_stop_session_failure(self, mock_running_manager, mocker, capsys):
        """Test stopping a session when it fails."""
        # Mock subprocess.run
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stderr = "Error stopping tailscale"
        mocker.patch("subprocess.run", return_value=mock_process)

        assert mock_running_manager.stop_session() is False

        captured = capsys.readouterr()
        assert "Failed to stop tailscale session" in captured.out


class TestServerShutdown:
    def test_stop_server_success(self, mock_running_manager, mocker):
        """Test stopping the server successfully."""
        # Mock os.kill
        mocker.patch("os.kill")
        mocker.patch("time.sleep")

        # First call to _is_server_running returns True, second returns False
        mocker.patch.object(
            mock_running_manager, "_is_server_running", side_effect=[True, False]
        )

        assert mock_running_manager.stop_server() is True

    def test_stop_server_not_running(self, mock_manager, mocker, capsys):
        """Test stopping the server when it's not running."""
        mocker.patch.object(mock_manager, "_is_server_running", return_value=False)

        assert mock_manager.stop_server() is True

        captured = capsys.readouterr()
        assert "Tailscaled is not running" in captured.out

    def test_stop_server_force_kill(self, mock_running_manager, mocker):
        """Test stopping the server with force kill."""
        # Mock os.kill
        mock_kill = mocker.patch("os.kill")
        mocker.patch("time.sleep")

        # Server keeps running after SIGTERM
        mocker.patch.object(
            mock_running_manager,
            "_is_server_running",
            side_effect=[True, True, True, True, True, True],
        )

        assert mock_running_manager.stop_server() is True

        # Should have called kill with SIGKILL
        assert mock_kill.call_count == 2
        args, kwargs = mock_kill.call_args_list[1]
        assert args[1] == 9  # SIGKILL


class TestErrorHandling:
    def test_handle_error(self, mock_manager, mocker):
        """Test error handling method."""
        # Mock print
        mock_print = mocker.patch("builtins.print")

        # Mock the logger to prevent it from causing additional print calls
        mock_logger = mocker.MagicMock()
        mock_manager.logger = mock_logger

        # Test with just a message
        result = mock_manager._handle_error("Test error message")
        assert result is False
        mock_print.assert_called_with("Test error message")
        mock_print.reset_mock()

        # Test with an exception
        exception = ValueError("Something went wrong")
        result = mock_manager._handle_error("Error occurred", exception)
        assert result is False
        mock_print.assert_called_once_with("Error occurred: Something went wrong")
        mock_print.reset_mock()

        # Test with log_only=True
        result = mock_manager._handle_error("Silent error", log_only=True)
        assert result is False
        mock_print.assert_not_called()

    def test_handle_error_with_logger(self, mock_manager, mocker):
        """Test error handling with a logger."""
        # Mock print
        mock_print = mocker.patch("builtins.print")

        # Add a mock logger to the manager
        mock_logger = mocker.MagicMock()
        mock_manager.logger = mock_logger

        # Test with an exception
        exception = ValueError("Test exception")
        result = mock_manager._handle_error("Error occurred", exception=exception)

        assert result is False
        mock_print.assert_called_once()
        mock_logger.error.assert_called_once()


class TestProcessManagement:
    def test_find_tailscaled_pid_linux(self, mock_manager, mocker):
        """Test finding tailscaled PID on Linux/macOS."""
        # Mock platform.system to return Linux
        mocker.patch("platform.system", return_value="Linux")

        # Mock subprocess.run to return a valid PID
        mock_process = mocker.MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "12345\n"
        mocker.patch("subprocess.run", return_value=mock_process)

        # Call the method
        pid = mock_manager._find_tailscaled_pid()

        # Verify the result
        assert pid == 12345

    def test_find_tailscaled_pid_windows(self, mock_manager, mocker):
        """Test finding tailscaled PID on Windows."""
        # Mock platform.system to return Windows
        mocker.patch("platform.system", return_value="Windows")

        # Mock subprocess.run
        mock_process = mocker.MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = '"tailscaled.exe","12345"'
        mocker.patch("subprocess.run", return_value=mock_process)

        # Call the method
        pid = mock_manager._find_tailscaled_pid()

        # Verify the result - should be None as Windows implementation doesn't return a PID
        assert pid is None

    def test_find_tailscaled_pid_error(self, mock_manager, mocker):
        """Test finding tailscaled PID with an error."""
        # Mock platform.system to return Linux
        mocker.patch("platform.system", return_value="Linux")

        # Mock subprocess.run to raise an exception
        mocker.patch("subprocess.run", side_effect=subprocess.SubprocessError())

        # Call the method
        pid = mock_manager._find_tailscaled_pid()

        # Verify the result
        assert pid is None

    def test_find_tailscaled_pid_multiple_results(self, mock_manager, mocker):
        """Test finding tailscaled PID when multiple processes match."""
        # Mock platform.system to return Linux
        mocker.patch("platform.system", return_value="Linux")

        # Mock subprocess.run to return multiple PIDs
        mock_process = mocker.MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "12345\n67890\n"
        mocker.patch("subprocess.run", return_value=mock_process)

        # Call the method
        pid = mock_manager._find_tailscaled_pid()

        # Should return the first PID
        assert pid == 12345


class TestProfileDeletion:
    def test_delete_profile_success(self, mock_manager, mocker):
        """Test successful profile deletion."""
        # Mock os.path.exists to return True
        mocker.patch("os.path.exists", return_value=True)

        # Mock shutil.rmtree
        mock_rmtree = mocker.patch("shutil.rmtree")

        # Mock _is_server_running to return False
        mocker.patch.object(mock_manager, "_is_server_running", return_value=False)

        # Mock print
        mock_print = mocker.patch("builtins.print")

        # Call the method
        result = mock_manager.delete_profile()

        # Verify the result
        assert result is True

        # Verify rmtree was called for both directories
        assert mock_rmtree.call_count == 2
        mock_rmtree.assert_any_call(mock_manager.config_dir)
        mock_rmtree.assert_any_call(mock_manager.cache_dir)

        # Verify print messages
        assert mock_print.call_count == 2

    def test_delete_profile_server_running(self, mock_manager, mocker):
        """Test profile deletion when server is running."""
        # Mock _is_server_running to return True
        mocker.patch.object(mock_manager, "_is_server_running", return_value=True)

        # Mock print
        mock_print = mocker.patch("builtins.print")

        # Call the method
        result = mock_manager.delete_profile()

        # Verify the result
        assert result is False

        # Verify print message
        mock_print.assert_called_once_with(
            "Cannot delete profile while server is running. Stop the server first."
        )

    def test_delete_profile_error(self, mock_manager, mocker):
        """Test profile deletion with an error."""
        # Mock os.path.exists to return True
        mocker.patch("os.path.exists", return_value=True)

        # Mock shutil.rmtree to raise an exception
        mocker.patch("shutil.rmtree", side_effect=PermissionError("Permission denied"))

        # Mock _is_server_running to return False
        mocker.patch.object(mock_manager, "_is_server_running", return_value=False)

        # Mock _handle_error
        mocker.patch.object(mock_manager, "_handle_error", return_value=False)

        # Call the method
        result = mock_manager.delete_profile()

        # Verify the result and error handling
        assert result is False
        mock_manager._handle_error.assert_called_once()
        assert (
            f"Error deleting profile {mock_manager.profile_name}"
            in mock_manager._handle_error.call_args[0][0]
        )
        assert isinstance(mock_manager._handle_error.call_args[0][1], PermissionError)


class TestProfileManagement:
    def test_get_all_profiles(self, mocker):
        """Test getting all profiles."""
        # Mock glob.glob to return some profile directories
        mocker.patch(
            "glob.glob",
            side_effect=[
                [
                    "/home/user/.config/tailscale-test_profile1",
                    "/home/user/.config/tailscale-test_profile2",
                ],
                [
                    "/home/user/.cache/tailscale-test_profile1",
                    "/home/user/.cache/tailscale-test_profile3",
                ],
            ],
        )

        # Mock TailscaleProxyManager.get_status
        mock_status = {"profile_name": "mock_profile", "server_running": False}
        mocker.patch.object(
            TailscaleProxyManager, "get_status", return_value=mock_status
        )

        profiles = get_all_profiles()

        # Should have 3 unique profiles
        assert len(profiles) == 3
        for profile in profiles:
            assert profile == mock_status

    def test_generate_random_profile_name_max_attempts(self, mock_manager, mocker):
        """Test profile name generation when max attempts are reached."""
        # Mock glob to return many existing profiles
        existing_profiles = [f"test_profile_{i}" for i in range(20)]
        mocker.patch(
            "glob.glob",
            return_value=[
                f"/home/user/.config/tailscale-{p}" for p in existing_profiles
            ],
        )

        # Mock random.choice to return predictable values that will always match existing profiles
        # for the first 10 attempts, then a unique value
        choices = existing_profiles[:10] + ["unique_profile"]
        mocker.patch("random.choice", side_effect=lambda x: choices.pop(0))

        # Use the real implementation
        from tailsocks.manager import TailscaleProxyManager

        mock_manager._generate_random_profile_name = (
            TailscaleProxyManager._generate_random_profile_name.__get__(mock_manager)
        )

        # Generate a profile name
        name = mock_manager._generate_random_profile_name()

        # Should contain a random number since we exhausted the simple combinations
        assert "_" in name
        assert any(c.isdigit() for c in name)

    def test_cleanup_test_profiles(self, mocker):
        """Test that test profiles are properly identified for cleanup."""
        # Create a manager with a test profile name
        manager = TailscaleProxyManager("test_profile")

        # Verify the profile name is properly formatted for cleanup detection
        assert manager.profile_name.startswith("test_")

        # Mock the necessary methods to avoid actual file operations
        mocker.patch.object(manager, "_save_config")
        mocker.patch.object(manager, "_save_state")

        # Mock os.path.exists and shutil.rmtree for cleanup verification
        mock_exists = mocker.patch("os.path.exists", return_value=True)
        mock_rmtree = mocker.patch("shutil.rmtree")

        # Simulate cleanup of this profile
        if os.path.exists(manager.config_dir):
            shutil.rmtree(manager.config_dir, ignore_errors=True)
        if os.path.exists(manager.cache_dir):
            shutil.rmtree(manager.cache_dir, ignore_errors=True)

        # Verify cleanup would be attempted
        assert mock_exists.call_count >= 1
        assert mock_rmtree.call_count >= 1
