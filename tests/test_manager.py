"""Tests for the TailscaleProxyManager class."""

import os
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

    def test_load_config_file_not_found(self, mock_manager, mocker, capsys):
        """Test loading configuration when file doesn't exist."""
        # Mock open to raise FileNotFoundError
        mocker.patch("builtins.open", side_effect=FileNotFoundError())

        config = mock_manager._load_config()

        # Should return empty dict
        assert config == {}

        # Should print error message
        captured = capsys.readouterr()
        assert "Config file not found" in captured.out

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

        assert mock_manager._is_server_running() is True

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

        result = mock_manager._ensure_available_port()

        assert result is True
        assert mock_manager.port == 1081

        captured = capsys.readouterr()
        assert "Port 1080 is already in use" in captured.out

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


class TestProfileManagement:
    def test_get_all_profiles(self, mocker):
        """Test getting all profiles."""
        # Mock glob.glob to return some profile directories
        mocker.patch(
            "glob.glob",
            side_effect=[
                [
                    "/home/user/.config/tailscale-profile1",
                    "/home/user/.config/tailscale-profile2",
                ],
                [
                    "/home/user/.cache/tailscale-profile1",
                    "/home/user/.cache/tailscale-profile3",
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
