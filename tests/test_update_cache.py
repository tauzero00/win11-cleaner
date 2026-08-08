"""UpdateCacheCleaner 扫描测试（root_overrides 注入假路径）。"""
from cleaners.update_cache import UpdateCacheCleaner


def test_scan_download_dir(tmp_path):
    root = tmp_path / "Windows"
    dl = root / "SoftwareDistribution" / "Download"
    dl.mkdir(parents=True)
    (dl / "cab.cab").write_bytes(b"\x00" * 5)
    c = UpdateCacheCleaner(root_overrides={"system_root": str(root), "program_data": str(tmp_path / "PD")})
    items = c.scan()
    item = next(i for i in items if "SoftwareDistribution" in i.path)
    assert item.path == str(dl)
    assert item.risk == "medium"
    assert item.to_recycle is False
    assert item.checked is True


def test_scan_windows_old_off_by_default(tmp_path):
    root = tmp_path / "Windows"
    root.mkdir()
    wold = tmp_path / "Windows.old"
    wold.mkdir()
    (wold / "x").write_text("old system")
    c = UpdateCacheCleaner(
        root_overrides={
            "system_root": str(root),
            "program_data": str(tmp_path / "PD"),
            "windows_old": str(wold),
        }
    )
    items = c.scan()
    item = next(i for i in items if i.path == str(wold))
    assert item.risk == "high"
    assert item.checked is False


def test_scan_delivery_optimization_network_service(tmp_path):
    root = tmp_path / "Windows"
    do_cache = (
        root / "ServiceProfiles" / "NetworkService" / "AppData" / "Local"
        / "Microsoft" / "Windows" / "DeliveryOptimization" / "Cache"
    )
    do_cache.mkdir(parents=True)
    (do_cache / "blob").write_text("data")
    c = UpdateCacheCleaner(
        root_overrides={
            "system_root": str(root),
            "program_data": str(tmp_path / "PD"),
        }
    )
    items = c.scan()
    assert any(i.path == str(do_cache) for i in items)


def test_scan_delivery_optimization_programdata_fallback(tmp_path):
    root = tmp_path / "Windows"
    root.mkdir()
    pd_do = tmp_path / "PD" / "Microsoft" / "Windows" / "DeliveryOptimization"
    pd_do.mkdir(parents=True)
    (pd_do / "blob").write_text("data")
    c = UpdateCacheCleaner(
        root_overrides={
            "system_root": str(root),
            "program_data": str(tmp_path / "PD"),
        }
    )
    items = c.scan()
    assert any(i.path == str(pd_do) for i in items)


def test_scan_all_missing_returns_empty(tmp_path):
    c = UpdateCacheCleaner(
        root_overrides={
            "system_root": str(tmp_path / "缺"),
            "program_data": str(tmp_path / "PD缺"),
            "windows_old": str(tmp_path / "缺_windows_old"),
        }
    )
    assert c.scan() == []
