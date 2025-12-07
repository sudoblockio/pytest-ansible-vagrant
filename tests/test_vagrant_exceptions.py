"""Tests for exception classes."""

import pytest

from pytest_ansible_vagrant import (
    VagrantError,
    VagrantfileNotFound,
    VagrantCommandFailed,
    PlaybookNotFound,
    PlaybookFailed,
    InvalidProjectLayout,
    SSHConfigError,
    HostNotFound,
)


def test_vagrant_error_is_exception():
    assert issubclass(VagrantError, Exception)


def test_vagrantfile_not_found_inherits():
    assert issubclass(VagrantfileNotFound, VagrantError)


def test_vagrant_command_failed_inherits():
    assert issubclass(VagrantCommandFailed, VagrantError)


def test_playbook_not_found_inherits():
    assert issubclass(PlaybookNotFound, VagrantError)


def test_playbook_failed_inherits():
    assert issubclass(PlaybookFailed, VagrantError)


def test_invalid_project_layout_inherits():
    assert issubclass(InvalidProjectLayout, VagrantError)


def test_ssh_config_error_inherits():
    assert issubclass(SSHConfigError, VagrantError)


def test_host_not_found_inherits():
    assert issubclass(HostNotFound, VagrantError)


def test_vagrant_error_message():
    err = VagrantError("Something went wrong")
    assert str(err) == "Something went wrong"


def test_vagrantfile_not_found_message():
    err = VagrantfileNotFound("Vagrantfile not found: /path/to/Vagrantfile")
    assert "/path/to/Vagrantfile" in str(err)


def test_playbook_failed_message():
    err = PlaybookFailed("Playbook failed with rc=1")
    assert "rc=1" in str(err)
    assert isinstance(err, VagrantError)


def test_host_not_found_message():
    err = HostNotFound("Host 'web' not found. Available: ['db']")
    assert "web" in str(err)
    assert "db" in str(err)


def test_raise_and_catch_as_base():
    with pytest.raises(VagrantError):
        raise VagrantfileNotFound("should be caught as base")

    with pytest.raises(VagrantError):
        raise PlaybookFailed("should be caught as base")

    with pytest.raises(VagrantError):
        raise HostNotFound("should be caught as base")
