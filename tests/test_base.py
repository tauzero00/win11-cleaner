"""CleanItem 与 make_dir_item 的测试。"""
import os

import pytest

from cleaners.base import Cleaner, CleanItem, make_dir_item


def test_cleanitem_defaults():
    item = CleanItem(path=r"C:\x", cleaner_id="t", label="测试", size=100)
    assert item.file_count == 0
    assert item.risk == "low"
    assert item.to_recycle is False
    assert item.checked is True
    assert item.delete_contents_only is False


def test_make_dir_item_returns_none_for_missing():
    assert make_dir_item(r"C:\不存在的目录", "t", "x", "low", False) is None


def test_make_dir_item_empty_dir_returns_none(tmp_path):
    assert make_dir_item(str(tmp_path), "t", "x", "low", False) is None


def test_make_dir_item_counts_files(tmp_path):
    (tmp_path / "a.txt").write_text("hello")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.bin").write_bytes(b"\x00" * 10)
    item = make_dir_item(str(tmp_path), "t", "x", "low", False)
    assert item is not None
    assert item.size == 15
    assert item.file_count == 2
    assert item.allowed_prefixes == (str(tmp_path),)


def test_make_dir_item_delete_contents_only_flag(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    item = make_dir_item(str(tmp_path), "t", "x", "low", True, delete_contents_only=True)
    assert item is not None
    assert item.delete_contents_only is True


def test_cleaner_base_scan_raises():
    c = Cleaner()
    with pytest.raises(NotImplementedError):
        c.scan()


def test_cleaner_p_override_prefers_root_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv("TEMP", "C:\\fake\\env")
    c = Cleaner(root_overrides={"temp": str(tmp_path)})
    assert c.p("temp", "TEMP") == str(tmp_path)
    assert c.p("missing_key", "TEMP") == "C:\\fake\\env"
    assert c.p("another_missing") is None
