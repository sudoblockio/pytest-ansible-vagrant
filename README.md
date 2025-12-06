# pytest-ansible-vagrant

[![Tests](https://github.com/sudoblockio-new/pytest-ansible-vagrant/actions/workflows/main.yaml/badge.svg?branch=main)](https://github.com/sudoblockio-new/pytest-ansible-vagrant/actions/workflows/main.yaml)
[![Copybara](https://github.com/sudoblockio-new/pytest-ansible-vagrant/actions/workflows/copy.yaml/badge.svg?branch=main)](https://github.com/sudoblockio-new/pytest-ansible-vagrant/actions/workflows/copy.yaml)
![GitHub Release Date](https://img.shields.io/github/release-date/sudoblockio-new/pytest-ansible-vagrant)
![GitHub tag (latest by date)](https://img.shields.io/github/v/tag/sudoblockio-new/pytest-ansible-vagrant)

Pytest plugin for testing Ansible playbooks against Vagrant VMs.

## Installation

```bash
pip install pytest-ansible-vagrant
```

## Requirements

- Python 3.10+
- Vagrant
- VirtualBox (default) or libvirt
- Ansible

## Usage

### Minimal

```python
from pytest_ansible_vagrant import VagrantRunner

def test_my_role(vagrant_runner: VagrantRunner):
    host = vagrant_runner("playbook.yaml")

    assert host.file("/etc/myconfig").is_file
```

### Full Options

```python
from pytest_ansible_vagrant import VagrantRunner

def test_my_role(vagrant_runner: VagrantRunner):
    host = vagrant_runner(
        "playbook.yaml",
        vagrant_file="Vagrantfile.custom",
        provider="virtualbox",
        extravars={"my_var": "value"},
        inventory_file="inventory.ini",
        artifact_dir="/tmp/ansible-artifacts",
    )

    assert host.file("/etc/myconfig").is_file
```

## Configuration

### pytest.ini Options

```ini
[pytest]
vagrant_shutdown = destroy      # halt | destroy | none
vagrant_file = Vagrantfile      # Path to Vagrantfile
vagrant_provider = virtualbox   # virtualbox | libvirt
vagrant_project_dir =           # Base project directory (auto-detected)
vagrant_artifact_dir =          # Directory for ansible artifacts
```

### Command Line Options

```bash
pytest --vagrant-file=Vagrantfile.custom
pytest --vagrant-shutdown=halt
pytest --vagrant-provider=libvirt
pytest --vagrant-project-dir=/path/to/project
pytest --vagrant-artifact-dir=/tmp/artifacts
```

## Project Layout

The plugin expects a standard Ansible role testing layout:

```
my-role/
├── roles/
│   └── my_role/
│       └── tasks/
│           └── main.yml
├── tests/
│   ├── tests/
│   │   ├── pytest.ini
│   │   └── test_my_role.py
│   ├── playbook.yaml
│   └── Vagrantfile
```

## Providers

### VirtualBox (Default)

VirtualBox is the default provider. No additional configuration needed.

```ruby
# Vagrantfile
Vagrant.configure("2") do |config|
  config.vm.box = "bento/ubuntu-24.04"

  config.vm.provider "virtualbox" do |vb|
    vb.memory = "1024"
    vb.cpus = 1
  end
end
```

### libvirt

Use libvirt by specifying the provider explicitly:

```python
host = vagrant_runner("playbook.yaml", provider="libvirt")
```

Or via pytest.ini:

```ini
[pytest]
vagrant_provider = libvirt
```

Requires additional binaries: `virsh`, `qemu-system-x86_64`

```ruby
# Vagrantfile.libvirt
Vagrant.configure("2") do |config|
  config.vm.box = "alvistack/ubuntu-24.10"

  config.vm.provider "libvirt" do |lv|
    lv.memory = 1024
    lv.cpus = 1
  end
end
```

## Shutdown Behavior

Control what happens to the VM after tests complete:

- `destroy` (default) - Destroy the VM
- `halt` - Stop the VM but keep it
- `none` - Leave the VM running

## Testinfra Integration

The `vagrant_runner()` call returns a [testinfra](https://testinfra.readthedocs.io/) `Host` object for assertions:

```python
def test_my_role(vagrant_runner: VagrantRunner):
    host = vagrant_runner("playbook.yaml")

    # File assertions
    assert host.file("/etc/myconfig").exists
    assert host.file("/etc/myconfig").is_file
    assert host.file("/etc/myconfig").user == "root"

    # Package assertions
    assert host.package("nginx").is_installed

    # Service assertions
    assert host.service("nginx").is_running
    assert host.service("nginx").is_enabled

    # Command execution
    result = host.run("whoami")
    assert result.stdout.strip() == "vagrant"
```

## License

Apache-2.0
