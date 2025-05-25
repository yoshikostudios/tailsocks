#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
import yaml
import signal
import time
import tempfile
import shutil
import random
import glob
from pathlib import Path


class TailscaleProxyManager:
    def __init__(self, profile_name=None):
        self.profile_name = profile_name or self._generate_random_profile_name()
        self.config_dir = os.path.expanduser(f"~/.config/tailscale-{self.profile_name}")
        self.cache_dir = os.path.expanduser(f"~/.cache/tailscale-{self.profile_name}")
        self.config_path = os.path.join(self.config_dir, "config.yaml")
        
        # Ensure both directories exist
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Create or load config
        if not os.path.exists(self.config_path):
            self._create_default_config()
        
        self.config = self._load_config()
        self.tailscaled_process = None
        
        # Set default values if not in config
        self.state_dir = self.cache_dir
        self.socket_path = self.config.get('socket_path', os.path.join(self.state_dir, 'tailscaled.sock'))
        self.port = self.config.get('socks5_port', 1080)
        self.tailscaled_path = self.config.get('tailscaled_path', '/usr/sbin/tailscaled')
        self.tailscale_path = self.config.get('tailscale_path', '/usr/bin/tailscale')
        
        # Get auth token from config or environment
        self.auth_token = self.config.get('auth_token', os.environ.get('TAILSCALE_AUTH_TOKEN', ''))

    def _generate_random_profile_name(self):
        """Generate a friendly random profile name"""
        adjectives = ["happy", "sunny", "clever", "brave", "mighty", "gentle", "wise", "calm", "swift", "bright"]
        animals = ["gorilla", "dolphin", "tiger", "eagle", "panda", "koala", "wolf", "fox", "rabbit", "turtle"]
        
        return f"{random.choice(adjectives)}_{random.choice(animals)}"

    def _create_default_config(self):
        """Create a default configuration file"""
        default_config = {
            'tailscaled_path': '/usr/sbin/tailscaled',
            'tailscale_path': '/usr/bin/tailscale',
            'socket_path': os.path.join(self.cache_dir, 'tailscaled.sock'),
            'socks5_port': 1080,
            'accept_routes': True,
            'accept_dns': True,
            'tailscaled_args': ['--verbose=1'],
            'tailscale_up_args': [f'--hostname={self.profile_name}-proxy']
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False)
        
        print(f"Created default configuration at {self.config_path}")

    def _load_config(self):
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            print(f"Config file not found: {self.config_path}")
            return {}
        except yaml.YAMLError as e:
            print(f"Error parsing config file: {e}")
            return {}

    def start_server(self):
        """Start the tailscaled process with custom state directory and socket"""
        if self._is_server_running():
            print("Tailscaled is already running")
            return True
        
        cmd = [
            self.tailscaled_path,
            '--state', self.state_dir,
            '--socket', self.socket_path,
            '--port', str(self.port),
            '--socks5-server', f'localhost:{self.port}'
        ]
        
        # Add any additional tailscaled args from config
        if 'tailscaled_args' in self.config:
            cmd.extend(self.config['tailscaled_args'])
        
        print(f"Starting tailscaled with command: {' '.join(cmd)}")
        
        # Start tailscaled as a background process
        self.tailscaled_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait a moment for the process to start
        time.sleep(2)
        
        if self.tailscaled_process.poll() is not None:
            stdout, stderr = self.tailscaled_process.communicate()
            print(f"Failed to start tailscaled: {stderr}")
            return False
        
        print(f"Tailscaled started with PID {self.tailscaled_process.pid}")
        print(f"SOCKS5 proxy will be available at localhost:{self.port}")
        return True

    def start_session(self):
        """Start a tailscale session, authenticate, and bring up the network"""
        if not self._is_server_running():
            print("Tailscaled is not running. Please start the server first.")
            return False
        
        # Build the up command
        cmd = [
            self.tailscale_path,
            '--socket', self.socket_path,
            'up'
        ]
        
        # Add accept routes and other options from config
        if self.config.get('accept_routes', True):
            cmd.append('--accept-routes')
        
        if self.config.get('accept_dns', True):
            cmd.append('--accept-dns')
            
        # Add any additional tailscale up args from config
        if 'tailscale_up_args' in self.config:
            cmd.extend(self.config['tailscale_up_args'])
            
        # Add auth token if available
        if self.auth_token:
            cmd.extend(['--authkey', self.auth_token])
        
        print(f"Starting tailscale session with command: {' '.join(cmd)}")
        
        # Run the tailscale up command
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if process.returncode != 0:
            print(f"Failed to start tailscale session: {process.stderr}")
            return False
        
        # If we didn't use an auth token, the output will contain a login URL
        if not self.auth_token and "To authenticate, visit:" in process.stdout:
            print(process.stdout)
        else:
            print("Tailscale session started successfully")
            
        return True

    def stop_session(self):
        """Stop the tailscale session"""
        if not self._is_server_running():
            print("Tailscaled is not running")
            return False
        
        cmd = [
            self.tailscale_path,
            '--socket', self.socket_path,
            'down'
        ]
        
        print(f"Stopping tailscale session with command: {' '.join(cmd)}")
        
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if process.returncode != 0:
            print(f"Failed to stop tailscale session: {process.stderr}")
            return False
        
        print("Tailscale session stopped successfully")
        return True
    
    def stop_server(self):
        """Stop the tailscaled process"""
        if not self._is_server_running():
            print("Tailscaled is not running")
            return True
        
        # Try to find the process ID using the socket file
        pid = self._find_tailscaled_pid()
        
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"Sent SIGTERM to tailscaled process {pid}")
                
                # Wait for process to terminate
                for _ in range(5):
                    if not self._is_server_running():
                        print("Tailscaled stopped successfully")
                        return True
                    time.sleep(1)
                
                # Force kill if still running
                os.kill(pid, signal.SIGKILL)
                print(f"Sent SIGKILL to tailscaled process {pid}")
                return True
            except ProcessLookupError:
                print(f"Process {pid} not found")
            except PermissionError:
                print(f"Permission denied when trying to kill process {pid}")
        
        print("Could not find or stop tailscaled process")
        return False
    
    def get_status(self):
        """Get the status of this profile"""
        server_running = self._is_server_running()
        session_up = False
        ip_address = "N/A"
        
        if server_running:
            # Check if the session is up
            cmd = [
                self.tailscale_path,
                '--socket', self.socket_path,
                'status',
                '--json'
            ]
            
            try:
                process = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=2
                )
                
                if process.returncode == 0:
                    import json
                    status_data = json.loads(process.stdout)
                    session_up = status_data.get('BackendState', '') == 'Running'
                    
                    # Try to get the IP address
                    if 'Self' in status_data and 'TailscaleIPs' in status_data['Self'] and status_data['Self']['TailscaleIPs']:
                        ip_address = status_data['Self']['TailscaleIPs'][0]
            except Exception as e:
                print(f"Error getting session status: {e}")
        
        return {
            'profile_name': self.profile_name,
            'server_running': server_running,
            'session_up': session_up,
            'socks5_port': self.port,
            'ip_address': ip_address,
            'config_dir': self.config_dir,
            'cache_dir': self.cache_dir
        }
    
    def _is_server_running(self):
        """Check if tailscaled is running by checking the socket file"""
        if not os.path.exists(self.socket_path):
            return False
        
        # Try to use the socket to check status
        cmd = [
            self.tailscale_path,
            '--socket', self.socket_path,
            'status'
        ]
        
        try:
            process = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2
            )
            return process.returncode == 0
        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
            return False
    
    def _find_tailscaled_pid(self):
        """Try to find the PID of the tailscaled process"""
        try:
            cmd = ['pgrep', '-f', f'tailscaled.*{self.socket_path}']
            result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip())
        except (subprocess.SubprocessError, ValueError):
            pass
        return None


def get_all_profiles():
    """Get a list of all existing profiles"""
    # Look in both config and cache directories
    config_dirs = glob.glob(os.path.expanduser("~/.config/tailscale-*"))
    cache_dirs = glob.glob(os.path.expanduser("~/.cache/tailscale-*"))
    
    # Extract profile names from directory paths
    config_profiles = [os.path.basename(d).replace('tailscale-', '') for d in config_dirs]
    cache_profiles = [os.path.basename(d).replace('tailscale-', '') for d in cache_dirs]
    
    # Combine and deduplicate profile names
    profile_names = list(set(config_profiles + cache_profiles))
    profiles = []
    
    for profile_name in profile_names:
        manager = TailscaleProxyManager(profile_name)
        profiles.append(manager.get_status())
    
    return profiles


def show_status(args):
    """Show status of all profiles or a specific profile"""
    if args.profile:
        manager = TailscaleProxyManager(args.profile)
        status = manager.get_status()
        print(f"Profile: {status['profile_name']}")
        print(f"  Server running: {'Yes' if status['server_running'] else 'No'}")
        print(f"  Session up: {'Yes' if status['session_up'] else 'No'}")
        print(f"  SOCKS5 port: {status['socks5_port']}")
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
    parser = argparse.ArgumentParser(description='Manage a tailscale SOCKS5 proxy')
    parser.add_argument('--profile', '-p', help='Profile name (random name will be generated if not provided)')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Start server command
    start_server_parser = subparsers.add_parser('start-server', help='Start the tailscaled process')
    
    # Start session command
    start_session_parser = subparsers.add_parser('start-session', help='Start a tailscale session')
    
    # Stop session command
    stop_session_parser = subparsers.add_parser('stop-session', help='Stop the tailscale session')
    
    # Stop server command
    stop_server_parser = subparsers.add_parser('stop-server', help='Stop the tailscaled process')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show status of profiles')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    if args.command == 'status':
        show_status(args)
        return 0
    
    manager = TailscaleProxyManager(args.profile)
    
    if args.command == 'start-server':
        success = manager.start_server()
    elif args.command == 'start-session':
        success = manager.start_session()
    elif args.command == 'stop-session':
        success = manager.stop_session()
    elif args.command == 'stop-server':
        success = manager.stop_server()
    else:
        parser.print_help()
        return 1
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
