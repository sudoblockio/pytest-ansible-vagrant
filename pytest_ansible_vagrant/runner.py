from __future__ import annotations

import os
import re
import subprocess
from enum import Enum
from typing import Any, TypedDict

import pytest
from testinfra import get_host
from testinfra.host import Host

from pytest_ansible_vagrant.utilities import (
    infer_project_dir_from_request,
    require_bins,
    resolve_inventory_path,
    resolve_playbook_path,
)


class ShutdownMode(str, Enum):
    HALT = "halt"
    DESTROY = "destroy"
    NONE = "none"


_PAT_HOST = re.compile(r"^\s*Host\s+(\S+)\s*$", re.IGNORECASE)
_PAT_KV = re.compile(
    r"^\s*(HostName|User|Port|IdentityFile)\s+(.+?)\s*$", re.IGNORECASE
)


class SSHConfig(TypedDict):
    hostname: str
    port: int
    user: str
    identityfile: str


def _from_ssh_config(text: str) -> SSHConfig:
    in_block = False
    fields: dict[str, str] = {}
    for raw in text.splitlines():
        if _PAT_HOST.match(raw):
            if not in_block:
                in_block = True
                continue
            break
        if not in_block:
            continue
        m = _PAT_KV.match(raw)
        if not m:
            continue
        key = m.group(1).lower()
        val = m.group(2).strip()
        # unquote
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        fields[key] = val

    missing = [
        k for k in ("hostname", "user", "port", "identityfile") if k not in fields
    ]
    if missing:
        casing = {
            "hostname": "HostName",
            "user": "User",
            "port": "Port",
            "identityfile": "IdentityFile",
        }
        raise ValueError("ssh-config missing: " + ", ".join(casing[k] for k in missing))

    try:
        port = int(fields["port"])
    except ValueError as e:
        raise ValueError(f"ssh-config invalid Port: {fields['port']!r}") from e

    return SSHConfig(
        hostname=fields["hostname"],
        port=port,
        user=fields["user"],
        identityfile=fields["identityfile"],
    )


def _env_for_file(vagrantfile: str) -> dict[str, str]:
    abs_vf = os.path.abspath(vagrantfile)
    env = dict(os.environ)
    env["VAGRANT_CWD"] = os.path.dirname(abs_vf)
    env["VAGRANT_VAGRANTFILE"] = os.path.basename(abs_vf)
    return env


def _run(
    cmd: list[str], vagrantfile: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["vagrant", *cmd],
        env=_env_for_file(vagrantfile),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=check,
    )


def up(vagrantfile: str) -> int:
    require_bins("vagrant", "ansible-playbook", "virsh", "qemu-system-x86_64")
    return _run(["up", "--provider", "libvirt"], vagrantfile).returncode


def halt(vagrantfile: str) -> int:
    return _run(["halt"], vagrantfile, check=False).returncode


def destroy(vagrantfile: str, force: bool = True) -> int:
    args = ["destroy", "-f"] if force else ["destroy"]
    return _run(args, vagrantfile, check=False).returncode


def ssh_config(vagrantfile: str) -> SSHConfig:
    cp = _run(["ssh-config"], vagrantfile)
    return _from_ssh_config(cp.stdout)


class VagrantRunner:
    """
    Callable runner used by the pytest fixture.

    Usage (from tests):

        def test_something(vagrant_runner: VagrantRunner):
            host = vagrant_runner("playbook.yaml")
            ...
    """

    def __init__(self, request: pytest.FixtureRequest) -> None:
        config = request.config

        proj_cli = config.getoption("vagrant_project_dir", default=None)
        proj_ini = (config.getini("vagrant_project_dir") or "").strip()
        if proj_cli:
            default_project_dir = os.path.abspath(proj_cli)
        elif proj_ini:
            default_project_dir = os.path.abspath(proj_ini)
        else:
            default_project_dir = infer_project_dir_from_request(request)

        assert (
            os.path.isdir(default_project_dir)
            and os.path.isdir(os.path.join(default_project_dir, "tests"))
            and os.path.isdir(os.path.join(default_project_dir, "roles"))
        ), (
            f"Invalid ansible project layout. Expected sibling 'tests' and 'roles' "
            f"under project_dir; resolved project_dir={default_project_dir!r}"
        )

        artifact_dir_cli = config.getoption("vagrant_artifact_dir", default=None)
        artifact_dir_ini = config.getini("vagrant_artifact_dir") or None

        self._config = config
        self._default_project_dir = default_project_dir
        self._artifact_dir_cli = artifact_dir_cli
        self._artifact_dir_ini = artifact_dir_ini
        self._vagrantfile: str | None = None
        self._host: Host | None = None

    def __call__(
        self,
        playbook: str,
        project_dir: str | None = None,
        vagrant_file: str | None = None,
        extravars: dict[str, Any] | None = None,
        inventory_file: str | None = None,
        artifact_dir: str | None = None,
    ) -> Host:
        # Local import to avoid circular import at module load time.
        from pytest_ansible_vagrant.ansible import run_playbook_on_vagrant_host

        proj = (
            os.path.abspath(project_dir)
            if project_dir is not None
            else self._default_project_dir
        )
        resolved_playbook = resolve_playbook_path(proj, playbook)
        resolved_inventory = resolve_inventory_path(proj, inventory_file)

        if vagrant_file:
            vf_abs = (
                vagrant_file
                if os.path.isabs(vagrant_file)
                else os.path.join(proj, vagrant_file)
            )
        else:
            config = self._config
            vf = (
                config.getoption("vagrant_file", default=None)
                or (config.getini("vagrant_file") or "").strip()
                or "Vagrantfile"
            )
            vf_abs = vf if os.path.isabs(vf) else os.path.join(proj, vf)

        if not os.path.exists(vf_abs):
            raise FileNotFoundError(f"Vagrantfile not found at: {vf_abs!r}")

        self._vagrantfile = vf_abs

        up(vf_abs)
        cfg = ssh_config(vf_abs)

        run_playbook_on_vagrant_host(
            playbook=resolved_playbook,
            project_dir=proj,
            ssh=cfg,
            inventory_file=resolved_inventory,
            extravars=extravars,
            artifact_dir=self._artifact_dir_cli
            or self._artifact_dir_ini
            or artifact_dir,
        )

        host = get_host(
            f"ssh://{cfg['user']}@{cfg['hostname']}:{cfg['port']}",
            ssh_identity_file=cfg["identityfile"],
            ssh_extra_args="-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/dev/null",
        )
        self._host = host
        return host

    @property
    def host(self) -> Host:
        if self._host is None:
            raise RuntimeError("VagrantRunner has not been invoked yet")
        return self._host

    @property
    def vagrantfile(self) -> str | None:
        return self._vagrantfile
