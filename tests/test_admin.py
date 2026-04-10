"""Tests for the admin tool — config path resolution and editor selection.

No SSH connection is required; all tests are fully offline.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest import mock

import pytest
import yaml

from polymarket_watcher.admin.admin_config import (
    AdminConfig,
    default_config_path,
)
from polymarket_watcher.admin.editor import find_editor


# ---------------------------------------------------------------------------
# AdminConfig — default path resolution
# ---------------------------------------------------------------------------


class TestDefaultConfigPath:
    def test_returns_path_instance(self) -> None:
        p = default_config_path()
        assert isinstance(p, Path)

    def test_filename_is_admin_yaml(self) -> None:
        assert default_config_path().name == "admin.yaml"

    def test_parent_dir_name(self) -> None:
        assert default_config_path().parent.name == "polymarket-watcher"

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
    def test_windows_uses_appdata(self) -> None:
        with mock.patch.dict(os.environ, {"APPDATA": r"C:\Users\Test\AppData\Roaming"}):
            p = default_config_path()
        assert str(p).startswith(r"C:\Users\Test\AppData\Roaming")

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX only")
    def test_posix_uses_xdg_config_home(self, tmp_path: Path) -> None:
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path)}):
            p = default_config_path()
        assert str(p).startswith(str(tmp_path))

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX only")
    def test_posix_falls_back_to_home_config(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "XDG_CONFIG_HOME"}
        with mock.patch.dict(os.environ, env, clear=True):
            p = default_config_path()
        expected_prefix = str(Path.home() / ".config")
        assert str(p).startswith(expected_prefix)


# ---------------------------------------------------------------------------
# AdminConfig — load / save round-trip
# ---------------------------------------------------------------------------


class TestAdminConfigLoadSave:
    def test_defaults_when_file_missing(self, tmp_path: Path) -> None:
        cfg = AdminConfig.load(tmp_path / "nonexistent.yaml")
        assert cfg.host == ""
        assert cfg.user == "admin"
        assert cfg.unit == "polymarket-watcher"
        assert cfg.remote_config == "/etc/polymarket-watcher/config.yaml"
        assert cfg.remote_config_group == "polymarket-watcher"

    def test_load_from_yaml(self, tmp_path: Path) -> None:
        data = {
            "host": "192.0.2.10",
            "user": "deploy",
            "unit": "my-service",
            "remote_config": "/etc/my-service/config.yaml",
            "remote_config_group": "my-service",
        }
        cfg_file = tmp_path / "admin.yaml"
        cfg_file.write_text(yaml.dump(data))

        cfg = AdminConfig.load(cfg_file)
        assert cfg.host == "192.0.2.10"
        assert cfg.user == "deploy"
        assert cfg.unit == "my-service"
        assert cfg.remote_config == "/etc/my-service/config.yaml"
        assert cfg.remote_config_group == "my-service"

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        cfg = AdminConfig(host="10.0.0.1")
        nested = tmp_path / "a" / "b" / "admin.yaml"
        saved = cfg.save(nested)
        assert saved == nested
        assert nested.exists()

    def test_save_load_round_trip(self, tmp_path: Path) -> None:
        cfg = AdminConfig(
            host="10.0.0.2",
            user="ops",
            unit="test-unit",
            remote_config="/var/lib/svc/config.yaml",
            remote_config_group="svc-group",
            ssh_options=["-p", "2222"],
        )
        path = tmp_path / "admin.yaml"
        cfg.save(path)

        loaded = AdminConfig.load(path)
        assert loaded.host == "10.0.0.2"
        assert loaded.user == "ops"
        assert loaded.unit == "test-unit"
        assert loaded.remote_config == "/var/lib/svc/config.yaml"
        assert loaded.remote_config_group == "svc-group"
        assert loaded.ssh_options == ["-p", "2222"]

    def test_ssh_options_as_string(self, tmp_path: Path) -> None:
        """A bare string value for ssh_options is split into a list."""
        data = {"host": "h", "ssh_options": "-p 2222 -i /tmp/key"}
        cfg_file = tmp_path / "admin.yaml"
        cfg_file.write_text(yaml.dump(data))

        cfg = AdminConfig.load(cfg_file)
        assert cfg.ssh_options == ["-p", "2222", "-i", "/tmp/key"]

    def test_require_host_raises_when_empty(self) -> None:
        cfg = AdminConfig()
        with pytest.raises(RuntimeError, match="No host configured"):
            cfg.require_host()

    def test_require_host_returns_host(self) -> None:
        cfg = AdminConfig(host="example.com")
        assert cfg.require_host() == "example.com"


# ---------------------------------------------------------------------------
# Editor selection
# ---------------------------------------------------------------------------


class TestFindEditor:
    def test_env_editor_takes_priority(self) -> None:
        with mock.patch.dict(os.environ, {"EDITOR": "emacs"}):
            assert find_editor() == ["emacs"]

    def test_env_editor_multi_word(self) -> None:
        with mock.patch.dict(os.environ, {"EDITOR": "emacsclient -t"}):
            assert find_editor() == ["emacsclient", "-t"]

    def test_vscode_used_when_no_env_editor(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "EDITOR"}
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch("shutil.which", side_effect=lambda x: "/usr/bin/code" if x == "code" else None),
        ):
            assert find_editor() == ["code", "--wait"]

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
    def test_windows_notepad_fallback(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "EDITOR"}
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch("shutil.which", return_value=None),
        ):
            assert find_editor() == ["notepad"]

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX only")
    def test_posix_nano_fallback(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "EDITOR"}
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch(
                "shutil.which",
                side_effect=lambda x: "/usr/bin/nano" if x == "nano" else None,
            ),
        ):
            assert find_editor() == ["nano"]

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX only")
    def test_posix_vi_last_resort(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "EDITOR"}
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch("shutil.which", return_value=None),
        ):
            assert find_editor() == ["vi"]
