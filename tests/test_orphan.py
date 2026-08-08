"""孤儿目录检测测试（纯函数 + cleaner 集成）。"""
import os
import time

from cleaners.orphan_remnants import OrphanRemnantsCleaner, detect_orphans, normalize


def _set_mtime(path, days_ago):
    """把文件修改时间设为 days_ago 天前（残留判定依赖活跃性）。"""
    t = time.time() - days_ago * 86400
    os.utime(path, (t, t))


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
        f = root / d / "data.bin"
        f.write_bytes(b"\x00" * 4)
        _set_mtime(f, 400)  # 残留必须长期无活动；已匹配目录不受活跃性影响
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
    f = orphan / "data"
    f.write_text("x")
    _set_mtime(f, 400)  # 长期无活动才符合残留
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
    f = orphan / "x"
    f.write_text("y")
    _set_mtime(f, 400)
    c = OrphanRemnantsCleaner(
        root_overrides={
            "ProgramFiles": str(root),
            "ProgramFiles(x86)": str(tmp_path / "缺"),
            "ProgramData": str(tmp_path / "缺2"),
            "LOCALAPPDATA": str(tmp_path / "缺3"),
            "APPDATA": str(tmp_path / "缺4"),
            "installed_names": ["LiveApp"],
            "installed_locations": [],
        }
    )
    items = c.scan()
    assert any(i.path == str(orphan) for i in items)
    assert all(i.risk == "high" for i in items)
    assert all(i.to_recycle is True for i in items)


def test_detect_orphans_token_match(tmp_path):
    """目录名含 Corporation 等后缀词时按词元匹配已安装程序（NVIDIA Corporation）。"""
    root = tmp_path / "PF"
    root.mkdir()
    (root / "NVIDIA Corporation").mkdir()
    (root / "NVIDIA Corporation" / "data.bin").write_bytes(b"\x00" * 4)
    items = detect_orphans(
        installed_names=["NVIDIA 图形驱动程序 610.62"],
        root_dirs=[str(root)],
        cleaner_id="orphan_remnants",
    )
    assert items == []


def test_detect_orphans_install_location(tmp_path):
    """候选目录是某已安装程序 InstallLocation 的父目录时不算残留（Tencent 微信）。"""
    root = tmp_path / "PF"
    root.mkdir()
    vendor = root / "Tencent"
    (vendor / "WeChat").mkdir(parents=True)
    (vendor / "WeChat" / "x.exe").write_text("x")
    items = detect_orphans(
        installed_names=["微信"],
        installed_locations=[str(vendor / "WeChat")],
        root_dirs=[str(root)],
        cleaner_id="orphan_remnants",
    )
    assert items == []


def test_detect_orphans_recent_activity_excluded(tmp_path):
    """目录树内 180 天内有文件修改 → 视为在用，不算残留（PotPlayer/vivo 套件场景）。"""
    root = tmp_path / "PF"
    root.mkdir()
    d = root / "PotPlayerVendor"
    f = d / "data.bin"
    f.parent.mkdir()
    f.write_bytes(b"\x00" * 4)
    _set_mtime(f, 30)
    items = detect_orphans(
        installed_names=["UnrelatedApp"],
        root_dirs=[str(root)],
        cleaner_id="orphan_remnants",
    )
    assert items == []


def test_detect_orphans_inactive_old_flagged(tmp_path):
    """目录树长期无活动（400 天）→ 仍是残留，活跃性检查不误杀真残留。"""
    root = tmp_path / "PF"
    root.mkdir()
    d = root / "DeadOldApp"
    f = d / "data.bin"
    f.parent.mkdir()
    f.write_bytes(b"\x00" * 4)
    _set_mtime(f, 400)
    items = detect_orphans(
        installed_names=["UnrelatedApp"],
        root_dirs=[str(root)],
        cleaner_id="orphan_remnants",
    )
    assert [i.path for i in items] == [str(d)]


def test_detect_orphans_running_process_excluded(tmp_path):
    """目录下有正在运行的进程 → 不算残留。"""
    root = tmp_path / "PF"
    root.mkdir()
    d = root / "AppInUse"
    f = d / "app.exe"
    f.parent.mkdir()
    f.write_bytes(b"\x00" * 4)
    _set_mtime(f, 400)  # 即使很久没活动，有进程在跑也不是残留
    items = detect_orphans(
        installed_names=["Whatever"],
        root_dirs=[str(root)],
        cleaner_id="orphan_remnants",
        running_paths=[str(f)],
    )
    assert items == []


def test_detect_orphans_subdir_matches_installed(tmp_path):
    """候选目录的子目录名是已装程序名 → 不算残留（DAUM/PotPlayer、Tencent/TIM）。"""
    root = tmp_path / "PF"
    root.mkdir()
    vendor = root / "Tencent"
    (vendor / "TIM").mkdir(parents=True)
    (vendor / "TIM" / "x.exe").write_text("x")
    items = detect_orphans(
        installed_names=["TIM"],
        root_dirs=[str(root)],
        cleaner_id="orphan_remnants",
    )
    assert items == []


def test_detect_orphans_subdir_generic_dir_not_exempt(tmp_path):
    """子目录是 extensions/resources 等基础设施目录 → 不豁免（Electron 残留仍会被标记）。"""
    root = tmp_path / "PF"
    root.mkdir()
    d = root / "DeadElectronApp"
    (d / "extensions").mkdir(parents=True)
    f = d / "extensions" / "x.bin"
    f.write_bytes(b"\x00" * 4)
    _set_mtime(f, 400)
    items = detect_orphans(
        installed_names=["Google Chrome", "Windows Desktop Extensions SDK"],
        root_dirs=[str(root)],
        cleaner_id="orphan_remnants",
    )
    assert [i.path for i in items] == [str(d)]


def test_cleaner_scan_running_paths_override(tmp_path):
    """scan() 接受 root_overrides["running_paths"]，不触发真实进程枚举。"""
    root = tmp_path / "PF"
    root.mkdir()
    d = root / "InUse"
    f = d / "app.exe"
    f.parent.mkdir()
    f.write_bytes(b"\x00" * 4)
    _set_mtime(f, 400)
    c = OrphanRemnantsCleaner(
        root_overrides={
            "ProgramFiles": str(root),
            "ProgramFiles(x86)": str(tmp_path / "缺"),
            "installed_names": [],
            "installed_locations": [],
            "running_paths": [str(f)],
        }
    )
    assert c.scan() == []


def test_cleaner_scan_ignores_appdata_roots(tmp_path):
    """扫描根仅限 Program Files / Program Files (x86)；AppData 数据目录不算残留。"""
    pf = tmp_path / "PF"
    pf.mkdir()
    dead = pf / "DeadApp"
    dead.mkdir()
    f = dead / "x"
    f.write_text("y")
    _set_mtime(f, 400)
    la = tmp_path / "LA"
    la.mkdir()
    (la / "LiveAppData").mkdir()
    (la / "LiveAppData" / "f").write_text("x")
    pd = tmp_path / "PD"
    pd.mkdir()
    (pd / "VendorData").mkdir()
    (pd / "VendorData" / "f").write_text("x")
    c = OrphanRemnantsCleaner(
        root_overrides={
            "ProgramFiles": str(pf),
            "ProgramFiles(x86)": str(tmp_path / "缺"),
            "ProgramData": str(pd),
            "LOCALAPPDATA": str(la),
            "APPDATA": str(tmp_path / "缺2"),
            "installed_names": [],
            "installed_locations": [],
        }
    )
    paths = [i.path for i in c.scan()]
    assert any(p.endswith("DeadApp") for p in paths)
    assert not any("LiveAppData" in p for p in paths)  # LOCALAPPDATA 不再扫描
    assert not any("VendorData" in p for p in paths)   # ProgramData 不再扫描
