# Contributing to Tailsocks

Thank you for considering contributing to Tailsocks! This document provides guidelines and instructions for contributing.

## Code of Conduct

Please be respectful and considerate of others when contributing to this project.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/your-username/tailsocks.git`
3. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
4. Install development dependencies:
   ```
   uv pip install -r requirements.txt
   uv pip install -e .
   ```

## Development Process

1. Create a new branch for your feature or bugfix: `git checkout -b feature-name`
2. Make your changes
3. Run tests to ensure your changes don't break existing functionality: `pytest`
4. Format and lint your code: `ruff check . --fix && ruff format .`
5. Update documentation as needed
6. Commit your changes with a descriptive commit message
7. Push to your fork: `git push origin feature-name`
8. Create a pull request

## Code Style

- Follow PEP 8 style guidelines
- Use Ruff for code formatting and linting
- Run `ruff format .` to format your code
- Run `ruff check .` to lint your code
- Use meaningful variable and function names
- Add docstrings to all functions, classes, and modules
- Keep functions focused on a single responsibility

## Testing

- Write tests for all new functionality
- Ensure all tests pass before submitting a pull request
- Run tests with `pytest`

## Versioning

This project follows [Semantic Versioning](https://semver.org/):
- MAJOR version for incompatible API changes
- MINOR version for backwards-compatible functionality
- PATCH version for backwards-compatible bug fixes

## Submitting Changes

1. Push your changes to your fork
2. Submit a pull request to the main repository
3. Describe your changes in detail
4. Reference any related issues

## Reporting Bugs

When reporting bugs, please include:
- A clear description of the issue
- Steps to reproduce the problem
- Expected behavior
- Actual behavior
- Your operating system and Python version
- Any relevant logs or error messages

## Feature Requests

Feature requests are welcome! Please provide:
- A clear description of the feature
- The motivation for adding this feature
- Any relevant examples or use cases
