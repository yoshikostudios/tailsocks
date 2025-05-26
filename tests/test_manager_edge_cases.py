"""Tests for edge cases in the TailscaleProxyManager."""

import subprocess


def test_handle_error_with_exception(mock_manager, capsys):
    """Test error handling with an exception."""
    exception = ValueError("Test exception")
    result = mock_manager._handle_error("Error message", exception)

    captured = capsys.readouterr()
    assert result is False
    assert "Error message: Test exception" in captured.out


def test_handle_error_log_only(mock_manager, capsys):
    """Test error handling with log_only=True."""
    result = mock_manager._handle_error("Silent error", log_only=True)

    captured = capsys.readouterr()
    assert result is False
    assert captured.out == ""  # Nothing should be printed


def test_start_tailscaled_process_with_poll_timeout(mock_manager, mocker):
    """Test starting tailscaled process with a timeout during polling."""
    # Mock subprocess.Popen
    mock_popen = mocker.MagicMock()
    mock_popen.poll.return_value = None  # Process is running
    mocker.patch("subprocess.Popen", return_value=mock_popen)

    # Mock time.sleep to raise an exception after first call
    mock_sleep = mocker.patch("time.sleep")
    mock_sleep.side_effect = [None, TimeoutError("Timeout")]

    # Call the method
    result = mock_manager._start_tailscaled_process()

    # Should still succeed since process started
    assert result is True
    assert mock_manager.tailscaled_process == mock_popen


def test_start_session_with_login_url(mock_running_manager, mocker, capsys):
    """Test starting a session that returns a login URL."""
    # Mock subprocess.run to return a process with login URL
    mock_process = mocker.MagicMock()
    mock_process.returncode = 0
    mock_process.stdout = (
        "To authenticate, visit: https://login.tailscale.com/a/abcdef123"
    )
    mocker.patch("subprocess.run", return_value=mock_process)

    # Call with no auth token
    mock_running_manager.auth_token = ""
    result = mock_running_manager.start_session()

    captured = capsys.readouterr()
    assert result is True
    assert "To authenticate, visit:" in captured.out


def test_get_status_with_subprocess_exception(mock_running_manager, mocker):
    """Test getting status when subprocess raises an exception."""
    # Mock subprocess.run to raise an exception
    mocker.patch("subprocess.run", side_effect=subprocess.SubprocessError("Test error"))

    # Call the method
    status = mock_running_manager.get_status()

    # Should still return a valid status dict
    assert status["profile_name"] == "test_profile"
    assert status["server_running"] is True
    assert status["session_up"] is False
    assert status["ip_address"] == "N/A"


def test_is_server_running_with_socket_check_failure(mock_manager, mocker):
    """Test server running check when socket check fails."""
    # Mock os.path.exists to return True (socket exists)
    mocker.patch("os.path.exists", return_value=True)

    # Mock _find_tailscaled_pid to return None
    mocker.patch.object(mock_manager, "_find_tailscaled_pid", return_value=None)

    # Mock subprocess.run for socket check to fail
    mock_process = mocker.MagicMock()
    mock_process.returncode = 1
    mocker.patch("subprocess.run", return_value=mock_process)

    # Use the real implementation
    from tailsocks.manager import TailscaleProxyManager

    mock_manager._is_server_running = TailscaleProxyManager._is_server_running.__get__(
        mock_manager
    )

    # Call the method
    result = mock_manager._is_server_running()

    # Should return False
    assert result is False


def test_is_server_running_with_pgrep_fallback(mock_manager, mocker):
    """Test server running check with pgrep fallback."""
    # Mock os.path.exists to return True (socket exists)
    mocker.patch("os.path.exists", return_value=True)

    # Mock _find_tailscaled_pid to return None
    mocker.patch.object(mock_manager, "_find_tailscaled_pid", return_value=None)

    # Mock subprocess.run for socket check to raise exception, then succeed for pgrep
    def mock_run_side_effect(*args, **kwargs):
        cmd = args[0]
        if "status" in cmd:
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=5)
        elif "pgrep" in cmd:
            mock_result = mocker.MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "12345\n"
            return mock_result
        return mocker.MagicMock(returncode=1)

    mocker.patch("subprocess.run", side_effect=mock_run_side_effect)

    # Mock platform.system to return Linux
    mocker.patch("platform.system", return_value="Linux")

    # Use the real implementation
    from tailsocks.manager import TailscaleProxyManager

    mock_manager._is_server_running = TailscaleProxyManager._is_server_running.__get__(
        mock_manager
    )

    # Call the method
    result = mock_manager._is_server_running()

    # Should return True due to pgrep fallback
    assert result is True


def test_find_tailscaled_pid_with_multiple_pids(mock_manager, mocker):
    """Test finding tailscaled PID when multiple PIDs are returned."""
    # Mock platform.system to return Linux
    mocker.patch("platform.system", return_value="Linux")

    # Mock subprocess.run to return multiple PIDs
    mock_process = mocker.MagicMock()
    mock_process.returncode = 0
    mock_process.stdout = "12345\n67890\n"
    mocker.patch("subprocess.run", return_value=mock_process)

    # Use the real implementation
    from tailsocks.manager import TailscaleProxyManager

    mock_manager._find_tailscaled_pid = (
        TailscaleProxyManager._find_tailscaled_pid.__get__(mock_manager)
    )

    # Call the method
    pid = mock_manager._find_tailscaled_pid()

    # Should return the first PID
    assert pid == 12345
