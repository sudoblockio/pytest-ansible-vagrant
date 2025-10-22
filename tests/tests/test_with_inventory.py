import os


def test_ansible_vagrant_inventory_with_inventory(collection_path, vagrant_run):
    host = vagrant_run(
        playbook=os.path.join(collection_path, "tests", "playbook-with-inventory.yaml"),
        project_dir=collection_path,
        inventory_file=os.path.join(collection_path, "tests", "inventory.ini"),
    )

    assert host.file("/etc/testfile").is_file
