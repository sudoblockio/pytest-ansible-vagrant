import os
from typing import Any, Mapping

import yaml
from ansible_runner import Runner, RunnerConfig


def run_playbook(
    playbook: str,
    *,
    project_dir: str,
    roles_path: str | None = None,
    inventory: str = "localhost,",
    extravars: Mapping[str, Any] | None = None,
    envvars: Mapping[str, str] | None = None,
    artifact_subdir: str = ".artifacts",
) -> None:
    rcfg = RunnerConfig(
        project_dir=project_dir,
        private_data_dir=project_dir,
        roles_path=roles_path or os.path.join(project_dir, "roles"),
        playbook=playbook,
        inventory=inventory,
        artifact_dir=os.path.join(project_dir, artifact_subdir),
        extravars=dict(extravars or {}),
        envvars=dict(envvars or {}),
    )
    rcfg.prepare()
    status, rc = Runner(config=rcfg).run()
    if not (status == "successful" and rc == 0):
        raise RuntimeError(f"play failed: status={status}, rc={rc}")


def _extract_play_hosts(playbook_path: str) -> list[str]:
    with open(playbook_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if isinstance(data, list):
        plays = [p for p in data if isinstance(p, dict)]
    elif isinstance(data, dict):
        plays = [data]
    else:
        return []

    out: list[str] = []
    for p in plays:
        h = p.get("hosts")
        if isinstance(h, str):
            hv = h.strip()
            if hv:
                out.append(hv)

    seen: set[str] = set()
    uniq: list[str] = []
    for h in out:
        if h not in seen:
            uniq.append(h)
            seen.add(h)
    return uniq


def run_playbook_on_host(
    hostname: str,
    port: int,
    user: str,
    identityfile: str,
    playbook: str,
    project_dir: str,
    *,
    inventory_file: str | None = None,
    envvars: Mapping[str, str] | None = None,
) -> None:
    ssh_vars = {
        "ansible_connection": "ssh",
        "ansible_host": hostname,
        "ansible_port": port,
        "ansible_user": user,
        "ansible_ssh_private_key_file": identityfile,
        "ansible_ssh_common_args": "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null",
        "ansible_python_interpreter": "/usr/bin/python3",
    }

    if inventory_file:
        run_playbook(
            playbook=playbook,
            project_dir=project_dir,
            roles_path=os.path.join(project_dir, "roles"),
            inventory=inventory_file,
            extravars=ssh_vars,
            envvars=dict(envvars or {}),
        )
        return

    patterns = _extract_play_hosts(playbook)
    host_aliases: list[str] = patterns or ["vagrant_host"]
    hostlist = ",".join(host_aliases) + ","

    run_playbook(
        playbook=playbook,
        project_dir=project_dir,
        roles_path=os.path.join(project_dir, "roles"),
        inventory=hostlist,
        extravars=ssh_vars,
        envvars=dict(envvars or {}),
    )
