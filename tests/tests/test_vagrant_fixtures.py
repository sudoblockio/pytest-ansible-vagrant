"""Integration tests for vagrant_runner fixture - requires VMs."""

import pytest

from pytest_ansible_vagrant import VagrantRunner


@pytest.mark.integration
def test_fixture_available(vagrant_runner: VagrantRunner):
    assert vagrant_runner is not None


@pytest.mark.integration
def test_fixture_type(vagrant_runner: VagrantRunner):
    assert isinstance(vagrant_runner, VagrantRunner)


@pytest.mark.integration
def test_simple_playbook(vagrant_runner: VagrantRunner):
    """Test basic playbook run with libvirt provider."""
    host = vagrant_runner(
        "playbook.yaml",
        vagrant_file="Vagrantfile.libvirt",
    )
    assert host.file("/etc/foofile").is_file


@pytest.mark.integration
def test_playbook_with_inventory(vagrant_runner: VagrantRunner):
    """Test playbook with custom inventory and extravars."""
    host = vagrant_runner(
        "tests/playbook-with-inventory.yaml",
        vagrant_file="Vagrantfile.libvirt",
        inventory_file="tests/inventory.ini",
        extravars={"my_var": "bar"},
    )
    assert host.file("/etc/barfile").is_file


@pytest.mark.integration
@pytest.mark.multihost
def test_multihost_all_hosts(vagrant_runner: VagrantRunner):
    """Test multi-host playbook targeting all hosts."""
    vagrant_runner(
        "playbook-multihost.yaml",
        vagrant_file="Vagrantfile.multihost",
        provider="libvirt",
    )

    web = vagrant_runner.get_host("web")
    db = vagrant_runner.get_host("db")

    assert web.file("/etc/webfile").is_file
    assert db.file("/etc/dbfile").is_file


@pytest.mark.integration
@pytest.mark.multihost
def test_multihost_target_single(vagrant_runner: VagrantRunner):
    """Test targeting only one host in multi-host Vagrantfile."""
    host = vagrant_runner(
        "playbook-all.yaml",
        vagrant_file="Vagrantfile.multihost",
        target_host="web",
        provider="libvirt",
    )

    assert host.file("/etc/commonfile").is_file
    assert "web" in vagrant_runner.hosts
    assert len(vagrant_runner.hosts) == 1


@pytest.mark.integration
@pytest.mark.multihost
def test_multihost_hosts_property(vagrant_runner: VagrantRunner):
    """Test that hosts property provides all hosts."""
    vagrant_runner(
        "playbook-all.yaml",
        vagrant_file="Vagrantfile.multihost",
        provider="libvirt",
    )

    hosts = vagrant_runner.hosts
    assert "web" in hosts
    assert "db" in hosts

    for name, host in hosts.items():
        assert host.file("/etc/commonfile").is_file
