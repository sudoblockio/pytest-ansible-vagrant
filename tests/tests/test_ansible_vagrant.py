from pytest_ansible_vagrant import VagrantRunner


def test_ansible_vagrant_simple(vagrant_runner: VagrantRunner):
    """Test basic playbook run with default virtualbox provider."""
    host = vagrant_runner("playbook.yaml")

    assert host.file("/etc/foofile").is_file


def test_ansible_vagrant_with_inventory(vagrant_runner: VagrantRunner):
    """Test playbook with custom inventory and extravars."""
    host = vagrant_runner(
        "tests/playbook-with-inventory.yaml",
        inventory_file="tests/inventory.ini",
        extravars={"my_var": "bar"},
    )

    assert host.file("/etc/barfile").is_file


def test_ansible_vagrant_libvirt(vagrant_runner: VagrantRunner):
    """Test playbook with explicit libvirt provider."""
    host = vagrant_runner(
        "playbook.yaml",
        vagrant_file="Vagrantfile.libvirt",
        provider="libvirt",
    )

    assert host.file("/etc/foofile").is_file
