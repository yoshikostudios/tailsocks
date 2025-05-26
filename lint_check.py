#!/usr/bin/env python3
"""
Script to perform linting and formatting checks on the tailsocks project.
Uses ruff as specified in the project conventions.
"""

import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Run a command and print its output."""
    print(f"\n=== {description} ===")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.stdout:
        print(result.stdout)

    if result.stderr:
        print(f"Error: {result.stderr}", file=sys.stderr)

    return result.returncode == 0


def main():
    """Run linting and formatting checks."""
    # Ensure we're in the project root directory
    project_root = Path(__file__).parent
    os.chdir(project_root)

    print("Running linting and formatting checks...")

    # Check if ruff is installed
    try:
        subprocess.run(["ruff", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: ruff is not installed or not in PATH.")
        print("Install it with: pip install ruff")
        return False

    # Run ruff linting with auto-fix
    lint_success = run_command(["ruff", "check", "--fix", "."], "Ruff Linting Auto-fix")

    # Run ruff formatting (modifies files)
    format_success = run_command(["ruff", "format", "."], "Ruff Format Auto-fix")

    if lint_success and format_success:
        print("\n✅ All fixes applied successfully!")
        return True
    else:
        print("\n⚠️ Some issues could not be fixed automatically.")
        print("\nManual intervention may be required for remaining issues.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
