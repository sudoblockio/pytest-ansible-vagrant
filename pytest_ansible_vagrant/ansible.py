from __future__ import annotations

import os
import tempfile
from typing import Any

from ansible_runner import Runner, RunnerConfig

from pytest_ansible_vagrant.utilities import extract_play_hosts
from pytest_ansible_vagrant.runner import SSHConfig


def run_playbook_on_vagrant_host(
    *,
    playbook: str,
    project_dir: str,
    ssh: SSHConfig,
    inventory_file: str | None,
    extravars: dict[str, Any] | None,
    artifact_dir: str | None,
) -> None:
    if inventory_file:
        inventory = inventory_file
    else:
        patterns = extract_play_hosts(playbook)
        host_aliases = patterns or ["vagrant_host"]
        inventory = ",".join(host_aliases) + ","

    ssh_vars = {
        "ansible_connection": "ssh",
        "ansible_host": ssh["hostname"],
        "ansible_port": ssh["port"],
        "ansible_user": ssh["user"],
        "ansible_ssh_private_key_file": ssh["identityfile"],
        "ansible_ssh_common_args": "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null",
        "ansible_python_interpreter": "/usr/bin/python3",
    }

    rcfg = RunnerConfig(
        project_dir=project_dir,
        private_data_dir=project_dir,
        roles_path=os.path.join(project_dir, "roles"),
        playbook=playbook,
        inventory=inventory,
        artifact_dir=artifact_dir or tempfile.mkdtemp(prefix="pytest-ansible-vagrant-"),
        extravars=(extravars or {}) | ssh_vars,
    )
    rcfg.prepare()
    status, rc = Runner(config=rcfg).run()

    if rc != 0 or status != "successful":
        raise RuntimeError(f"ansible-runner failed: status={status!r}, rc={rc}")
