# tailsocks

A Tailscale SOCKS5 proxy manager for Linux and macOS.

## Description

`tailsocks` allows you to easily create and manage multiple Tailscale SOCKS5 proxies, each with its own profile. This is useful for routing traffic through different Tailscale networks or for testing purposes.

## Installation

### Using uv (recommended)

```bash
uv pip install tailsocks
```

### Using uvx

```bash
uvx tailsocks
```
This will install tailsocks if not already present and immediately execute it.

### Upgrading

To upgrade to the latest version:

```bash
uv pip install --upgrade tailsocks
```


After installation, you can run `tailsocks` directly from your terminal.

## Usage

### Starting a proxy server

```bash
tailsocks start-server
```

This will create a new profile with a random name and start a tailscaled process.

### Starting a proxy server with a specific bind address

```bash
tailsocks start-server --bind 127.0.0.1:1080
```

You can specify just the port to use the default localhost address:

```bash
tailsocks start-server --bind 1080
```

Or bind to all interfaces:

```bash
tailsocks start-server --bind 0.0.0.0:1080
```

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
tailsocks --profile profile_name start-server
tailsocks --profile profile_name start-session
```

### Checking status

```bash
tailsocks [--profile profile_name] status
```

### Stopping a session or server

```bash
tailsocks [--profile profile_name] stop-session
tailsocks [--profile profile_name] stop-server
```

### Deleting a profile

```bash
tailsocks --profile profile_name delete-profile
```

This will completely remove a profile's configuration and cache directories. The profile must be stopped first (using `stop-server`).

## Configuration

Each profile has its own configuration file located at `~/.config/tailscale-{profile_name}/config.yaml`.

Example configuration:

```yaml
tailscaled_path: /usr/sbin/tailscaled
tailscale_path: /usr/bin/tailscale
socket_path: /home/user/.cache/tailscale-{profile_name}/tailscaled.sock
accept_routes: true
accept_dns: true
bind: localhost:1080  # Format: address:port
tailscaled_args:
  - --verbose=1
tailscale_up_args:
  - --hostname={profile_name}-proxy
```

## Development

To run the tool in development mode:

1. Clone the repository:
   ```bash
   git clone https://github.com/yoshikostudios/tailsocks.git
   cd tailsocks
   ```

2. Create a virtual environment using uv:
   ```bash
   uv venv
   source .venv/bin/activate
   ```

3. Install in development mode with test dependencies:
   ```bash
   uv pip install -e ".[test,dev]"
   ```

4. Run tests:
   ```bash
   pytest
   ```

5. Format and lint code:
   ```bash
   ruff format .
   ruff check .
   ```

6. Run the tool:
   ```bash
   python -m tailsocks
   ```

## Requirements

- Python 3.9+
- Tailscale installed on your system
- Linux

## Future Plans

 - macOS (close, but not extensively tested)
 - integrate with systemd on linux/macos
 - full windows support 

## License

MIT License - Copyright (c) 2025 Yoshiko Studios LLC
