import json
import os
from dataclasses import dataclass
from typing import Optional, Dict

import yaml


YAML_FILES = [
    "notion-docs.yaml",
    "notion-docs.yml",
]


@dataclass
class AppConfig:
    root: str
    root_page_id: str
    api_key: str


def _load_yaml(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config(path_or_dir: Optional[str] = None) -> AppConfig:
    """Load configuration from YAML.

    If path_or_dir is a file, load that file. If it's a directory (or None),
    search for a known YAML config name in that directory.
    """
    print(f"Loading config from {path_or_dir}")
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
    root_page_id_raw = data.get("root_page_id")
    if root_page_id_raw is None:
        raise ValueError("Config 'root_page_id' must be set")
    root_page_id = str(root_page_id_raw).strip()
    if not root_page_id:
        raise ValueError("Config 'root_page_id' must be a non-empty string")

    api_key = os.environ.get("NOTION_API_KEY")
    if not api_key:
        raise ValueError("Environment variable NOTION_API_KEY must be set")

    return AppConfig(root=root, root_page_id=root_page_id, api_key=api_key)


