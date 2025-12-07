"""Pytest configuration for pytest-ansible-vagrant tests."""

import os

import pytest


@pytest.fixture(scope="function", autouse=True)
def cd_to_test_dir(request):
    """Change to test file's directory for relative path resolution."""
    original_dir = os.getcwd()
    os.chdir(request.fspath.dirname)
    yield
    os.chdir(original_dir)
