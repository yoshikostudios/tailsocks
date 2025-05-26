# Deployment Guide for tailsocks

This document provides instructions for building, testing, and deploying the tailsocks package to PyPI repositories.

## Prerequisites

- Python 3.7 or higher
- pip and build tools
- A PyPI account (for manual deployment)
- GitHub account with write access to the repository (for GitHub Actions deployment)

## Manual Deployment Process

### 1. Prepare Your Environment

```bash
# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install build tools
pip install --upgrade pip
pip install build twine
```

### 2. Update Version Number

Before deployment, ensure the version number in `tailsocks/__init__.py` is updated according to [Semantic Versioning](https://semver.org/).

### 3. Build the Package

```bash
# Clean previous builds
rm -rf build/ dist/ *.egg-info/

# Build the package
python -m build
```

This creates both source distribution (.tar.gz) and wheel (.whl) files in the `dist/` directory.

### 4. Test the Build

```bash
# Verify the package structure
twine check dist/*
```

### 5. Test Upload to TestPyPI

```bash
# Upload to TestPyPI
twine upload --repository-url https://test.pypi.org/legacy/ dist/*

# Test installation from TestPyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ tailsocks
```

### 6. Deploy to Production PyPI

Once you've verified the package works correctly from TestPyPI:

```bash
# Upload to PyPI
twine upload dist/*
```

## GitHub Actions Deployment

This project uses GitHub Actions for automated testing and deployment.

### Setting Up GitHub Actions

1. **Configure Secrets**:
   - Go to your GitHub repository
   - Navigate to Settings > Secrets and variables > Actions
   - Add the following secrets:
     - `PYPI_API_TOKEN`: Your PyPI API token
     - `TEST_PYPI_API_TOKEN`: Your TestPyPI API token

2. **Workflow Files**:
   - `.github/workflows/ci.yml`: Runs tests on every push and pull request
   - `.github/workflows/publish.yml`: Publishes the package when a release is created

### Triggering a Deployment

1. **Create a New Release**:
   - Go to your GitHub repository
   - Navigate to Releases > Draft a new release
   - Create a new tag matching your version (e.g., `v0.1.0`)
   - Add release notes
   - Publish the release

2. **Monitor the Workflow**:
   - Go to the Actions tab in your repository
   - You should see the publish workflow running
   - Once completed, your package will be available on PyPI

### Troubleshooting GitHub Actions

- Check the workflow logs in the Actions tab
- Ensure your API tokens are correctly set up
- Verify that your version number is unique and follows semantic versioning

## Version Management

- Follow [Semantic Versioning](https://semver.org/)
- Update the version in `tailsocks/__init__.py`
- Ensure the version matches the GitHub release tag

## Post-Deployment Verification

After deployment, verify the package can be installed and used:

```bash
# Install the package
pip install --upgrade tailsocks

# Verify the installation
python -c "import tailsocks; print(tailsocks.__version__)"
```
