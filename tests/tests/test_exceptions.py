"""Tests for exception handling and edge cases."""

import pytest

from pytest_ansible_vagrant.utilities import (
    require_bins,
    resolve_playbook_path,
    resolve_inventory_path,
    extract_play_hosts,
)
from pytest_ansible_vagrant.runner import _from_ssh_config


class TestRequireBins:
    """Tests for require_bins utility."""

    def test_require_bins_all_present(self):
        """Should not raise when all binaries exist."""
        require_bins("python", "sh")

    def test_require_bins_missing_single(self):
        """Should raise RuntimeError for missing binary."""
        with pytest.raises(RuntimeError, match="Missing required binaries"):
            require_bins("nonexistent_binary_xyz123")

    def test_require_bins_missing_multiple(self):
        """Should list all missing binaries in error."""
        with pytest.raises(
            RuntimeError,
            match="nonexistent_a.*nonexistent_b|nonexistent_b.*nonexistent_a",
        ):
            require_bins("python", "nonexistent_a", "nonexistent_b")


class TestResolvePlaybookPath:
    """Tests for resolve_playbook_path utility."""

    def test_resolve_playbook_absolute_exists(self, tmp_path):
        """Should return absolute path when file exists."""
        playbook = tmp_path / "test.yaml"
        playbook.touch()
        result = resolve_playbook_path(str(tmp_path), str(playbook))
        assert result == str(playbook)

    def test_resolve_playbook_absolute_not_found(self, tmp_path):
        """Should raise FileNotFoundError for missing absolute path."""
        with pytest.raises(FileNotFoundError, match="playbook not found"):
            resolve_playbook_path(str(tmp_path), "/nonexistent/playbook.yaml")

    def test_resolve_playbook_relative_exists(self, tmp_path):
        """Should resolve relative path from project_dir."""
        playbook = tmp_path / "playbook.yaml"
        playbook.touch()
        result = resolve_playbook_path(str(tmp_path), "playbook.yaml")
        assert result == str(playbook)

    def test_resolve_playbook_relative_not_found(self, tmp_path):
        """Should raise FileNotFoundError for missing relative path."""
        with pytest.raises(
            FileNotFoundError, match="playbook not found relative to project_dir"
        ):
            resolve_playbook_path(str(tmp_path), "missing.yaml")


class TestResolveInventoryPath:
    """Tests for resolve_inventory_path utility."""

    def test_resolve_inventory_none(self, tmp_path):
        """Should return None when inventory_file is None."""
        result = resolve_inventory_path(str(tmp_path), None)
        assert result is None

    def test_resolve_inventory_empty_string(self, tmp_path):
        """Should return None when inventory_file is empty string."""
        result = resolve_inventory_path(str(tmp_path), "")
        assert result is None

    def test_resolve_inventory_absolute_path(self, tmp_path):
        """Should return absolute path unchanged."""
        result = resolve_inventory_path(str(tmp_path), "/etc/ansible/hosts")
        assert result == "/etc/ansible/hosts"

    def test_resolve_inventory_relative_exists(self, tmp_path):
        """Should resolve relative path when file exists."""
        inv = tmp_path / "inventory.ini"
        inv.touch()
        result = resolve_inventory_path(str(tmp_path), "inventory.ini")
        assert result == str(inv)

    def test_resolve_inventory_relative_not_found(self, tmp_path):
        """Should return original string for host-list patterns."""
        result = resolve_inventory_path(str(tmp_path), "host1,host2,")
        assert result == "host1,host2,"


class TestExtractPlayHosts:
    """Tests for extract_play_hosts utility."""

    def test_extract_hosts_single_play(self, tmp_path):
        """Should extract hosts from single play."""
        playbook = tmp_path / "test.yaml"
        playbook.write_text("- hosts: webservers\n  tasks: []")
        result = extract_play_hosts(str(playbook))
        assert result == ["webservers"]

    def test_extract_hosts_multiple_plays(self, tmp_path):
        """Should extract unique hosts from multiple plays."""
        playbook = tmp_path / "test.yaml"
        playbook.write_text(
            "- hosts: webservers\n  tasks: []\n"
            "- hosts: dbservers\n  tasks: []\n"
            "- hosts: webservers\n  tasks: []"
        )
        result = extract_play_hosts(str(playbook))
        assert result == ["webservers", "dbservers"]

    def test_extract_hosts_empty_playbook(self, tmp_path):
        """Should return empty list for empty playbook."""
        playbook = tmp_path / "test.yaml"
        playbook.write_text("")
        result = extract_play_hosts(str(playbook))
        assert result == []

    def test_extract_hosts_no_hosts_key(self, tmp_path):
        """Should return empty list when no hosts key."""
        playbook = tmp_path / "test.yaml"
        playbook.write_text("- tasks: []")
        result = extract_play_hosts(str(playbook))
        assert result == []


class TestSSHConfigParsing:
    """Tests for SSH config parsing."""

    def test_parse_valid_ssh_config(self):
        """Should parse valid SSH config correctly."""
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

    def test_parse_ssh_config_quoted_values(self):
        """Should handle quoted values correctly."""
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

    def test_parse_ssh_config_missing_hostname(self):
        """Should raise ValueError for missing HostName."""
        config_text = """
Host default
  User vagrant
  Port 2222
  IdentityFile /path/to/key
"""
        with pytest.raises(ValueError, match="ssh-config missing.*HostName"):
            _from_ssh_config(config_text)

    def test_parse_ssh_config_missing_user(self):
        """Should raise ValueError for missing User."""
        config_text = """
Host default
  HostName 127.0.0.1
  Port 2222
  IdentityFile /path/to/key
"""
        with pytest.raises(ValueError, match="ssh-config missing.*User"):
            _from_ssh_config(config_text)

    def test_parse_ssh_config_missing_port(self):
        """Should raise ValueError for missing Port."""
        config_text = """
Host default
  HostName 127.0.0.1
  User vagrant
  IdentityFile /path/to/key
"""
        with pytest.raises(ValueError, match="ssh-config missing.*Port"):
            _from_ssh_config(config_text)

    def test_parse_ssh_config_missing_identityfile(self):
        """Should raise ValueError for missing IdentityFile."""
        config_text = """
Host default
  HostName 127.0.0.1
  User vagrant
  Port 2222
"""
        with pytest.raises(ValueError, match="ssh-config missing.*IdentityFile"):
            _from_ssh_config(config_text)

    def test_parse_ssh_config_invalid_port(self):
        """Should raise ValueError for non-integer Port."""
        config_text = """
Host default
  HostName 127.0.0.1
  User vagrant
  Port notanumber
  IdentityFile /path/to/key
"""
        with pytest.raises(ValueError, match="ssh-config invalid Port"):
            _from_ssh_config(config_text)

    def test_parse_ssh_config_empty(self):
        """Should raise ValueError for empty config."""
        with pytest.raises(ValueError, match="ssh-config missing"):
            _from_ssh_config("")


class TestVagrantRunnerExceptions:
    """Tests for VagrantRunner exception handling."""

    def test_vagrantfile_not_found(self, tmp_path):
        """Should raise FileNotFoundError for missing Vagrantfile."""
        from pytest_ansible_vagrant.runner import VagrantRunner
        from unittest.mock import MagicMock

        mock_request = MagicMock()
        mock_request.config.getoption.return_value = None
        mock_request.config.getini.return_value = ""
        mock_request.fspath = tmp_path / "tests" / "test_file.py"

        roles_dir = tmp_path / "roles"
        roles_dir.mkdir()
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_file.py"
        test_file.touch()

        runner = VagrantRunner(mock_request)

        playbook = tmp_path / "playbook.yaml"
        playbook.touch()

        with pytest.raises(FileNotFoundError, match="Vagrantfile not found"):
            runner("playbook.yaml", vagrant_file="nonexistent/Vagrantfile")

    def test_host_property_before_invocation(self, tmp_path):
        """Should raise RuntimeError when accessing host before invocation."""
        from pytest_ansible_vagrant.runner import VagrantRunner
        from unittest.mock import MagicMock

        mock_request = MagicMock()
        mock_request.config.getoption.return_value = None
        mock_request.config.getini.return_value = ""
        mock_request.fspath = tmp_path / "tests" / "test_file.py"

        roles_dir = tmp_path / "roles"
        roles_dir.mkdir()
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_file.py"
        test_file.touch()

        runner = VagrantRunner(mock_request)

        with pytest.raises(
            RuntimeError, match="VagrantRunner has not been invoked yet"
        ):
            _ = runner.host

    def test_invalid_project_layout_no_tests(self, tmp_path):
        """Should raise AssertionError for missing tests directory."""
        from pytest_ansible_vagrant.runner import VagrantRunner
        from unittest.mock import MagicMock

        mock_request = MagicMock()
        mock_request.config.getoption.return_value = str(tmp_path)
        mock_request.config.getini.return_value = ""

        roles_dir = tmp_path / "roles"
        roles_dir.mkdir()

        with pytest.raises(AssertionError, match="Invalid ansible project layout"):
            VagrantRunner(mock_request)

    def test_invalid_project_layout_no_roles(self, tmp_path):
        """Should raise AssertionError for missing roles directory."""
        from pytest_ansible_vagrant.runner import VagrantRunner
        from unittest.mock import MagicMock

        mock_request = MagicMock()
        mock_request.config.getoption.return_value = str(tmp_path)
        mock_request.config.getini.return_value = ""

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        with pytest.raises(AssertionError, match="Invalid ansible project layout"):
            VagrantRunner(mock_request)
