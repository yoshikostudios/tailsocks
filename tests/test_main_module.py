"""Tests for the __main__ module."""

from unittest.mock import patch


def test_main_module_import():
    """Test importing the __main__ module."""
    with patch("tailsocks.cli.main", return_value=0):
        # Import the module
        import tailsocks.__main__

        # Verify the module has the expected attributes
        assert hasattr(tailsocks.__main__, "main")


def test_main_module_execution():
    """Test executing the main function from __main__."""
    with patch("tailsocks.cli.main", return_value=42) as mock_main:
        # Import and execute main
        from tailsocks.__main__ import main

        result = main()

        # Verify main was called and return value is passed through
        mock_main.assert_called_once()
        assert result == 42
