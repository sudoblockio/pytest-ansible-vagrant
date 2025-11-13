from __future__ import annotations

from typing import Generator

import pytest

from pytest_ansible_vagrant.runner import ShutdownMode, VagrantRunner, destroy, halt


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addini(
        "vagrant_shutdown",
        "Vagrant shutdown behavior (halt|destroy|none).",
        default=ShutdownMode.DESTROY.value,
    )
    parser.addini(
        "vagrant_file",
        "Path to the Vagrantfile.",
        default="Vagrantfile",
    )
    parser.addini(
        "vagrant_project_dir",
        "Base project directory; if omitted it is inferred as the parent of the nearest `tests/` directory.",
        default="",
    )
    parser.addini(
        "vagrant_artifact_dir",
        "Directory to store artifacts from ansible run.",
        default="",
    )

    grp = parser.getgroup("vagrant")
    grp.addoption(
        "--vagrant-file",
        action="store",
        dest="vagrant_file",
        help="Path to the Vagrantfile",
    )
    grp.addoption(
        "--vagrant-shutdown",
        action="store",
        dest="vagrant_shutdown",
        choices=[m.value for m in ShutdownMode],
        help="Shutdown behavior after tests: halt|destroy|none",
    )
    grp.addoption(
        "--vagrant-project-dir",
        action="store",
        dest="vagrant_project_dir",
        help="Base directory containing roles/ and tests/",
    )
    grp.addoption(
        "--vagrant-artifact-dir",
        action="store",
        dest="vagrant_artifact_dir",
        help="Directory to store artifacts from ansible run.",
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


@pytest.fixture(scope="module")
def vagrant_runner(
    request: pytest.FixtureRequest,
) -> Generator[VagrantRunner, None, None]:
    runner = VagrantRunner(request)
    try:
        yield runner
    finally:
        vf_abs = runner.vagrantfile
        if not vf_abs:
            return
        mode = _resolve_shutdown_mode(request.config)
        if mode is ShutdownMode.HALT:
            halt(vf_abs)
        elif mode is ShutdownMode.DESTROY:
            destroy(vf_abs)
        elif mode is ShutdownMode.NONE:
            pass
