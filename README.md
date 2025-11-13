# pytest-sb-ansible

[![Tests](https://github.com/sudoblockio-new/pytest-ansible-vagrant/actions/workflows/main.yaml/badge.svg?branch=main)](https://github.com/sudoblockio-new/pytest-ansible-vagrant/actions/workflows/main.yaml)
[![Copybara](https://github.com/sudoblockio-new/pytest-ansible-vagrant/actions/workflows/copy.yaml/badge.svg?branch=main)](https://github.com/sudoblockio-new/pytest-ansible-vagrant/actions/workflows/copy.yaml)
![GitHub Release Date](https://img.shields.io/github/release-date/sudoblockio-new/pytest-ansible-vagrant)
![GitHub tag (latest by date)](https://img.shields.io/github/v/tag/sudoblockio-new/pytest-ansible-vagrant)

Pytest plugins for running various ansible tests against VMs in vagrant.

### Usage

**minimal**
```python
from pytest_ansible_vagrant import VagrantRunner

def test_vagrant_runner(vagrant_runner: VagrantRunner):
    host = vagrant_runner("tests/playbook-vms.yaml")  # Assumes `roles` directory next to `tests` dir

    assert host.file("/etc/testfile").is_file  # Returns a `pytest-infra` host object for assertions
```

**full**
```python
from pytest_ansible_vagrant import VagrantRunner

def test_vagrant_run(vagrant_run: VagrantRunner):
    host = vagrant_run(
      "tests/playbook-vms.yaml",
      vagrant_file="Vagrant.ubuntu24",
      extravars={"my_var": 42},
      inventory_file="my_inventory.yml",
    )

    assert host.file("/etc/testfile").is_file
```
