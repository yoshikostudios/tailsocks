"""
Test fixes for failing tests in the tailsocks package.
"""


def test_is_server_running_with_socket_and_pid(mock_manager, mocker):
    """Test checking if server is running when socket exists and PID is found."""
    # Reset any previous mocks on the method
    if hasattr(mock_manager._is_server_running, "reset_mock"):
        mock_manager._is_server_running.reset_mock()

    # Store the original method
    original_method = mock_manager._is_server_running

    # Unmock the _is_server_running method to test the real implementation
    if hasattr(mock_manager, "_is_server_running"):
        del mock_manager._is_server_running

    # Apply the mocks to the dependencies
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch.object(mock_manager, "_find_tailscaled_pid", return_value=12345)

    # Mock the subprocess.run call that's used as a fallback
    mock_process = mocker.MagicMock()
    mock_process.returncode = 0
    mocker.patch("subprocess.run", return_value=mock_process)

    # Test the actual method
    assert mock_manager._is_server_running() is True

    # Restore the original method if it was a mock
    if hasattr(original_method, "reset_mock"):
        mock_manager._is_server_running = original_method


def test_ensure_available_port_configured_port_in_use(mock_manager, mocker, capsys):
    """Test ensuring port is available when configured port is in use."""
    # Reset any previous mocks on the method
    if hasattr(mock_manager._ensure_available_port, "reset_mock"):
        mock_manager._ensure_available_port.reset_mock()

    # Store the original method
    original_method = mock_manager._ensure_available_port

    # Instead of trying to delete the attribute, we'll use the original implementation
    from tailsocks.manager import TailscaleProxyManager

    mock_manager._ensure_available_port = (
        TailscaleProxyManager._ensure_available_port.__get__(mock_manager)
    )

    # Set a configured bind address
    mock_manager.config = {"bind": "localhost:1080"}
    mock_manager.port = 1080
    mock_manager.bind_address = "localhost"

    # Create a more explicit side effect function to ensure port incrementation
    def port_in_use_side_effect(port):
        return port == 1080  # Only the original port is in use

    mocker.patch.object(
        mock_manager, "_is_port_in_use", side_effect=port_in_use_side_effect
    )

    result = mock_manager._ensure_available_port()

    assert result is True
    assert mock_manager.port == 1081

    # Restore the original method if it was a mock
    if hasattr(original_method, "reset_mock"):
        mock_manager._ensure_available_port = original_method
