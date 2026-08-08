"""目录大小计算与格式化测试。"""
import os
import subprocess

import pytest

from core.scanner import ScanWorker, dir_size, human_size


def _make_junction(link: str, target: str) -> bool:
    """用 mklink /J 创建 junction；失败（非 Windows/无权限）返回 False。"""
    r = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
    )
    return r.returncode == 0


def test_dir_size_counts_bytes_and_files(tmp_path):
    (tmp_path / "a.txt").write_text("12345")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.bin").write_bytes(b"\x00" * 10)
    size, count = dir_size(str(tmp_path))
    assert size == 15
    assert count == 2


def test_dir_size_skips_missing(tmp_path):
    size, count = dir_size(str(tmp_path / "不存在"))
    assert size == 0
    assert count == 0


def test_dir_size_skips_symlink_loop(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "f.txt").write_text("x")
    link = tmp_path / "link"
    try:
        os.symlink(target, link)
    except OSError:
        pytest.skip("无法创建符号链接（需开发者模式或管理员权限）")
    size, count = dir_size(str(tmp_path))
    assert count == 1  # 链接目录不递归


def test_dir_size_skips_junction(tmp_path):
    """Windows junction（islink 返回 False）不被递归统计。"""
    target = tmp_path / "target"
    target.mkdir()
    (target / "f.txt").write_text("x")
    link = tmp_path / "loop"
    if not _make_junction(str(link), str(target)):
        pytest.skip("无法创建 junction（非 Windows 或无权限）")
    size, count = dir_size(str(tmp_path))
    assert count == 1  # junction 目录不展开


def test_dir_size_skips_junction_self_loop(tmp_path):
    """父目录内指回父目录的 junction 自环不会陷入无限递归。"""
    root = tmp_path / "root"
    root.mkdir()
    (root / "f.txt").write_text("x")
    if not _make_junction(str(root / "loop"), str(root)):
        pytest.skip("无法创建 junction（非 Windows 或无权限）")
    size, count = dir_size(str(root))
    assert count == 1


def test_human_size():
    assert human_size(0) == "0 B"
    assert human_size(500) == "500 B"
    assert human_size(2048) == "2.0 KB"
    assert human_size(5 * 1024 * 1024) == "5.0 MB"
    assert human_size(int(1.5 * 1024 ** 3)) == "1.5 GB"


def test_scan_worker_posts_messages(tmp_path):
    import queue

    class FakeCleaner:
        id = "fake"
        display_name = "假清理器"

        def scan(self):
            return []

    q = queue.Queue()
    w = ScanWorker([FakeCleaner()], q)
    w.run()  # 同步跑完
    msgs = [q.get_nowait() for _ in range(q.qsize())]
    kinds = [m[0] for m in msgs]
    assert kinds == ["category_start", "category_done", "scan_finished"]
    assert msgs[0][1] == "fake"
    assert msgs[2][0] == "scan_finished"


def test_scan_worker_error_path(tmp_path):
    import queue

    class BadCleaner:
        id = "bad"
        display_name = "坏清理器"

        def scan(self):
            raise RuntimeError("boom")

    class GoodCleaner:
        id = "good"
        display_name = "好清理器"

        def scan(self):
            return []

    q = queue.Queue()
    ScanWorker([BadCleaner(), GoodCleaner()], q).run()
    msgs = [q.get_nowait() for _ in range(q.qsize())]
    kinds = [m[0] for m in msgs]
    assert kinds == ["category_start", "category_error", "category_start", "category_done", "scan_finished"]
    assert msgs[1][2] == "boom"
    assert msgs[4][0] == "scan_finished"
