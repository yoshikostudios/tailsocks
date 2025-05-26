"""Tests for the CLI functionality."""

from unittest.mock import MagicMock, patch

from tailsocks.cli import (
    _handle_delete_profile,
    _handle_start_server,
    _handle_start_session,
    _handle_stop_server,
    _handle_stop_session,
    _print_status,
    _require_profile_selection,
    handle_command,
    main,
    show_status,
)


class TestStatusDisplay:
    def test_print_status_with_header(self, capsys):
        """Test printing status information with header."""
        status = {
            "profile_name": "test_profile",
            "server_running": True,
            "session_up": False,
            "bind": "localhost:1080",
            "ip_address": "100.100.100.100",
            "config_dir": "/home/user/.config/tailscale-test_profile",
            "cache_dir": "/home/user/.cache/tailscale-test_profile",
            "last_started": "2023-01-01 12:00:00",
            "using_auth_token": True,
        }

        _print_status(status)

        captured = capsys.readouterr()
        assert "Profile: test_profile" in captured.out
        assert "Server running: Yes" in captured.out
        assert "Session up: No" in captured.out
        assert "Bind address: localhost:1080" in captured.out
        assert "IP address: 100.100.100.100" in captured.out

    def test_print_status_with_partial_data(self, capsys):
        """Test printing status with missing fields."""
        status = {
            "profile_name": "test_profile",
            "server_running": True,
            # Missing some fields
        }

        _print_status(status)
        captured = capsys.readouterr()

        assert "test_profile" in captured.out
        assert "Server running: Yes" in captured.out

    def test_print_status_without_header(self, capsys):
        """Test printing status information without header."""
        status = {
            "profile_name": "test_profile",
            "server_running": True,
        }

        _print_status(status, show_header=False)

        captured = capsys.readouterr()
        assert "Profile: test_profile" not in captured.out
        assert "Server running: Yes" in captured.out

    def test_show_status_specific_profile(self, mock_cli_args, mocker):
        """Test showing status for a specific profile."""
        mock_cli_args.profile = "test_profile"

        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {"profile_name": "test_profile"}

        with patch("tailsocks.cli.TailscaleProxyManager", return_value=mock_manager):
            with patch("tailsocks.cli._print_status") as mock_print:
                show_status(mock_cli_args)

                mock_print.assert_called_once_with({"profile_name": "test_profile"})

    def test_show_status_all_profiles(self, mock_cli_args, mocker, capsys):
        """Test showing status for all profiles."""
        mock_cli_args.profile = None

        profiles = [{"profile_name": "profile1"}, {"profile_name": "profile2"}]

        with patch("tailsocks.cli.get_all_profiles", return_value=profiles):
            show_status(mock_cli_args)

            captured = capsys.readouterr()
            assert "Found 2 profile(s)" in captured.out
            assert "profile1" in captured.out
            assert "profile2" in captured.out

    def test_show_status_no_profiles(self, mock_cli_args, mocker, capsys):
        """Test showing status when no profiles exist."""
        mock_cli_args.profile = None

        with patch("tailsocks.cli.get_all_profiles", return_value=[]):
            show_status(mock_cli_args)

            captured = capsys.readouterr()
            assert "No profiles found" in captured.out


class TestProfileSelection:
    def test_require_profile_selection_with_arg(self, mock_cli_args):
        """Test profile selection when profile is provided in args."""
        mock_cli_args.profile = "specified_profile"

        result = _require_profile_selection(mock_cli_args, "test-command")
        assert result == "specified_profile"

    def test_require_profile_selection_with_no_profiles(
        self, mock_cli_args, mocker, capsys
    ):
        """Test profile selection when no profiles exist."""
        mock_cli_args.profile = None
        mocker.patch("tailsocks.cli.get_all_profiles", return_value=[])

        result = _require_profile_selection(mock_cli_args, "test-command")

        captured = capsys.readouterr()
        assert result is None
        assert "Error: No profiles exist" in captured.out

    def test_require_profile_selection_with_single_profile(
        self, mock_cli_args, mocker, capsys
    ):
        """Test profile selection when only one profile exists."""
        mock_cli_args.profile = None
        mocker.patch(
            "tailsocks.cli.get_all_profiles",
            return_value=[{"profile_name": "only_profile"}],
        )

        result = _require_profile_selection(mock_cli_args, "test-command")

        captured = capsys.readouterr()
        assert result == "only_profile"
        assert "Using the only existing profile: only_profile" in captured.out

    def test_require_profile_selection_with_multiple_profiles(
        self, mock_cli_args, mocker, capsys
    ):
        """Test profile selection when multiple profiles exist."""
        mock_cli_args.profile = None
        mocker.patch(
            "tailsocks.cli.get_all_profiles",
            return_value=[{"profile_name": "profile1"}, {"profile_name": "profile2"}],
        )

        result = _require_profile_selection(mock_cli_args, "test-command")

        captured = capsys.readouterr()
        assert result is None
        assert "Error: Multiple profiles exist" in captured.out
        assert "profile1" in captured.out
        assert "profile2" in captured.out


class TestCommandHandlers:
    def test_handle_start_server_with_bind(self, mock_manager, mock_cli_args):
        """Test handling the start-server command with bind address."""
        mock_cli_args.bind = "0.0.0.0:8080"

        with patch.object(mock_manager, "update_bind_address") as mock_update:
            with patch.object(
                mock_manager, "start_server", return_value=True
            ) as mock_start:
                result = _handle_start_server(mock_manager, mock_cli_args)

                assert result is True
                mock_update.assert_called_once_with("0.0.0.0:8080")
                mock_start.assert_called_once()

    def test_handle_start_server_without_bind(self, mock_manager, mock_cli_args):
        """Test handling the start-server command without bind address."""
        mock_cli_args.bind = None

        with patch.object(
            mock_manager, "start_server", return_value=True
        ) as mock_start:
            result = _handle_start_server(mock_manager, mock_cli_args)

            assert result is True
            mock_start.assert_called_once()

    def test_handle_start_session_server_not_running(
        self, mock_manager, mock_cli_args, capsys
    ):
        """Test handling start-session when server is not running."""
        mock_cli_args.auth_token = "tskey-123"

        with patch.object(mock_manager, "_is_server_running", return_value=False):
            result = _handle_start_session(mock_manager, mock_cli_args)

            assert result is False
            captured = capsys.readouterr()
            assert "Error: Tailscaled is not running" in captured.out

    def test_handle_start_session_with_auth_token(
        self, mock_running_manager, mock_cli_args
    ):
        """Test handling start-session with auth token."""
        mock_cli_args.auth_token = "tskey-123"

        with patch.object(
            mock_running_manager, "start_session", return_value=True
        ) as mock_start:
            result = _handle_start_session(mock_running_manager, mock_cli_args)

            assert result is True
            mock_start.assert_called_once_with("tskey-123")

    def test_handle_stop_session_not_running(self, mock_manager, capsys):
        """Test handling stop-session when server is not running."""
        with patch.object(mock_manager, "_is_server_running", return_value=False):
            result = _handle_stop_session(mock_manager)

            assert result is False
            captured = capsys.readouterr()
            assert "Error: No tailscale services are running" in captured.out

    def test_handle_stop_session_running(self, mock_running_manager):
        """Test handling stop-session when server is running."""
        with patch.object(
            mock_running_manager, "stop_session", return_value=True
        ) as mock_stop:
            result = _handle_stop_session(mock_running_manager)

            assert result is True
            mock_stop.assert_called_once()

    def test_handle_stop_server(self, mock_running_manager):
        """Test handling stop-server command."""
        with patch.object(
            mock_running_manager, "stop_server", return_value=True
        ) as mock_stop:
            result = _handle_stop_server(mock_running_manager)

            assert result is True
            mock_stop.assert_called_once()

    def test_handle_delete_profile_running(self, mock_running_manager, capsys):
        """Test handling delete-profile when server is running."""
        with patch.object(
            mock_running_manager, "_is_server_running", return_value=True
        ):
            result = _handle_delete_profile(mock_running_manager)

            assert result is False
            captured = capsys.readouterr()
            assert "Error: Cannot delete profile" in captured.out

    def test_handle_delete_profile_success(self, mock_manager, mocker):
        """Test handling delete-profile command successfully."""
        with patch.object(mock_manager, "_is_server_running", return_value=False):
            with patch("os.path.exists", return_value=True):
                with patch("shutil.rmtree") as mock_rmtree:
                    # Make sure the paths contain the expected substrings
                    mock_manager.config_dir = (
                        "/home/user/.config/tailscale-test_profile"
                    )
                    mock_manager.cache_dir = "/home/user/.cache/tailscale-test_profile"

                    result = _handle_delete_profile(mock_manager)

                    assert result is True
                    assert mock_rmtree.call_count == 2


class TestCommandDispatch:
    def test_handle_command_status(self, mocker):
        """Test handling the status command."""
        args = MagicMock()
        args.command = "status"

        with patch("tailsocks.cli.show_status") as mock_show:
            result = handle_command(args)

            assert result == 0
            mock_show.assert_called_once_with(args)

    def test_handle_command_with_profile_selection(self, mocker):
        """Test handling commands that require profile selection."""
        args = MagicMock()
        args.command = "start-server"
        args.profile = None

        # Mock _require_profile_selection to return a profile
        with patch(
            "tailsocks.cli._require_profile_selection", return_value="selected_profile"
        ):
            with patch("tailsocks.cli.TailscaleProxyManager") as mock_manager_class:
                mock_manager = MagicMock()
                mock_manager_class.return_value = mock_manager

                with patch(
                    "tailsocks.cli._handle_start_server", return_value=True
                ) as mock_handler:
                    result = handle_command(args)

                    assert result == 0
                    assert args.profile == "selected_profile"
                    mock_manager_class.assert_called_once_with("selected_profile")
                    mock_handler.assert_called_once_with(mock_manager, args)

    def test_handle_command_with_verbose_flag(self, mocker):
        """Test handling commands with verbose flag set."""
        args = MagicMock()
        args.command = "start-server"
        args.verbose = True
        args.profile = "test_profile"

        with patch("tailsocks.cli.TailscaleProxyManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager

            with patch(
                "tailsocks.cli._handle_start_server", return_value=True
            ) as mock_handler:
                result = handle_command(args)

                assert result == 0
                mock_handler.assert_called_once_with(mock_manager, args)

    def test_handle_command_with_failed_profile_selection(self, mocker):
        """Test handling commands when profile selection fails."""
        args = MagicMock()
        args.command = "start-server"
        args.profile = None

        # Mock _require_profile_selection to return None (failure)
        with patch("tailsocks.cli._require_profile_selection", return_value=None):
            result = handle_command(args)

            assert result == 1

    def test_handle_command_start_server(self, mocker):
        """Test handling the start-server command."""
        args = MagicMock()
        args.command = "start-server"
        args.profile = "test_profile"

        with patch("tailsocks.cli.TailscaleProxyManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager

            with patch(
                "tailsocks.cli._handle_start_server", return_value=True
            ) as mock_handler:
                result = handle_command(args)

                assert result == 0
                mock_handler.assert_called_once_with(mock_manager, args)

    def test_handle_command_start_session(self, mocker):
        """Test handling the start-session command."""
        args = MagicMock()
        args.command = "start-session"
        args.profile = "test_profile"

        with patch("tailsocks.cli.TailscaleProxyManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager

            with patch(
                "tailsocks.cli._handle_start_session", return_value=True
            ) as mock_handler:
                result = handle_command(args)

                assert result == 0
                mock_handler.assert_called_once_with(mock_manager, args)

    def test_handle_command_stop_session(self, mocker):
        """Test handling the stop-session command."""
        args = MagicMock()
        args.command = "stop-session"
        args.profile = "test_profile"

        with patch("tailsocks.cli.TailscaleProxyManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager

            with patch(
                "tailsocks.cli._handle_stop_session", return_value=True
            ) as mock_handler:
                result = handle_command(args)

                assert result == 0
                mock_handler.assert_called_once_with(mock_manager)

    def test_handle_command_stop_server(self, mocker):
        """Test handling the stop-server command."""
        args = MagicMock()
        args.command = "stop-server"
        args.profile = "test_profile"

        with patch("tailsocks.cli.TailscaleProxyManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager

            with patch(
                "tailsocks.cli._handle_stop_server", return_value=True
            ) as mock_handler:
                result = handle_command(args)

                assert result == 0
                mock_handler.assert_called_once_with(mock_manager)

    def test_handle_command_delete_profile(self, mocker):
        """Test handling the delete-profile command."""
        args = MagicMock()
        args.command = "delete-profile"
        args.profile = "test_profile"

        with patch("tailsocks.cli.TailscaleProxyManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager

            with patch(
                "tailsocks.cli._handle_delete_profile", return_value=True
            ) as mock_handler:
                result = handle_command(args)

                assert result == 0
                mock_handler.assert_called_once_with(mock_manager)

    def test_handle_command_unknown(self, mocker):
        """Test handling an unknown command."""
        args = MagicMock()
        args.command = "unknown-command"
        args.profile = "test_profile"

        result = handle_command(args)

        assert result == 1


class TestMainFunction:
    def test_main_version(self, mocker, capsys):
        """Test main function with --version flag."""
        # Mock parse_args to return args with version=True
        args = MagicMock()
        args.version = True
        args.command = None
        mocker.patch("argparse.ArgumentParser.parse_args", return_value=args)

        # Mock __version__
        mocker.patch("tailsocks.__version__", "0.1.0")

        result = main()

        assert result == 0
        captured = capsys.readouterr()
        assert "tailsocks version 0.1.0" in captured.out

    def test_cli_verbose_mode(self, mocker):
        """Test CLI with verbose mode enabled."""
        # Mock parse_args to return args with verbose=True
        args = MagicMock()
        args.version = False
        args.command = "status"
        args.verbose = True
        mocker.patch("argparse.ArgumentParser.parse_args", return_value=args)

        # Mock handle_command
        mock_handle = mocker.patch("tailsocks.cli.handle_command", return_value=0)

        # Call main
        result = main()

        # Verify result and that handle_command was called with verbose args
        assert result == 0
        mock_handle.assert_called_once_with(args)
        assert args.verbose is True

    def test_main_no_command(self, mocker):
        """Test main function with no command."""
        # Mock parse_args to return args with no command
        args = MagicMock()
        args.version = False
        args.command = None
        mocker.patch("argparse.ArgumentParser.parse_args", return_value=args)

        with patch("argparse.ArgumentParser.print_help") as mock_help:
            result = main()

            assert result == 1
            mock_help.assert_called_once()

    def test_main_with_command(self, mocker):
        """Test main function with a command."""
        # Mock parse_args to return args with a command
        args = MagicMock()
        args.version = False
        args.command = "status"
        mocker.patch("argparse.ArgumentParser.parse_args", return_value=args)

        with patch("tailsocks.cli.handle_command", return_value=0) as mock_handle:
            result = main()

            assert result == 0
            mock_handle.assert_called_once_with(args)

    def test_main_with_invalid_command(self, mocker):
        """Test main function with an invalid command."""
        # Mock parse_args to return args with an invalid command
        args = MagicMock()
        args.version = False
        args.command = "invalid-command"
        args.profile = "test_profile"
        mocker.patch("argparse.ArgumentParser.parse_args", return_value=args)

        with patch("tailsocks.cli.handle_command", return_value=1) as mock_handle:
            result = main()

            assert result == 1
            mock_handle.assert_called_once_with(args)
