"""删除引擎测试：校验 + 删除 + 重试。"""
import os

import pytest

from cleaners.base import CleanItem
from core.deleter import Deleter


def make_item(path, to_recycle=False, prefixes=None, contents_only=False):
    return CleanItem(
        path=str(path),
        cleaner_id="test",
        label="测试项",
        size=10,
        file_count=1,
        allowed_prefixes=tuple(prefixes) if prefixes else (str(path),),
        to_recycle=to_recycle,
        delete_contents_only=contents_only,
    )


# ---------- 校验 ----------

def test_validate_rejects_path_outside_c_drive():
    # 构造不存在的 D 盘路径，SystemDrive=C:
    item = make_item("D:\\something", prefixes=(r"C:\allowed",))
    d = Deleter()
    assert d.validate(item) is not None


def test_validate_rejects_outside_allowed_prefix(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    item = make_item(other / "x", prefixes=(str(tmp_path / "allowed"),))
    d = Deleter()
    assert d.validate(item) is not None


def test_validate_accepts_path_in_allowed_prefix(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    item = make_item(sub / "x.txt", prefixes=(str(tmp_path),))
    d = Deleter()
    assert d.validate(item) is None


def test_validate_rejects_system32_under_windows(tmp_path):
    # 前缀允许也不行：System32 在黑名单
    p = tmp_path / "Windows" / "System32" / "config"
    item = make_item(p, prefixes=(str(tmp_path),))
    d = Deleter()
    assert d.validate(item) is not None


def test_validate_rejects_windows_dir_body():
    item = make_item(r"C:\Windows", prefixes=(r"C:\Windows",))
    d = Deleter()
    assert d.validate(item) is not None


def test_validate_rejects_running_process_dir(tmp_path):
    item = make_item(tmp_path / "x", prefixes=(str(tmp_path),))
    d = Deleter()
    # 把本进程 python.exe 的目录当作“运行中程序目录”
    proc_dir = os.path.dirname(os.sys.executable)
    d._proc_dirs = {proc_dir}
    item2 = make_item(os.path.join(proc_dir, "somefile.dll"), prefixes=(proc_dir,))
    assert d.validate(item2) is not None
    assert d.validate(item) is None  # 与进程目录无关的路径不受影响


# ---------- 删除行为 ----------

def test_delete_permanent_removes_dir(tmp_path):
    target = tmp_path / "junk"
    target.mkdir()
    (target / "f.txt").write_text("data")
    d = Deleter()
    ok, reason, freed = d.delete(make_item(target))
    assert ok is True
    assert reason == ""
    assert freed == 10
    assert not target.exists()


def test_delete_recycle_uses_send2trash(tmp_path, monkeypatch):
    target = tmp_path / "junk2"
    target.mkdir()
    sent = []

    def fake_send(path):
        sent.append(path)

    monkeypatch.setattr("send2trash.send2trash", fake_send)
    d = Deleter()
    ok, _, freed = d.delete(make_item(target, to_recycle=True))
    assert ok is True
    assert sent == [str(target)]
    assert freed == 10


def test_delete_missing_path_is_silent_success(tmp_path):
    d = Deleter()
    ok, reason, freed = d.delete(make_item(tmp_path / "不存在"))
    assert ok is True
    assert freed == 0


def test_delete_contents_only_keeps_dir(tmp_path):
    target = tmp_path / "keepdir"
    target.mkdir()
    (target / "a.txt").write_text("x")
    sub = target / "sub"
    sub.mkdir()
    (sub / "b.txt").write_text("y")
    item = make_item(target, contents_only=True)
    d = Deleter()
    ok, _, freed = d.delete(item)
    assert ok is True
    assert target.exists()          # 目录本体保留
    assert freed == 10
    assert list(target.iterdir()) == []  # 内容已清空


def test_delete_failure_returns_reason(tmp_path):
    # 命中黑名单 → 删除前被拒
    item = make_item(r"C:\Windows\System32\config", prefixes=(r"C:\Windows\System32\config",))
    d = Deleter()
    ok, reason, freed = d.delete(item)
    assert ok is False
    assert "系统关键目录" in reason
    assert freed == 0


def test_delete_contents_only_all_fail(tmp_path, monkeypatch):
    target = tmp_path / "keepdir"
    target.mkdir()
    (target / "a.txt").write_text("x")
    (target / "b.txt").write_text("y")
    item = make_item(target, contents_only=True)
    d = Deleter()
    # 让 _delete_path 始终抛异常
    monkeypatch.setattr(d, "_delete_path", lambda p: (_ for _ in ()).throw(OSError("mock")))
    ok, reason, freed = d.delete(item)
    assert ok is False
    assert "2 个子项均无法删除" in reason
    assert freed == 0
