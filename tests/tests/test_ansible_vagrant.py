def test_ansible_vagrant_adopt_inventory_simple(vagrant_run):
    host = vagrant_run("playbook-adopt-inventory.yaml")

    assert host.file("/etc/foofile").is_file


def test_ansible_vagrant_inventory_with_inventory(vagrant_run):
    host = vagrant_run(
        "tests/playbook-with-inventory.yaml",
        inventory_file="tests/inventory.ini",
        extravars={"my_var": "bar"},
    )

    assert host.file("/etc/barfile").is_file
