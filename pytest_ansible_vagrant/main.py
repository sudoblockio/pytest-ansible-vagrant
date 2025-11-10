from __future__ import annotations

import os
from typing import Any, Callable, Generator

import pytest
from testinfra import get_host
from testinfra.host import Host

from pytest_ansible_vagrant.ansible import run_playbook_on_vagrant_host
from pytest_ansible_vagrant.utilities import (
    addoption_safe,
    addini_safe,
    infer_project_dir_from_request,
    resolve_playbook_path,
    resolve_inventory_path,
)
from pytest_ansible_vagrant.vagrant import ShutdownMode, up, halt, destroy, ssh_config


def pytest_addoption(parser: pytest.Parser) -> None:
    addini_safe(
        parser,
        "vagrant_shutdown",
        "Vagrant shutdown behavior (halt|destroy|none).",
        default=ShutdownMode.DESTROY.value,
    )
    addini_safe(
        parser,
        "vagrant_file",
        "Path to the Vagrantfile.",
        default="Vagrantfile",
    )
    addini_safe(
        parser,
        "vagrant_project_dir",
        "Base project directory; if omitted it is inferred as the parent of the nearest `tests/` directory.",
        default="",
    )

    grp = parser.getgroup("vagrant")
    addoption_safe(
        grp,
        "--vagrant-file",
        action="store",
        dest="vagrant_file",
        help="Path to the Vagrantfile",
    )
    addoption_safe(
        grp,
        "--vagrant-shutdown",
        action="store",
        dest="vagrant_shutdown",
        choices=[m.value for m in ShutdownMode],
        help="Shutdown behavior after tests: halt|destroy|none",
    )
    addoption_safe(
        grp,
        "--vagrant-project-dir",
        action="store",
        dest="vagrant_project_dir",
        help="Base directory containing roles/ and tests/",
    )


def _resolve_shutdown_mode(config: pytest.Config) -> ShutdownMode:
    raw = (
        (
            config.getoption("vagrant_shutdown", default=None)
            or config.getini("vagrant_shutdown")
            or ""
        )
        .strip()
        .lower()
    )
    if not raw:
        raw = ShutdownMode.DESTROY.value
    try:
        return ShutdownMode(raw)
    except ValueError as e:
        raise pytest.UsageError(
            f"Invalid vagrant_shutdown={raw!r}. Must be one of: "
            + ", ".join(m.value for m in ShutdownMode)
        ) from e


def _resolve_vagrant_file(config: pytest.Config, base_dir: str) -> str:
    vf = (
        config.getoption("vagrant_file", default=None)
        or (config.getini("vagrant_file") or "").strip()
        or "Vagrantfile"
    )
    return vf if os.path.isabs(vf) else os.path.join(base_dir, vf)


@pytest.fixture(scope="module")
def vagrant_run(
    request: pytest.FixtureRequest,
) -> Generator[Callable[..., Host], None, None]:
    vf_abs: str | None = None

    proj_cli = request.config.getoption("vagrant_project_dir", default=None)
    proj_ini = (request.config.getini("vagrant_project_dir") or "").strip()
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

    def _runner(
        playbook: str,
        project_dir: str | None = None,
        vagrant_file: str | None = None,
        extravars: dict[str, Any] | None = None,
        inventory_file: str | None = None,
    ) -> Host:
        nonlocal vf_abs

        proj = os.path.abspath(project_dir) if project_dir else default_project_dir
        resolved_playbook = resolve_playbook_path(proj, playbook)
        resolved_inventory = resolve_inventory_path(proj, inventory_file)

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

        run_playbook_on_vagrant_host(
            playbook=resolved_playbook,
            project_dir=proj,
            ssh=cfg,
            inventory_file=resolved_inventory,
            extravars=extravars,
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
