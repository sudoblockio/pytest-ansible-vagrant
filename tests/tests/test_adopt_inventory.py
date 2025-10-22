import os


def test_ansible_vagrant_adopt_inventory(collection_path, vagrant_run):
    host = vagrant_run(
        playbook=os.path.join(collection_path, "playbook-adopt-inventory.yaml"),
        project_dir=collection_path,
    )

    assert host.file("/etc/testfile").is_file
