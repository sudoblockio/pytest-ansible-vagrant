from __future__ import annotations

import os
import re
import shutil
import subprocess
from enum import Enum
from typing import Callable, TypedDict

import pytest
from testinfra import get_host
from testinfra.host import Host

from pytest_ansible_vagrant.ansible import run_playbook_on_host


def require_bins(*bins: str) -> None:
    missing = [b for b in bins if shutil.which(b) is None]
    if missing:
        raise RuntimeError("Missing required binaries: " + ", ".join(missing))


class ShutdownMode(str, Enum):
    HALT = "halt"
    DESTROY = "destroy"
    NONE = "none"


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register CLI options and ini keys."""
    parser.addini(
        "vagrant_shutdown",
        "Vagrant shutdown behavior (halt|destroy|none).",
        default="destroy",
    )
    parser.addini("vagrant_file", "Path to the Vagrantfile.", default="Vagrantfile")

    grp = parser.getgroup("vagrant")
    grp.addoption(
        "--vagrant-file",
        action="store",
        dest="vagrant_file",
        help="Path to the Vagrantfile (overrides ini/env).",
    )
    grp.addoption(
        "--vagrant-shutdown",
        action="store",
        dest="vagrant_shutdown",
        choices=[m.value for m in ShutdownMode],
        help="Shutdown behavior after tests: halt|destroy|none (overrides ini/env).",
    )


def _read_opt(
    config: pytest.Config, name: str, env: str, ini: str, default: str
) -> str:
    """
    Precedence: CLI (--name) > ini (ini) > env (env) > default.
    """
    from_cli = config.getoption(name, default=None)
    if from_cli:
        return str(from_cli)
    from_ini = config.getini(ini)
    if isinstance(from_ini, str) and from_ini.strip():
        return from_ini.strip()
    from_env = os.getenv(env)
    if from_env:
        return from_env.strip()
    return default


def _resolve_vagrant_file(config: pytest.Config) -> str:
    return _read_opt(
        config=config,
        name="vagrant_file",
        env="VAGRANT_FILE",
        ini="vagrant_file",
        default="Vagrantfile",
    )


def _resolve_shutdown_mode(config: pytest.Config) -> ShutdownMode:
    raw = _read_opt(
        config=config,
        name="vagrant_shutdown",
        env="VAGRANT_SHUTDOWN",
        ini="vagrant_shutdown",
        default=ShutdownMode.DESTROY.value,
    ).lower()
    try:
        return ShutdownMode(raw)
    except ValueError as e:
        raise pytest.UsageError(
            f"Invalid vagrant_shutdown={raw!r}. Must be one of: "
            + ", ".join(m.value for m in ShutdownMode)
        ) from e


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


@pytest.fixture(scope="module")
def vagrant_run(request: pytest.FixtureRequest) -> Callable[..., Host]:
    """
    Callable fixture:
      vagrant_run(playbook=..., project_dir=..., vagrant_file=...) -> Host

    - Brings the VM up once per module.
    - Applies the given Ansible playbook to the guest.
    - Returns a testinfra Host connected over SSH.
    - Teardown honors the shutdown policy (halt|destroy|none).
    """
    vf: str | None = None

    def _runner(
        *, playbook: str, project_dir: str, vagrant_file: str | None = None
    ) -> Host:
        nonlocal vf
        vf = vagrant_file or _resolve_vagrant_file(request.config)

        up(vf)
        cfg = ssh_config(vf)
        run_playbook_on_host(playbook=playbook, project_dir=project_dir, **cfg)
        return get_host(
            f"ssh://{cfg['user']}@{cfg['hostname']}:{cfg['port']}",
            ssh_identity_file=cfg["identityfile"],
            ssh_extra_args="-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/dev/null",
        )

    try:
        yield _runner
    finally:
        # If the VM never came up (test aborted early), do nothing.
        # TODO: Why is this? Why no error? Not trying to catch errors
        if not vf:
            return

        mode = _resolve_shutdown_mode(request.config)
        if mode is ShutdownMode.HALT:
            halt(vf)
        elif mode is ShutdownMode.DESTROY:
            destroy(vf)
        elif mode is ShutdownMode.NONE:
            # leave it running
            pass
