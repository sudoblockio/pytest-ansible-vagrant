"""Tests for utility functions."""

import pytest

from pytest_ansible_vagrant.utilities import (
    require_bins,
    resolve_playbook_path,
    resolve_inventory_path,
    extract_play_hosts,
)


def test_require_bins_all_present():
    require_bins("python", "sh")


def test_require_bins_missing_single():
    with pytest.raises(RuntimeError, match="Missing required binaries"):
        require_bins("nonexistent_binary_xyz123")


def test_require_bins_missing_multiple():
    with pytest.raises(
        RuntimeError, match="nonexistent_a.*nonexistent_b|nonexistent_b.*nonexistent_a"
    ):
        require_bins("python", "nonexistent_a", "nonexistent_b")


def test_resolve_playbook_absolute_exists(tmp_path):
    playbook = tmp_path / "test.yaml"
    playbook.touch()
    result = resolve_playbook_path(str(tmp_path), str(playbook))
    assert result == str(playbook)


def test_resolve_playbook_absolute_not_found(tmp_path):
    with pytest.raises(FileNotFoundError, match="playbook not found"):
        resolve_playbook_path(str(tmp_path), "/nonexistent/playbook.yaml")


def test_resolve_playbook_relative_exists(tmp_path):
    playbook = tmp_path / "playbook.yaml"
    playbook.touch()
    result = resolve_playbook_path(str(tmp_path), "playbook.yaml")
    assert result == str(playbook)


def test_resolve_playbook_relative_not_found(tmp_path):
    with pytest.raises(
        FileNotFoundError, match="playbook not found relative to project_dir"
    ):
        resolve_playbook_path(str(tmp_path), "missing.yaml")


def test_resolve_inventory_none(tmp_path):
    result = resolve_inventory_path(str(tmp_path), None)
    assert result is None


def test_resolve_inventory_empty_string(tmp_path):
    result = resolve_inventory_path(str(tmp_path), "")
    assert result is None


def test_resolve_inventory_absolute_path(tmp_path):
    result = resolve_inventory_path(str(tmp_path), "/etc/ansible/hosts")
    assert result == "/etc/ansible/hosts"


def test_resolve_inventory_relative_exists(tmp_path):
    inv = tmp_path / "inventory.ini"
    inv.touch()
    result = resolve_inventory_path(str(tmp_path), "inventory.ini")
    assert result == str(inv)


def test_resolve_inventory_host_list_pattern(tmp_path):
    result = resolve_inventory_path(str(tmp_path), "host1,host2,")
    assert result == "host1,host2,"


def test_extract_hosts_single_play(tmp_path):
    playbook = tmp_path / "test.yaml"
    playbook.write_text("- hosts: webservers\n  tasks: []")
    result = extract_play_hosts(str(playbook))
    assert result == ["webservers"]


def test_extract_hosts_multiple_plays(tmp_path):
    playbook = tmp_path / "test.yaml"
    playbook.write_text(
        "- hosts: webservers\n  tasks: []\n"
        "- hosts: dbservers\n  tasks: []\n"
        "- hosts: webservers\n  tasks: []"
    )
    result = extract_play_hosts(str(playbook))
    assert result == ["webservers", "dbservers"]


def test_extract_hosts_empty_playbook(tmp_path):
    playbook = tmp_path / "test.yaml"
    playbook.write_text("")
    result = extract_play_hosts(str(playbook))
    assert result == []


def test_extract_hosts_no_hosts_key(tmp_path):
    playbook = tmp_path / "test.yaml"
    playbook.write_text("- tasks: []")
    result = extract_play_hosts(str(playbook))
    assert result == []
