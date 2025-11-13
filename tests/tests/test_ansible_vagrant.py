from pytest_ansible_vagrant import VagrantRunner


def test_ansible_vagrant_inventory_simple(vagrant_runner: VagrantRunner):
    host = vagrant_runner("playbook.yaml")

    assert host.file("/etc/foofile").is_file


def test_ansible_vagrant_inventory_with_inventory(vagrant_runner: VagrantRunner):
    host = vagrant_runner(
        "tests/playbook-with-inventory.yaml",
        inventory_file="tests/inventory.ini",
        extravars={"my_var": "bar"},
    )

    assert host.file("/etc/barfile").is_file
