from __future__ import annotations

import os
import re
import subprocess
from enum import Enum
from typing import TypedDict

from pytest_ansible_vagrant.utilities import require_bins


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
