"""Tests for VagrantRunner - unit tests without VMs."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pytest_ansible_vagrant import VagrantRunner
from pytest_ansible_vagrant.runner import (
    _from_ssh_config,
    _from_ssh_config_multi,
    _parse_ssh_config_block,
)


TESTS_DIR = Path(__file__).parent


def _make_mock_request(tmp_path: Path) -> MagicMock:
    """Create a mock pytest request with valid project layout."""
    mock_request = MagicMock()
    mock_request.config.getoption.return_value = None
    mock_request.config.getini.return_value = ""
    mock_request.path = tmp_path / "tests" / "test_file.py"

    (tmp_path / "roles").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_file.py").touch()

    return mock_request


def test_runner_init(tmp_path):
    mock_request = _make_mock_request(tmp_path)
    runner = VagrantRunner(mock_request)
    assert runner._default_project_dir == str(tmp_path)


def test_runner_vagrantfile_not_found(tmp_path):
    mock_request = _make_mock_request(tmp_path)
    runner = VagrantRunner(mock_request)

    playbook = tmp_path / "playbook.yaml"
    playbook.touch()

    with pytest.raises(FileNotFoundError, match="Vagrantfile not found"):
        runner("playbook.yaml", vagrant_file="nonexistent/Vagrantfile")


def test_runner_host_before_invocation(tmp_path):
    mock_request = _make_mock_request(tmp_path)
    runner = VagrantRunner(mock_request)

    with pytest.raises(RuntimeError, match="VagrantRunner has not been invoked yet"):
        _ = runner.host


def test_runner_hosts_before_invocation(tmp_path):
    mock_request = _make_mock_request(tmp_path)
    runner = VagrantRunner(mock_request)

    with pytest.raises(RuntimeError, match="VagrantRunner has not been invoked yet"):
        _ = runner.hosts


def test_runner_get_host_before_invocation(tmp_path):
    mock_request = _make_mock_request(tmp_path)
    runner = VagrantRunner(mock_request)

    with pytest.raises(RuntimeError, match="VagrantRunner has not been invoked yet"):
        runner.get_host("web")


def test_runner_ssh_configs_before_invocation(tmp_path):
    mock_request = _make_mock_request(tmp_path)
    runner = VagrantRunner(mock_request)

    with pytest.raises(RuntimeError, match="VagrantRunner has not been invoked yet"):
        _ = runner.ssh_configs


def test_runner_invalid_layout_no_roles(tmp_path):
    mock_request = MagicMock()
    mock_request.config.getoption.return_value = str(tmp_path)
    mock_request.config.getini.return_value = ""

    (tmp_path / "tests").mkdir()

    with pytest.raises(AssertionError, match="Invalid ansible project layout"):
        VagrantRunner(mock_request)


def test_runner_invalid_layout_no_tests(tmp_path):
    mock_request = MagicMock()
    mock_request.config.getoption.return_value = str(tmp_path)
    mock_request.config.getini.return_value = ""

    (tmp_path / "roles").mkdir()

    with pytest.raises(AssertionError, match="Invalid ansible project layout"):
        VagrantRunner(mock_request)


def test_parse_ssh_config_valid():
    config_text = """
Host default
  HostName 127.0.0.1
  User vagrant
  Port 2222
  IdentityFile /path/to/key
"""
    result = _from_ssh_config(config_text)
    assert result["hostname"] == "127.0.0.1"
    assert result["user"] == "vagrant"
    assert result["port"] == 2222
    assert result["identityfile"] == "/path/to/key"


def test_parse_ssh_config_quoted_values():
    config_text = """
Host default
  HostName "127.0.0.1"
  User 'vagrant'
  Port 2222
  IdentityFile "/path/to/key"
"""
    result = _from_ssh_config(config_text)
    assert result["hostname"] == "127.0.0.1"
    assert result["identityfile"] == "/path/to/key"


def test_parse_ssh_config_empty():
    with pytest.raises(ValueError, match="ssh-config contains no valid host blocks"):
        _from_ssh_config("")


def test_parse_ssh_config_missing_fields():
    config_text = """
Host default
  User vagrant
  Port 2222
"""
    with pytest.raises(ValueError, match="ssh-config contains no valid host blocks"):
        _from_ssh_config(config_text)


def test_parse_ssh_config_multi():
    config_text = """
Host web
  HostName 127.0.0.1
  User vagrant
  Port 2222
  IdentityFile /path/to/web/key

Host db
  HostName 127.0.0.1
  User vagrant
  Port 2223
  IdentityFile /path/to/db/key
"""
    result = _from_ssh_config_multi(config_text)
    assert len(result) == 2
    assert "web" in result
    assert "db" in result
    assert result["web"]["port"] == 2222
    assert result["db"]["port"] == 2223


def test_parse_ssh_config_multi_single():
    config_text = """
Host default
  HostName 127.0.0.1
  User vagrant
  Port 2222
  IdentityFile /path/to/key
"""
    result = _from_ssh_config_multi(config_text)
    assert len(result) == 1
    assert "default" in result


def test_parse_ssh_config_multi_empty():
    result = _from_ssh_config_multi("")
    assert result == {}


def test_parse_ssh_config_block_missing_hostname():
    fields = {"user": "vagrant", "port": "2222", "identityfile": "/path"}
    with pytest.raises(ValueError, match="HostName"):
        _parse_ssh_config_block(fields)


def test_parse_ssh_config_block_invalid_port():
    fields = {
        "hostname": "127.0.0.1",
        "user": "vagrant",
        "port": "notanumber",
        "identityfile": "/path",
    }
    with pytest.raises(ValueError, match="invalid Port"):
        _parse_ssh_config_block(fields)
