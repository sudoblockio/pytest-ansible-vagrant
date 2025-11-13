from __future__ import annotations

import os
import shutil
from typing import Any

import pytest
import yaml


def require_bins(*bins: str) -> None:
    missing = [b for b in bins if shutil.which(b) is None]
    if missing:
        raise RuntimeError("Missing required binaries: " + ", ".join(missing))


def infer_project_dir_from_request(request: pytest.FixtureRequest) -> str:
    """
    Walk up from the test file until 'tests/' is found, then return its parent.
    Fallback: parent-of-parent of the test file.
    """
    test_file = os.path.abspath(str(request.fspath))
    cur = os.path.dirname(test_file)
    while True:
        if os.path.basename(cur) == "tests":
            return os.path.dirname(cur)
        parent = os.path.dirname(cur)
        if parent == cur:
            return os.path.dirname(os.path.dirname(test_file))
        cur = parent


def resolve_playbook_path(project_dir: str, playbook: str) -> str:
    """
    If playbook is absolute and exists -> return it.
    Else treat as relative to project_dir.
    """
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


def resolve_inventory_path(project_dir: str, inventory_file: str | None) -> str | None:
    """
    If a path is provided and exists (absolute or relative to project_dir), return the path.
    If provided but not found as a file, pass through unchanged (it may be a host-list string).
    If not provided, return None.
    """
    if not inventory_file:
        return None
    if os.path.isabs(inventory_file):
        return inventory_file
    candidate = os.path.join(project_dir, inventory_file)
    return candidate if os.path.exists(candidate) else inventory_file


def extract_play_hosts(playbook_path: str) -> list[str]:
    """
    Minimal YAML parser to extract unique `hosts` patterns from a playbook.
    Returns an ordered list of unique patterns. Empty if none.
    """
    with open(playbook_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    plays: list[dict[str, Any]]
    if isinstance(data, list):
        plays = [p for p in data if isinstance(p, dict)]
    elif isinstance(data, dict):
        plays = [data]
    else:
        return []

    seen: set[str] = set()
    out: list[str] = []
    for p in plays:
        h = p.get("hosts")
        if isinstance(h, str):
            hv = h.strip()
            if hv and hv not in seen:
                seen.add(hv)
                out.append(hv)
    return out
