from __future__ import annotations

import os
import tempfile
from typing import Any

from ansible_runner import Runner, RunnerConfig

from pytest_ansible_vagrant.utilities import extract_play_hosts
from pytest_ansible_vagrant.runner import SSHConfig


def _build_inventory_content(
    ssh_configs: dict[str, SSHConfig],
    host_patterns: list[str] | None = None,
) -> str:
    lines = ["[vagrant]"]

    if len(ssh_configs) == 1 and host_patterns:
        cfg = next(iter(ssh_configs.values()))
        for pattern in host_patterns:
            lines.append(
                f"{pattern} "
                f"ansible_host={cfg['hostname']} "
                f"ansible_port={cfg['port']} "
                f"ansible_user={cfg['user']} "
                f"ansible_ssh_private_key_file={cfg['identityfile']} "
                f"ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null' "
                f"ansible_python_interpreter=/usr/bin/python3"
            )
    else:
        for name, cfg in ssh_configs.items():
            lines.append(
                f"{name} "
                f"ansible_host={cfg['hostname']} "
                f"ansible_port={cfg['port']} "
                f"ansible_user={cfg['user']} "
                f"ansible_ssh_private_key_file={cfg['identityfile']} "
                f"ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null' "
                f"ansible_python_interpreter=/usr/bin/python3"
            )
    return "\n".join(lines) + "\n"


def run_playbook_on_vagrant_host(
    *,
    playbook: str,
    project_dir: str,
    ssh: SSHConfig,
    inventory_file: str | None,
    extravars: dict[str, Any] | None,
    artifact_dir: str | None,
) -> None:
    run_playbook_on_vagrant_hosts(
        playbook=playbook,
        project_dir=project_dir,
        ssh_configs={"default": ssh},
        inventory_file=inventory_file,
        extravars=extravars,
        artifact_dir=artifact_dir,
    )


def run_playbook_on_vagrant_hosts(
    *,
    playbook: str,
    project_dir: str,
    ssh_configs: dict[str, SSHConfig],
    inventory_file: str | None,
    extravars: dict[str, Any] | None,
    artifact_dir: str | None,
) -> None:
    artifact_dir_resolved = artifact_dir or tempfile.mkdtemp(
        prefix="pytest-ansible-vagrant-"
    )

    if inventory_file:
        inventory = inventory_file
        cfg = next(iter(ssh_configs.values()))
        ssh_vars = {
            "ansible_host": cfg["hostname"],
            "ansible_port": cfg["port"],
            "ansible_user": cfg["user"],
            "ansible_ssh_private_key_file": cfg["identityfile"],
            "ansible_ssh_common_args": "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null",
            "ansible_python_interpreter": "/usr/bin/python3",
        }
    else:
        host_patterns = extract_play_hosts(playbook) or None
        inventory_content = _build_inventory_content(ssh_configs, host_patterns)
        inventory_path = os.path.join(artifact_dir_resolved, "inventory.ini")
        os.makedirs(artifact_dir_resolved, exist_ok=True)
        with open(inventory_path, "w") as f:
            f.write(inventory_content)
        inventory = inventory_path
        ssh_vars = {}

    base_extravars = (extravars or {}) | ssh_vars

    rcfg = RunnerConfig(
        project_dir=project_dir,
        private_data_dir=project_dir,
        roles_path=os.path.join(project_dir, "roles"),
        playbook=playbook,
        inventory=inventory,
        artifact_dir=artifact_dir_resolved,
        extravars=base_extravars,
    )
    rcfg.prepare()
    status, rc = Runner(config=rcfg).run()

    if rc != 0 or status != "successful":
        raise RuntimeError(f"ansible-runner failed: status={status!r}, rc={rc}")
