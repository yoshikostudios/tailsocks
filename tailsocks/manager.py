#!/usr/bin/env python3
"""
Core functionality for managing Tailscale SOCKS5 proxies.
"""

import os
import subprocess
import sys
import yaml
import signal
import time
import random
import glob
import json
import socket
import platform
from pathlib import Path


class TailscaleProxyManager:
    """Manages a Tailscale SOCKS5 proxy instance with its own profile."""
    
    def __init__(self, profile_name=None):
        """Initialize a new Tailscale proxy manager with the given profile name."""
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
        
        # Parse bind address and port
        bind_config = self.config.get('bind', 'localhost:1080')
        self.bind_address, self.port = self._parse_bind_address(bind_config)
        
        # Set paths based on OS
        system = platform.system()
        if system == 'Darwin':  # macOS
            default_tailscaled = '/usr/local/bin/tailscaled'
            default_tailscale = '/usr/local/bin/tailscale'
        elif system == 'Linux':
            default_tailscaled = '/usr/sbin/tailscaled'
            default_tailscale = '/usr/bin/tailscale'
        else:  # Windows or other
            default_tailscaled = 'tailscaled'
            default_tailscale = 'tailscale'
            
        self.tailscaled_path = self.config.get('tailscaled_path', default_tailscaled)
        self.tailscale_path = self.config.get('tailscale_path', default_tailscale)
        
        # Get auth token from config or environment
        self.auth_token = self.config.get('auth_token', os.environ.get('TAILSCALE_AUTH_TOKEN', ''))

    def _generate_random_profile_name(self):
        """Generate a friendly random profile name that's not already in use"""
        adjectives = ["happy", "sunny", "clever", "brave", "mighty", "gentle", "wise", "calm", "swift", "bright"]
        animals = ["gorilla", "dolphin", "tiger", "eagle", "panda", "koala", "wolf", "fox", "rabbit", "turtle"]
        
        # Get existing profile names
        config_dirs = glob.glob(os.path.expanduser("~/.config/tailscale-*"))
        cache_dirs = glob.glob(os.path.expanduser("~/.cache/tailscale-*"))
        existing_profiles = set([os.path.basename(d).replace('tailscale-', '') for d in config_dirs + cache_dirs])
        
        # Try to generate a unique name (max 10 attempts)
        for _ in range(10):
            name = f"{random.choice(adjectives)}_{random.choice(animals)}"
            if name not in existing_profiles:
                return name
        
        # If we couldn't find a unique name, add a random number
        while True:
            name = f"{random.choice(adjectives)}_{random.choice(animals)}_{random.randint(1, 999)}"
            if name not in existing_profiles:
                return name

    def _parse_bind_address(self, bind_string):
        """Parse a bind string in the format 'address:port' or just 'port'"""
        if ':' in bind_string:
            address, port_str = bind_string.rsplit(':', 1)
            try:
                return address, int(port_str)
            except ValueError:
                print(f"Invalid port in bind address: {bind_string}, using default 1080")
                return address, 1080
        else:
            # If only a port is provided
            try:
                return 'localhost', int(bind_string)
            except ValueError:
                print(f"Invalid port: {bind_string}, using default 1080")
                return 'localhost', 1080

    def _create_default_config(self):
        """Create a default configuration file"""
        system = platform.system()
        if system == 'Darwin':  # macOS
            default_tailscaled = '/usr/local/bin/tailscaled'
            default_tailscale = '/usr/local/bin/tailscale'
        elif system == 'Linux':
            default_tailscaled = '/usr/sbin/tailscaled'
            default_tailscale = '/usr/bin/tailscale'
        else:  # Windows or other
            default_tailscaled = 'tailscaled'
            default_tailscale = 'tailscale'
            
        default_config = {
            'tailscaled_path': default_tailscaled,
            'tailscale_path': default_tailscale,
            'socket_path': os.path.join(self.cache_dir, 'tailscaled.sock'),
            'accept_routes': True,
            'accept_dns': True,
            'bind': 'localhost:1080',
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
        
        # Check port availability only when starting the server
        if 'bind' in self.config:
            # If bind is explicitly configured, verify the port is available
            if self._is_port_in_use(self.port):
                print(f"Error: Configured port {self.port} in bind address {self.bind_address}:{self.port} is already in use.")
                print("Please modify your config.yaml to use a different port.")
                return False
        else:
            # If bind is not configured, start with default and find an available port
            while self._is_port_in_use(self.port):
                print(f"Port {self.port} is already in use, trying port {self.port + 1}")
                self.port += 1
            print(f"Using bind address: {self.bind_address}:{self.port}")
        
        # Create a state file path instead of just using the directory
        state_file = os.path.join(self.state_dir, "tailscale.state")
        
        cmd = [
            self.tailscaled_path,
            '--state', state_file,  # Use the state file path instead of just the directory
            '--socket', self.socket_path,
            '--socks5-server', f'{self.bind_address}:{self.port}',
            '--tun=userspace-networking'
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
        print(f"SOCKS5 proxy will be available at {self.bind_address}:{self.port}")
        return True

    def start_session(self, auth_token=None):
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
            
        # Add auth token with precedence: command line > environment > config
        token_to_use = auth_token or self.auth_token
        if token_to_use:
            cmd.extend(['--authkey', token_to_use])
        
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
        if not token_to_use and "To authenticate, visit:" in process.stdout:
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
            'bind': f'{self.bind_address}:{self.port}',
            'ip_address': ip_address,
            'config_dir': self.config_dir,
            'cache_dir': self.cache_dir
        }
    
    def _is_server_running(self):
        """Check if tailscaled is running by checking the socket file and process existence"""
        # First check if the socket file exists
        if not os.path.exists(self.socket_path):
            return False
        
        # Try to find the process ID
        pid = self._find_tailscaled_pid()
        if pid:
            # If we found a PID, the server is running
            return True
        
        # As a fallback, try to use the socket to check status
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
                timeout=5  # Increase timeout from 2 to 5 seconds
            )
            return process.returncode == 0
        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
            # If the socket check fails, check if we can find the process by looking for the command line
            try:
                # Look for a process with our socket path in its command line
                system = platform.system()
                if system in ['Linux', 'Darwin']:  # Linux or macOS
                    cmd = ['pgrep', '-f', f'tailscaled.*{self.socket_path}']
                    result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
                    return result.returncode == 0 and bool(result.stdout.strip())
            except subprocess.SubprocessError:
                pass
            
            return False
    
    def _is_port_in_use(self, port):
        """Check if the given port is already in use"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0
            
    def _find_tailscaled_pid(self):
        """Try to find the PID of the tailscaled process"""
        system = platform.system()
        
        if system in ['Linux', 'Darwin']:  # Linux or macOS
            try:
                cmd = ['pgrep', '-f', f'tailscaled.*{self.socket_path}']
                result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    return int(result.stdout.strip())
            except (subprocess.SubprocessError, ValueError):
                pass
        else:  # Windows or other
            # This is a simplified approach for Windows
            try:
                cmd = ['tasklist', '/FI', f'IMAGENAME eq tailscaled.exe', '/FO', 'CSV']
                result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
                if 'tailscaled.exe' in result.stdout:
                    # This doesn't actually get the right PID for the specific socket
                    # A more sophisticated approach would be needed for Windows
                    pass
            except subprocess.SubprocessError:
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
