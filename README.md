# pytest-sb-ansible

[![Tests](https://github.com/sudoblockio-new/pytest-ansible-vagrant/actions/workflows/main.yaml/badge.svg?branch=main)](https://github.com/sudoblockio-new/pytest-ansible-vagrant/actions/workflows/main.yaml)
[![Copybara](https://github.com/sudoblockio-new/pytest-ansible-vagrant/actions/workflows/copy.yaml/badge.svg?branch=main)](https://github.com/sudoblockio-new/pytest-ansible-vagrant/actions/workflows/copy.yaml)
![GitHub Release Date](https://img.shields.io/github/release-date/sudoblockio-new/pytest-ansible-vagrant)
![GitHub tag (latest by date)](https://img.shields.io/github/v/tag/sudoblockio-new/pytest-ansible-vagrant)

Pytest plugins for running various ansible tests against VMs in vagrant.

### Usage

```python
def test_vagrant_run(vagrant_run):
    host = vagrant_run("tests/playbook-vms.yaml")  # Assumes `roles` directory next to `tests` dir

    assert host.file("/etc/testfile").is_file  # Returns a `pytest-infra` host object for assertions
```

### API

> TODO: Document the API

- `vagrant_run` params:
  - `playbook: str` - path to playbook
  - `project_dir: str` - path to the base of the collections directory
  - `vagrant_file: str` - path to Vagrantfile
- Returns a [`host` object](https://testinfra.readthedocs.io/en/latest/modules.html) from [pytest-testinfra](https://github.com/pytest-dev/pytest-testinfra) to make assertions
