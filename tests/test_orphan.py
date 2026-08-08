"""孤儿目录检测测试（纯函数 + cleaner 集成）。"""
import os

from cleaners.orphan_remnants import OrphanRemnantsCleaner, detect_orphans, normalize


def test_normalize():
    assert normalize("Google Chrome") == "googlechrome"
    assert normalize("Intel(R) Wireless 123") == "intelrwireless123"


def test_normalize_cjk():
    """CJK 字符保留——normalize 只去非字母数字，不删除 CJK。"""
    assert normalize("腾讯QQ") == "腾讯qq"
    assert normalize("한글") == "한글"


def test_detect_orphans_marks_unmatched(tmp_path):
    root = tmp_path / "PF"
    root.mkdir()
    (root / "OldBrokenApp").mkdir()
    (root / "Adobe Photoshop").mkdir()
    (root / "InstalledApp").mkdir()
    for d in ("OldBrokenApp", "Adobe Photoshop", "InstalledApp"):
        (root / d / "data.bin").write_bytes(b"\x00" * 4)
    items = detect_orphans(
        installed_names=["Adobe Photoshop 2026", "InstalledApp"],
        root_dirs=[str(root)],
        cleaner_id="orphan_remnants",
    )
    paths = [i.path for i in items]
    assert any(p.endswith("OldBrokenApp") for p in paths)   # 无匹配 → 残留
    assert not any(p.endswith("InstalledApp") for p in paths)  # 完全匹配 → 非残留
    assert not any(p.endswith("Adobe Photoshop") for p in paths)  # 子串匹配 → 非残留


def test_detect_orphans_whitelist(tmp_path):
    root = tmp_path / "PF"
    root.mkdir()
    for name in (
        "Common Files", "Internet Explorer", "Windows Kits",
        "Application Data", "Local Settings",  # Windows 遗留 junction
        "AppWithData",
    ):
        d = root / name
        d.mkdir()
        (d / "f").write_text("x")
    items = detect_orphans(
        installed_names=["AppWithData"],
        root_dirs=[str(root)],
        cleaner_id="orphan_remnants",
    )
    paths = [i.path for i in items]
    assert paths == []  # 白名单 + 已安装，全部排除


def test_detect_orphans_fuzzy_match(tmp_path):
    root = tmp_path / "PF"
    root.mkdir()
    (root / "InstaledAp").mkdir()  # 轻微拼写差异
    (root / "InstaledAp" / "data").write_text("x")
    items = detect_orphans(
        installed_names=["InstalledApp"],
        root_dirs=[str(root)],
        cleaner_id="orphan_remnants",
    )
    assert items == []  # fuzzy ratio >= 0.6 → 非残留


def test_detect_orphans_skips_files_and_empty_dirs(tmp_path):
    root = tmp_path / "PF"
    root.mkdir()
    (root / "notes.txt").write_text("not a dir")
    (root / "EmptyDir").mkdir()
    items = detect_orphans(
        installed_names=["Whatever"],
        root_dirs=[str(root)],
        cleaner_id="orphan_remnants",
    )
    assert items == []


def test_detect_orphans_empty_norm_name_not_matched(tmp_path):
    """installed_names 含 "!!!" 时 normalize 得空串，不应误匹配而漏报残留。"""
    root = tmp_path / "PF"
    root.mkdir()
    orphan = root / "RealOrphanApp"
    orphan.mkdir()
    (orphan / "data").write_text("x")
    items = detect_orphans(
        installed_names=["!!!", "KnownApp"],
        root_dirs=[str(root)],
        cleaner_id="orphan_remnants",
    )
    assert any(i.path == str(orphan) for i in items)


def test_detect_orphans_special_chars_dir_skipped(tmp_path):
    """目录名全为特殊字符（"!!!"）且非空 → not nname 路径跳过。"""
    root = tmp_path / "PF"
    root.mkdir()
    special = root / "!!!"
    special.mkdir()
    (special / "f").write_text("x")
    items = detect_orphans(
        installed_names=["Whatever"],
        root_dirs=[str(root)],
        cleaner_id="orphan_remnants",
    )
    assert items == []


def test_permission_error_on_listdir_skipped(tmp_path, monkeypatch):
    """os.listdir 抛 PermissionError 时该 root 被跳过，不中断扫描。"""
    root = tmp_path / "PF"
    root.mkdir()

    class FailListDir:
        called = False

        def __call__(self, path):
            raise PermissionError("EACCES")

    fail = FailListDir()
    monkeypatch.setattr(os, "listdir", fail)
    items = detect_orphans(
        installed_names=["App"],
        root_dirs=[str(root)],
        cleaner_id="orphan_remnants",
    )
    assert items == []


def test_cleaner_scan_with_fake_installed_names(tmp_path):
    root = tmp_path / "PF"
    root.mkdir()
    orphan = root / "DeadApp"
    orphan.mkdir()
    (orphan / "x").write_text("y")
    c = OrphanRemnantsCleaner(
        root_overrides={
            "ProgramFiles": str(root),
            "ProgramFiles(x86)": str(tmp_path / "缺"),
            "ProgramData": str(tmp_path / "缺2"),
            "LOCALAPPDATA": str(tmp_path / "缺3"),
            "APPDATA": str(tmp_path / "缺4"),
            "installed_names": ["LiveApp"],
        }
    )
    items = c.scan()
    assert any(i.path == str(orphan) for i in items)
    assert all(i.risk == "high" for i in items)
    assert all(i.to_recycle is True for i in items)
