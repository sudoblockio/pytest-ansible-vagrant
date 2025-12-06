# pytest-ansible-vagrant

Pytest plugin for testing Ansible playbooks against Vagrant VMs.

## Commands

```bash
# Install in development mode
pip install -e .

# Run unit tests (no VM required)
cd tests/tests && pytest test_exceptions.py -v

# Run integration tests (requires Vagrant + VirtualBox)
cd tests/tests && pytest test_ansible_vagrant.py -v

# Run all tests
cd tests/tests && pytest -v
```

## Architecture

```
pytest_ansible_vagrant/
├── main.py       # pytest plugin hooks, fixtures, CLI options
├── runner.py     # VagrantRunner class, vagrant commands (up/halt/destroy)
├── ansible.py    # Ansible runner integration
└── utilities.py  # Path resolution, binary checks, YAML parsing
```

## Key Classes

- `VagrantRunner` - Main fixture callable, manages VM lifecycle
- `SSHConfig` - TypedDict for parsed SSH config from `vagrant ssh-config`
- `ShutdownMode` - Enum for halt/destroy/none behavior

## Default Provider

VirtualBox is the default provider. Use `--vagrant-provider=libvirt` or `provider="libvirt"` for libvirt.

## Test Layout

Tests expect sibling `roles/` and `tests/` directories:

```
project/
├── roles/
├── tests/
│   ├── tests/
│   │   └── test_*.py
│   ├── playbook.yaml
│   └── Vagrantfile
```

## Adding Tests

Unit tests go in `tests/tests/test_exceptions.py`. Integration tests requiring a VM go in `tests/tests/test_ansible_vagrant.py`.
