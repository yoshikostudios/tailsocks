#!/usr/bin/env python3
"""
Command-line interface for tailsocks.
"""

import argparse
import sys

from tailsocks.manager import TailscaleProxyManager, get_all_profiles


def _print_status(status, show_header=True):
    """Print the status of a profile in a consistent format"""
    if show_header:
        print(f"Profile: {status['profile_name']}")

    # Define the fields to display and their labels
    fields = [
        ("server_running", "Server running", lambda v: "Yes" if v else "No"),
        ("session_up", "Session up", lambda v: "Yes" if v else "No"),
        ("bind", "Bind address", str),
        ("ip_address", "IP address", str),
        ("config_dir", "Config directory", str),
        ("cache_dir", "Cache directory", str),
        ("last_started", "Last started", str),
        ("using_auth_token", "Using auth token", lambda v: "Yes" if v else "No"),
    ]

    # Print each field if it exists in the status
    for key, label, formatter in fields:
        if key in status:
            print(f"  {label}: {formatter(status[key])}")


def show_status(args):
    """Show status of all profiles or a specific profile"""
    if args.profile:
        manager = TailscaleProxyManager(args.profile)
        status = manager.get_status()
        _print_status(status)
    else:
        profiles = get_all_profiles()
        if not profiles:
            print("No profiles found")
            return

        print(f"Found {len(profiles)} profile(s):")
        for status in profiles:
            _print_status(status)
            print()


def _require_profile_selection(args, command_name):
    """
    Require profile selection for commands when multiple profiles exist.
    Returns the profile name if valid, None otherwise.
    """
    if args.profile:
        return args.profile

    # Get all existing profiles
    profiles = get_all_profiles()

    if not profiles:
        print(
            "Error: No profiles exist. Please create a profile first with 'start-server' command."
        )
        return None

    if len(profiles) == 1:
        # Use the only existing profile
        profile_name = profiles[0]["profile_name"]
        print(f"Using the only existing profile: {profile_name}")
        return profile_name
    else:
        print(
            f"Error: Multiple profiles exist. Please specify a profile with --profile for the '{command_name}' command."
        )
        print("Available profiles:")
        for profile in profiles:
            print(f"  {profile['profile_name']}")
        return None


def _handle_start_server(manager, args):
    """Handle the start-server command."""
    # If bind is specified, update the manager's runtime state
    if hasattr(args, "bind") and args.bind:
        # Update the config with the bind address
        manager.update_bind_address(args.bind)

    return manager.start_server()


def _handle_start_session(manager, args):
    """Handle the start-session command."""
    # Check if the server is running before starting a session
    if not manager._is_server_running():
        print(f"Error: Tailscaled is not running for profile '{manager.profile_name}'.")
        print("Please start the server first with 'start-server' command.")
        return False

    # Pass auth token from command line if provided
    auth_token = None
    if hasattr(args, "auth_token") and args.auth_token:
        auth_token = args.auth_token

    return manager.start_session(auth_token)


def _handle_stop_session(manager):
    """Handle the stop-session command."""
    # Check if there's anything to stop
    if not manager._is_server_running():
        print(
            f"Error: No tailscale services are running for profile '{manager.profile_name}'."
        )
        return False
    return manager.stop_session()


def _handle_stop_server(manager):
    """Handle the stop-server command."""
    return manager.stop_server()


def _handle_delete_profile(manager):
    """Handle the delete-profile command."""
    # Check if the server is running
    if manager._is_server_running():
        print(
            f"Error: Cannot delete profile '{manager.profile_name}' while it's running."
        )
        print("Please stop the server first with 'stop-server' command.")
        return False

    # Delete the profile
    import os
    import shutil

    config_dir = manager.config_dir
    cache_dir = manager.cache_dir

    # Confirm both directories exist and are within the expected parent directories
    if (
        os.path.exists(config_dir)
        and os.path.exists(cache_dir)
        and "/.config/tailscale-" in config_dir
        and "/.cache/tailscale-" in cache_dir
    ):
        try:
            # Remove the directories
            shutil.rmtree(config_dir, ignore_errors=True)
            shutil.rmtree(cache_dir, ignore_errors=True)
            print(f"Profile '{manager.profile_name}' has been deleted.")
            return True
        except Exception as e:
            print(f"Error deleting profile: {str(e)}")
            return False
    else:
        print(
            f"Error: Could not locate profile directories for '{manager.profile_name}'."
        )
        return False


def handle_command(args):
    """Handle the command specified in the arguments."""
    if args.command == "status":
        show_status(args)
        return 0

    # Handle profile selection for all commands except status
    if args.command in [
        "start-server",
        "start-session",
        "stop-session",
        "stop-server",
        "delete-profile",
    ]:
        profile_name = _require_profile_selection(args, args.command)
        if not profile_name:
            return 1
        args.profile = profile_name

    manager = TailscaleProxyManager(args.profile)

    # Dispatch to the appropriate command handler
    if args.command == "start-server":
        success = _handle_start_server(manager, args)
    elif args.command == "start-session":
        success = _handle_start_session(manager, args)
    elif args.command == "stop-session":
        success = _handle_stop_session(manager)
    elif args.command == "stop-server":
        success = _handle_stop_server(manager)
    elif args.command == "delete-profile":
        success = _handle_delete_profile(manager)
    else:
        return 1

    return 0 if success else 1


def main():
    """Main entry point for the CLI"""
    parser = argparse.ArgumentParser(description="Manage a tailscale SOCKS5 proxy")
    parser.add_argument(
        "--profile",
        "-p",
        help="Profile name (random name will be generated if not provided)",
    )
    parser.add_argument(
        "--version", "-v", action="store_true", help="Show version information"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Start server command
    start_server_parser = subparsers.add_parser(
        "start-server", help="Start the tailscaled process"
    )
    start_server_parser.add_argument(
        "--bind", help="Bind address and port (format: address:port or just port)"
    )

    # Start session command
    start_session_parser = subparsers.add_parser(
        "start-session", help="Start a tailscale session"
    )
    start_session_parser.add_argument(
        "--auth-token", help="Tailscale authentication token"
    )

    # Stop session command
    subparsers.add_parser("stop-session", help="Stop the tailscale session")

    # Stop server command
    subparsers.add_parser("stop-server", help="Stop the tailscaled process")

    # Delete profile command
    subparsers.add_parser("delete-profile", help="Delete a profile completely")

    # Status command
    subparsers.add_parser("status", help="Show status of profiles")

    args = parser.parse_args()

    if args.version:
        from tailsocks import __version__

        print(f"tailsocks version {__version__}")
        return 0

    if not args.command:
        parser.print_help()
        return 1

    return handle_command(args)


if __name__ == "__main__":
    sys.exit(main())
