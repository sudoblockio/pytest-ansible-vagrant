import shutil

import pytest

from typing import Callable
import os
import re
import subprocess
from typing import TypedDict

from testinfra import get_host
from testinfra.host import Host

from pytest_ansible_vagrant.ansible import run_playbook_on_host


def require_bins(*bins: str) -> None:
    missing = [b for b in bins if shutil.which(b) is None]
    if missing:
        raise RuntimeError("Missing required binaries: " + ", ".join(missing))


def pytest_addoption(parser):
    v = parser.getgroup("vagrant")
    v.addoption("--vagrant-file", action="store", default="Vagrantfile")
    v.addoption(
        "--vagrant-shutdown",
        action="store",
        choices=("halt", "destroy", "none"),
        default="destroy",
    )


_PAT_HOST = re.compile(r"^\s*Host\s+(\S+)\s*$", re.IGNORECASE)
_PAT_KV = re.compile(
    r"^\s*(HostName|User|Port|IdentityFile)\s+(.+?)\s*$", re.IGNORECASE
)


class SSHConfig(TypedDict):
    hostname: str
    port: int
    user: str
    identityfile: str


def _from_ssh_config(text: str) -> "SSHConfig":
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
    return _run(
        ["destroy", "-f"] if force else ["destroy"], vagrantfile, check=False
    ).returncode


def ssh_config(vagrantfile: str) -> SSHConfig:
    cp = _run(["ssh-config"], vagrantfile)
    return _from_ssh_config(cp.stdout)


@pytest.fixture(scope="module")
def vagrant_run(request) -> Callable[..., Host]:
    """
    Callable fixture:
      vagrant_run(playbook=..., project_dir=..., vagrant_file=...) -> Host
    VM is brought up once per module and torn down at fixture teardown.
    """
    vf: str | None = None

    def _run(
        *,
        playbook: str,
        project_dir: str,
        vagrant_file: str | None = None,
    ) -> Host:
        nonlocal vf
        vf = vagrant_file or request.config.getoption("vagrant_file")

        up(vf)
        cfg = ssh_config(vf)
        run_playbook_on_host(playbook=playbook, project_dir=project_dir, **cfg)
        return get_host(
            f"ssh://{cfg['user']}@{cfg['hostname']}:{cfg['port']}",
            ssh_identity_file=cfg["identityfile"],
            ssh_extra_args="-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/dev/null",
        )

    try:
        yield _run
    finally:
        shutdown: str = request.config.getoption("vagrant_shutdown")
        if shutdown == "halt":
            halt(vf)
        elif shutdown == "destroy":
            destroy(vf)
