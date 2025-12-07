class VagrantError(Exception):
    """Base exception for vagrant errors."""


class VagrantfileNotFound(VagrantError):
    """Vagrantfile not found."""


class VagrantCommandFailed(VagrantError):
    """Vagrant command execution failed."""


class PlaybookNotFound(VagrantError):
    """Ansible playbook file not found."""


class PlaybookFailed(VagrantError):
    """Ansible playbook execution failed."""


class InvalidProjectLayout(VagrantError):
    """Invalid ansible project layout (missing roles/ or tests/)."""


class SSHConfigError(VagrantError):
    """Error parsing vagrant ssh-config output."""


class HostNotFound(VagrantError):
    """Requested host not found in vagrant environment."""
