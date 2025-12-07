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


def _parse_ssh_config_block(fields: dict[str, str]) -> SSHConfig:
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


def _from_ssh_config(text: str) -> SSHConfig:
    hosts = _from_ssh_config_multi(text)
    if not hosts:
        raise ValueError("ssh-config contains no valid host blocks")
    return next(iter(hosts.values()))


def _from_ssh_config_multi(text: str) -> dict[str, SSHConfig]:
    hosts: dict[str, SSHConfig] = {}
    current_host: str | None = None
    fields: dict[str, str] = {}

    for raw in text.splitlines():
        host_match = _PAT_HOST.match(raw)
        if host_match:
            if current_host is not None and fields:
                try:
                    hosts[current_host] = _parse_ssh_config_block(fields)
                except ValueError:
                    pass
            current_host = host_match.group(1)
            fields = {}
            continue

        if current_host is None:
            continue

        m = _PAT_KV.match(raw)
        if not m:
            continue
        key = m.group(1).lower()
        val = m.group(2).strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        fields[key] = val

    if current_host is not None and fields:
        try:
            hosts[current_host] = _parse_ssh_config_block(fields)
        except ValueError:
            pass

    return hosts


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


def up(vagrantfile: str, provider: str | None = "virtualbox") -> int:
    if provider == "libvirt":
        require_bins("vagrant", "ansible-playbook", "virsh", "qemu-system-x86_64")
        args = ["up", "--provider", "libvirt"]
    elif provider:
        require_bins("vagrant", "ansible-playbook")
        args = ["up", "--provider", provider]
    else:
        require_bins("vagrant", "ansible-playbook")
        args = ["up"]
    return _run(args, vagrantfile).returncode


def halt(vagrantfile: str) -> int:
    return _run(["halt"], vagrantfile, check=False).returncode


def destroy(vagrantfile: str, force: bool = True) -> int:
    args = ["destroy", "-f"] if force else ["destroy"]
    return _run(args, vagrantfile, check=False).returncode


def ssh_config(vagrantfile: str, host: str | None = None) -> SSHConfig:
    cp = _run(["ssh-config"], vagrantfile)
    if host:
        hosts = _from_ssh_config_multi(cp.stdout)
        if host not in hosts:
            available = list(hosts.keys())
            raise ValueError(
                f"Host {host!r} not found in ssh-config. Available: {available}"
            )
        return hosts[host]
    return _from_ssh_config(cp.stdout)


def ssh_config_all(vagrantfile: str) -> dict[str, SSHConfig]:
    cp = _run(["ssh-config"], vagrantfile)
    return _from_ssh_config_multi(cp.stdout)


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

        provider_cli = config.getoption("vagrant_provider", default=None)
        provider_ini = (config.getini("vagrant_provider") or "").strip()
        provider = provider_cli or provider_ini or "virtualbox"

        self._config = config
        self._default_project_dir = default_project_dir
        self._artifact_dir_cli = artifact_dir_cli
        self._artifact_dir_ini = artifact_dir_ini
        self._provider = provider
        self._vagrantfile: str | None = None
        self._host: Host | None = None
        self._hosts: dict[str, Host] = {}
        self._ssh_configs: dict[str, SSHConfig] = {}

    def __call__(
        self,
        playbook: str,
        project_dir: str | None = None,
        vagrant_file: str | None = None,
        provider: str | None = None,
        extravars: dict[str, Any] | None = None,
        inventory_file: str | None = None,
        artifact_dir: str | None = None,
        target_host: str | None = None,
    ) -> Host:
        from pytest_ansible_vagrant.ansible import run_playbook_on_vagrant_hosts

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
        provider_to_use = self._provider if provider is None else provider

        self._hosts = {}
        self._ssh_configs = {}

        up(vf_abs, provider=provider_to_use)
        all_ssh_configs = ssh_config_all(vf_abs)
        self._ssh_configs = all_ssh_configs

        if target_host:
            if target_host not in all_ssh_configs:
                available = list(all_ssh_configs.keys())
                raise ValueError(
                    f"Host {target_host!r} not found. Available: {available}"
                )
            ssh_configs_to_use = {target_host: all_ssh_configs[target_host]}
        else:
            ssh_configs_to_use = all_ssh_configs

        run_playbook_on_vagrant_hosts(
            playbook=resolved_playbook,
            project_dir=proj,
            ssh_configs=ssh_configs_to_use,
            inventory_file=resolved_inventory,
            extravars=extravars,
            artifact_dir=self._artifact_dir_cli
            or self._artifact_dir_ini
            or artifact_dir,
        )

        for name, cfg in ssh_configs_to_use.items():
            host = get_host(
                f"ssh://{cfg['user']}@{cfg['hostname']}:{cfg['port']}",
                ssh_identity_file=cfg["identityfile"],
                ssh_extra_args="-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/dev/null",
            )
            self._hosts[name] = host

        if target_host:
            self._host = self._hosts[target_host]
        else:
            self._host = next(iter(self._hosts.values()))

        return self._host

    @property
    def host(self) -> Host:
        if self._host is None:
            raise RuntimeError("VagrantRunner has not been invoked yet")
        return self._host

    @property
    def hosts(self) -> dict[str, Host]:
        if not self._hosts:
            raise RuntimeError("VagrantRunner has not been invoked yet")
        return self._hosts

    def get_host(self, name: str) -> Host:
        if not self._hosts:
            raise RuntimeError("VagrantRunner has not been invoked yet")
        if name not in self._hosts:
            available = list(self._hosts.keys())
            raise ValueError(f"Host {name!r} not found. Available: {available}")
        return self._hosts[name]

    @property
    def ssh_configs(self) -> dict[str, SSHConfig]:
        if not self._ssh_configs:
            raise RuntimeError("VagrantRunner has not been invoked yet")
        return self._ssh_configs

    @property
    def vagrantfile(self) -> str | None:
        return self._vagrantfile
