#!/usr/bin/env python3
"""
Run tests with coverage reporting for the tailsocks project.
"""

import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Run a command and print its output."""
    print(f"\n=== {description} ===")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    print(result.stdout)
    if result.stderr:
        print(f"STDERR:\n{result.stderr}", file=sys.stderr)

    if result.returncode != 0:
        print(f"Command failed with exit code {result.returncode}", file=sys.stderr)
        return False
    return True


def main():
    """Run tests with coverage and generate reports."""
    # Create directory for coverage reports if it doesn't exist
    reports_dir = Path("coverage_reports")
    reports_dir.mkdir(exist_ok=True)

    # Run tests with coverage
    cmd = (
        "python -m pytest tests/ "
        "--cov=tailsocks "
        "--cov-report=term "
        f"--cov-report=html:{reports_dir}/html "
        f"--cov-report=xml:{reports_dir}/coverage.xml "
        "-v"
    )

    success = run_command(cmd, "Running tests with coverage")

    if success:
        print(f"\nCoverage report generated in {reports_dir}/html/index.html")

        # Check if we're on CI and should fail on coverage threshold
        min_coverage = os.environ.get("MIN_COVERAGE", 80)
        coverage_output = subprocess.check_output(
            "python -m coverage report", shell=True, text=True
        )

        # Extract total coverage percentage
        for line in coverage_output.splitlines():
            if "TOTAL" in line:
                total_coverage = int(line.split()[-1].rstrip("%"))
                if total_coverage < int(min_coverage):
                    print(
                        f"Coverage {total_coverage}% is below minimum threshold of {min_coverage}%",
                        file=sys.stderr,
                    )
                    return 1
                break

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
