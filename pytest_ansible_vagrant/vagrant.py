from __future__ import annotations

import os
import re
import shutil
import subprocess
from enum import Enum
from typing import Callable, TypedDict, Any

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
    # INI options
    parser.addini(
        "vagrant_shutdown",
        "Vagrant shutdown behavior (halt|destroy|none).",
        default="destroy",
    )
    parser.addini("vagrant_file", "Path to the Vagrantfile.", default="Vagrantfile")
    parser.addini(
        "vagrant_project_dir",
        "Base project directory; if omitted it is inferred as the parent of the nearest `tests/` directory.",
        default="",
    )

    # CLI options (namespaced to avoid conflicts with other plugins)
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
    grp.addoption(
        "--vagrant-project-dir",
        action="store",
        dest="vagrant_project_dir",
        help="Base directory containing roles/ and tests/ (overrides ini).",
    )


def _read_opt(
    config: pytest.Config, name: str, env: str, ini: str, default: str
) -> str:
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


def _infer_project_dir_from_request(request: pytest.FixtureRequest) -> str:
    test_file = os.path.abspath(str(request.fspath))
    cur = os.path.dirname(test_file)
    while True:
        if os.path.basename(cur) == "tests":
            return os.path.dirname(cur)
        parent = os.path.dirname(cur)
        if parent == cur:
            return os.path.dirname(os.path.dirname(test_file))
        cur = parent


def _resolve_playbook_path(project_dir: str, playbook: str) -> str:
    if os.path.isabs(playbook):
        if os.path.exists(playbook):
            return playbook
        raise FileNotFoundError(f"playbook not found: {playbook!r}")
    candidate = os.path.join(project_dir, playbook)
    if os.path.exists(candidate):
        return candidate
    raise FileNotFoundError(
        f"playbook not found relative to project_dir. "
        f"project_dir={project_dir!r}, playbook={playbook!r}, tried={candidate!r}"
    )


def _resolve_inventory_path(project_dir: str, inventory_file: str | None) -> str | None:
    if not inventory_file:
        return None
    if os.path.isabs(inventory_file):
        return inventory_file
    candidate = os.path.join(project_dir, inventory_file)
    return candidate if os.path.exists(candidate) else inventory_file


def _resolve_vagrant_file(config: pytest.Config, base_dir: str) -> str:
    vf_raw = _read_opt(
        config=config,
        name="vagrant_file",
        env="VAGRANT_FILE",
        ini="vagrant_file",
        default="Vagrantfile",
    )
    return vf_raw if os.path.isabs(vf_raw) else os.path.join(base_dir, vf_raw)


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
    vf_abs: str | None = None

    # Resolve project_dir: CLI > INI > inferred
    proj_cli = request.config.getoption("vagrant_project_dir", default=None)
    proj_ini = (request.config.getini("vagrant_project_dir") or "").strip()
    if proj_cli:
        default_project_dir = os.path.abspath(proj_cli)
    elif proj_ini:
        default_project_dir = os.path.abspath(proj_ini)
    else:
        default_project_dir = _infer_project_dir_from_request(request)

    assert (
        os.path.isdir(default_project_dir)
        and os.path.isdir(os.path.join(default_project_dir, "tests"))
        and os.path.isdir(os.path.join(default_project_dir, "roles"))
    ), (
        f"Invalid ansible project layout. Expected sibling 'tests' and 'roles' "
        f"under project_dir; resolved project_dir={default_project_dir!r}"
    )

    def _runner(
        playbook: str,
        project_dir: str | None = None,
        vagrant_file: str | None = None,
        extravars: dict[str, Any] | None = None,
        inventory_file: str | None = None,
    ) -> Host:
        nonlocal vf_abs

        proj = os.path.abspath(project_dir) if project_dir else default_project_dir
        resolved_playbook = _resolve_playbook_path(proj, playbook)
        resolved_inventory = _resolve_inventory_path(proj, inventory_file)

        if vagrant_file:
            vf_abs = (
                vagrant_file
                if os.path.isabs(vagrant_file)
                else os.path.join(proj, vagrant_file)
            )
        else:
            vf_abs = _resolve_vagrant_file(request.config, proj)

        if not os.path.exists(vf_abs):
            raise FileNotFoundError(f"Vagrantfile not found at: {vf_abs!r}")

        up(vf_abs)
        cfg = ssh_config(vf_abs)

        run_playbook_on_host(
            playbook=resolved_playbook,
            project_dir=proj,
            inventory_file=resolved_inventory,
            extravars=extravars,
            **cfg,
        )

        return get_host(
            f"ssh://{cfg['user']}@{cfg['hostname']}:{cfg['port']}",
            ssh_identity_file=cfg["identityfile"],
            ssh_extra_args="-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/dev/null",
        )

    try:
        yield _runner
    finally:
        if not vf_abs:
            return
        mode = _resolve_shutdown_mode(request.config)
        if mode is ShutdownMode.HALT:
            halt(vf_abs)
        elif mode is ShutdownMode.DESTROY:
            destroy(vf_abs)
        elif mode is ShutdownMode.NONE:
            pass
