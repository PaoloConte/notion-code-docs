import json
import os
from dataclasses import dataclass
from typing import Optional, Dict

import yaml


YAML_FILES = ["notion.config.yaml", "notion.config.yml"]


@dataclass
class AppConfig:
    root: str


def _load_yaml(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config(path_or_dir: Optional[str] = None) -> AppConfig:
    """Load configuration from YAML.

    If path_or_dir is a file, load that file. If it's a directory (or None),
    search for a known YAML config name in that directory.
    """
    if path_or_dir:
        candidate = os.path.abspath(path_or_dir)
        if os.path.isdir(candidate):
            base = candidate
            data = None
            for name in YAML_FILES:
                p = os.path.join(base, name)
                if os.path.exists(p):
                    data = _load_yaml(p)
                    break
            if data is None:
                raise FileNotFoundError(
                    f"No config found in directory {base}. Create one of: {', '.join(YAML_FILES)}"
                )
        else:
            data = _load_yaml(candidate)
    else:
        base = os.getcwd()
        data = None
        for name in YAML_FILES:
            p = os.path.join(base, name)
            if os.path.exists(p):
                data = _load_yaml(p)
                break
        if data is None:
            raise FileNotFoundError(
                f"No config found. Create one of: {', '.join(YAML_FILES)}"
            )

    root = data.get("root")
    if not isinstance(root, str) or not root:
        raise ValueError("Config 'root' must be a non-empty string")
    return AppConfig(root=root)


