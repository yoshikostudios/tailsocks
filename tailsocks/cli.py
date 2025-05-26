#!/usr/bin/env python3
"""
Command-line interface for tailsocks.
"""

import argparse
import sys
from tailsocks.manager import TailscaleProxyManager, get_all_profiles


def show_status(args):
    """Show status of all profiles or a specific profile"""
    if args.profile:
        manager = TailscaleProxyManager(args.profile)
        status = manager.get_status()
        print(f"Profile: {status['profile_name']}")
        print(f"  Server running: {'Yes' if status['server_running'] else 'No'}")
        print(f"  Session up: {'Yes' if status['session_up'] else 'No'}")
        print(f"  Bind address: {status['bind']}")
        print(f"  IP address: {status['ip_address']}")
        print(f"  Config directory: {status['config_dir']}")
        print(f"  Cache directory: {status['cache_dir']}")
    else:
        profiles = get_all_profiles()
        if not profiles:
            print("No profiles found")
            return
        
        print(f"Found {len(profiles)} profile(s):")
        for status in profiles:
            print(f"Profile: {status['profile_name']}")
            print(f"  Server running: {'Yes' if status['server_running'] else 'No'}")
            print(f"  Session up: {'Yes' if status['session_up'] else 'No'}")
            print(f"  SOCKS5 port: {status['socks5_port']}")
            print(f"  IP address: {status['ip_address']}")
            print(f"  Config directory: {status['config_dir']}")
            print(f"  Cache directory: {status['cache_dir']}")
            print()


def main():
    """Main entry point for the CLI"""
    parser = argparse.ArgumentParser(description='Manage a tailscale SOCKS5 proxy')
    parser.add_argument('--profile', '-p', help='Profile name (random name will be generated if not provided)')
    parser.add_argument('--version', '-v', action='store_true', help='Show version information')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Start server command
    start_server_parser = subparsers.add_parser('start-server', help='Start the tailscaled process')
    start_server_parser.add_argument('--bind', help='Bind address and port (format: address:port or just port)')
    
    # Start session command
    start_session_parser = subparsers.add_parser('start-session', help='Start a tailscale session')
    start_session_parser.add_argument('--auth-token', help='Tailscale authentication token')
    
    # Stop session command
    subparsers.add_parser('stop-session', help='Stop the tailscale session')
    
    # Stop server command
    subparsers.add_parser('stop-server', help='Stop the tailscaled process')
    
    # Status command
    subparsers.add_parser('status', help='Show status of profiles')
    
    args = parser.parse_args()
    
    if args.version:
        from tailsocks import __version__
        print(f"tailsocks version {__version__}")
        return 0
    
    if not args.command:
        parser.print_help()
        return 1
    
    if args.command == 'status':
        show_status(args)
        return 0
    
    # Handle profile selection for session commands
    if args.command in ['start-session', 'stop-session']:
        if not args.profile:
            # Get all existing profiles
            profiles = get_all_profiles()
            
            if not profiles:
                print(f"Error: No profiles exist. Please create a profile first with 'start-server' command.")
                return 1
            
            if len(profiles) == 1:
                # Use the only existing profile
                args.profile = profiles[0]['profile_name']
                print(f"Using the only existing profile: {args.profile}")
            else:
                print("Error: Multiple profiles exist. Please specify a profile with --profile.")
                print("Available profiles:")
                for profile in profiles:
                    print(f"  {profile['profile_name']}")
                return 1
    
    manager = TailscaleProxyManager(args.profile)
    
    if args.command == 'start-server':
        # If bind is specified, update the manager's config
        if hasattr(args, 'bind') and args.bind:
            bind_address, port = manager._parse_bind_address(args.bind)
            manager.bind_address = bind_address
            manager.port = port
        success = manager.start_server()
    elif args.command == 'start-session':
        # Check if the server is running before starting a session
        if not manager._is_server_running():
            print(f"Error: Tailscaled is not running for profile '{manager.profile_name}'.")
            print("Please start the server first with 'start-server' command.")
            return 1
        
        # Pass auth token from command line if provided
        auth_token = None
        if hasattr(args, 'auth_token') and args.auth_token:
            auth_token = args.auth_token
        
        success = manager.start_session(auth_token)
    elif args.command == 'stop-session':
        # Check if there's anything to stop
        if not manager._is_server_running():
            print(f"Error: No tailscale services are running for profile '{manager.profile_name}'.")
            return 1
        success = manager.stop_session()
    elif args.command == 'stop-server':
        success = manager.stop_server()
    else:
        parser.print_help()
        return 1
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
