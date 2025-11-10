from __future__ import annotations

import os
from typing import Any

from ansible_runner import RunnerConfig, Runner

from pytest_ansible_vagrant.utilities import extract_play_hosts
from pytest_ansible_vagrant.vagrant import SSHConfig


def _ansible_run_playbook(
    *,
    playbook: str,
    project_dir: str,
    roles_path: str | None,
    inventory: str,
    extravars: dict[str, Any] | None,
    artifact_subdir: str = ".artifacts",
) -> None:
    rcfg = RunnerConfig(
        project_dir=project_dir,
        private_data_dir=project_dir,
        roles_path=roles_path or os.path.join(project_dir, "roles"),
        playbook=playbook,
        inventory=inventory,
        artifact_dir=os.path.join(project_dir, artifact_subdir),
        extravars=extravars or {},
    )
    rcfg.prepare()
    status, rc = Runner(config=rcfg).run()
    if not (status == "successful" and rc == 0):
        raise RuntimeError(f"play failed: status={status}, rc={rc}")


def run_playbook_on_vagrant_host(
    *,
    playbook: str,
    project_dir: str,
    ssh: SSHConfig,
    inventory_file: str | None,
    extravars: dict[str, Any] | None,
) -> None:
    if inventory_file:
        inv = inventory_file
    else:
        patterns = extract_play_hosts(playbook)
        host_aliases = patterns or ["vagrant_host"]
        inv = ",".join(host_aliases) + ","

    ssh_vars = {
        "ansible_connection": "ssh",
        "ansible_host": ssh["hostname"],
        "ansible_port": ssh["port"],
        "ansible_user": ssh["user"],
        "ansible_ssh_private_key_file": ssh["identityfile"],
        "ansible_ssh_common_args": "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null",
        "ansible_python_interpreter": "/usr/bin/python3",
    }

    _ansible_run_playbook(
        playbook=playbook,
        project_dir=project_dir,
        roles_path=os.path.join(project_dir, "roles"),
        inventory=inv,
        extravars=(extravars or {}) | ssh_vars,
    )
