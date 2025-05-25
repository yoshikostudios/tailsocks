# tailsocks

A Tailscale SOCKS5 proxy manager for Linux, macOS, and WSL.

## Description

`tailsocks` allows you to easily create and manage multiple Tailscale SOCKS5 proxies, each with its own profile. This is useful for routing traffic through different Tailscale networks or for testing purposes.

## Installation

### Using pipx (recommended)

```bash
pipx install tailsocks
```

### Using pip

```bash
pip install tailsocks
```

### Using uv

```bash
uv pip install tailsocks
```

## Usage

### Starting a proxy server

```bash
tailsocks start-server
```

This will create a new profile with a random name and start a tailscaled process.

### Starting a Tailscale session

```bash
tailsocks start-session
```

This will authenticate with Tailscale and bring up the network connection.

You can provide an auth token:

```bash
tailsocks start-session --auth-token tskey-auth-xxx
```

Or set it via environment variable:

```bash
export TAILSCALE_AUTH_TOKEN=tskey-auth-xxx
tailsocks start-session
```

### Using a specific profile

```bash
tailsocks --profile my_profile start-server
tailsocks --profile my_profile start-session
```

### Checking status

```bash
tailsocks status
```

### Stopping a session or server

```bash
tailsocks stop-session
tailsocks stop-server
```

## Configuration

Each profile has its own configuration file located at `~/.config/tailscale-{profile_name}/config.yaml`.

Example configuration:

```yaml
tailscaled_path: /usr/sbin/tailscaled
tailscale_path: /usr/bin/tailscale
socket_path: /home/user/.cache/tailscale-my_profile/tailscaled.sock
accept_routes: true
accept_dns: true
socks5_port: 1080
socks5_interface: localhost
tailscaled_args:
  - --verbose=1
tailscale_up_args:
  - --hostname=my_profile-proxy
```

## Development

To run the tool in development mode:

1. Clone the repository:
   ```bash
   git clone https://github.com/yoshikostudios/tailsocks.git
   cd tailsocks
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install in development mode:
   ```bash
   pip install -e .
   ```

4. Run the tool:
   ```bash
   python -m tailsocks
   ```

## Requirements

- Python 3.7+
- Tailscale installed on your system
- Linux, macOS, or Windows with WSL

## License

MIT License - Copyright (c) 2025 Yoshiko Studios
