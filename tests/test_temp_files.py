"""TempFilesCleaner 扫描测试（root_overrides 注入假路径）。"""
from cleaners.temp_files import TempFilesCleaner


def test_scan_user_temp(tmp_path):
    user_temp = tmp_path / "user_temp"
    user_temp.mkdir()
    (user_temp / "a.txt").write_text("hello")
    c = TempFilesCleaner(
        root_overrides={
            "user_temp": str(user_temp),
            "system_temp": str(tmp_path / "缺"),
            "prefetch": str(tmp_path / "缺2"),
            "explorer_dir": str(tmp_path / "缺3"),
        }
    )
    items = c.scan()
    assert any(i.cleaner_id == "temp_files" and i.path == str(user_temp) for i in items)


def test_scan_user_temp_missing_env_treated_as_empty(monkeypatch, tmp_path):
    monkeypatch.delenv("TEMP", raising=False)
    c = TempFilesCleaner(
        root_overrides={
            "system_temp": str(tmp_path / "缺"),
            "prefetch": str(tmp_path / "缺2"),
            "explorer_dir": str(tmp_path / "缺3"),
        }
    )
    assert c.scan() == []


def test_scan_missing_dirs_skipped(tmp_path):
    c = TempFilesCleaner(
        root_overrides={
            "user_temp": str(tmp_path / "不存在"),
            "system_temp": str(tmp_path / "不存在2"),
            "prefetch": str(tmp_path / "不存在3"),
            "explorer_dir": str(tmp_path / "不存在4"),
        }
    )
    assert c.scan() == []


def test_scan_thumbcache_files(tmp_path):
    explorer = tmp_path / "Explorer"
    explorer.mkdir()
    (explorer / "thumbcache_32.db").write_bytes(b"\x00" * 100)
    (explorer / "other.txt").write_text("not cache")
    c = TempFilesCleaner(
        root_overrides={
            "user_temp": str(tmp_path / "缺"),   # 不存在，跳过
            "system_temp": str(tmp_path / "缺2"),
            "prefetch": str(tmp_path / "缺3"),
            "explorer_dir": str(explorer),
        }
    )
    items = c.scan()
    paths = [i.path for i in items]
    assert any(p.endswith("thumbcache_32.db") for p in paths)
    assert not any(p.endswith("other.txt") for p in paths)


def test_scan_system_temp_contents_only(tmp_path):
    sys_temp = tmp_path / "Windows_Temp"
    sys_temp.mkdir()
    (sys_temp / "f.tmp").write_text("x")
    c = TempFilesCleaner(
        root_overrides={
            "system_temp": str(sys_temp),
            "user_temp": str(tmp_path / "缺"),
            "prefetch": str(tmp_path / "缺2"),
            "explorer_dir": str(tmp_path / "缺3"),
        }
    )
    items = c.scan()
    item = next(i for i in items if i.path == str(sys_temp))
    assert item.delete_contents_only is True
