from pathlib import Path
import os
import textwrap
import pytest

from notion_docs.config import load_config


def write_yaml(p: Path, content: str) -> None:
    p.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")


def test_load_config_from_file_success(tmp_path, monkeypatch):
    cfg_path = tmp_path / "notion-docs.yaml"
    write_yaml(
        cfg_path,
        """
        root: ./src
        root_page_id: 1234567890abcdef
        """,
    )
    monkeypatch.setenv("NOTION_API_KEY", "secret-key")

    cfg = load_config(str(cfg_path))
    assert cfg.root == "./src"
    assert cfg.root_page_id == "1234567890abcdef"
    assert cfg.api_key == "secret-key"


def test_load_config_from_dir_success(tmp_path, monkeypatch):
    cfg_path = tmp_path / "notion-docs.yml"
    write_yaml(
        cfg_path,
        """
        root: ./
        root_page_id: root-page
        """,
    )
    monkeypatch.setenv("NOTION_API_KEY", "another-secret")

    cfg = load_config(str(tmp_path))
    assert cfg.root == "./"
    assert cfg.root_page_id == "root-page"
    assert cfg.api_key == "another-secret"


def test_missing_root_page_id_raises(tmp_path, monkeypatch):
    cfg_path = tmp_path / "notion-docs.yaml"
    write_yaml(
        cfg_path,
        """
        root: ./
        """,
    )
    monkeypatch.setenv("NOTION_API_KEY", "secret")
    with pytest.raises(ValueError):
        load_config(str(cfg_path))


def test_missing_api_key_raises(tmp_path, monkeypatch):
    cfg_path = tmp_path / "notion-docs.yaml"
    write_yaml(
        cfg_path,
        """
        root: ./
        root_page_id: abc
        """,
    )
    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    with pytest.raises(ValueError):
        load_config(str(cfg_path))


