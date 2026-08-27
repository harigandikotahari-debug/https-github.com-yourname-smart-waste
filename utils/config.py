"""Central config loader. Reads config/settings.yaml once and caches it."""
from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.yaml"


@functools.lru_cache(maxsize=1)
def get_settings() -> dict[str, Any]:
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get(path: str, default: Any = None) -> Any:
    """Dotted-path lookup, e.g. get('priority_weights.fill_level')."""
    node: Any = get_settings()
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def waste_categories() -> dict[str, dict]:
    return get_settings()["waste_categories"]


def db_url() -> str:
    url = get_settings()["database"]["url"]
    if url.startswith("sqlite:///./"):
        # Resolve relative sqlite paths against the project root regardless
        # of the process's current working directory.
        rel = url.replace("sqlite:///./", "")
        abs_path = (PROJECT_ROOT / rel).as_posix()
        return f"sqlite:///{abs_path}"
    return url
