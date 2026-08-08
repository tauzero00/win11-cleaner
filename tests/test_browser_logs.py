"""BrowserLogsCleaner 扫描测试（root_overrides 注入假路径）。"""
from cleaners.browser_logs import BrowserLogsCleaner


def _build_cleaner(tmp_path) -> BrowserLogsCleaner:
    return BrowserLogsCleaner(
        root_overrides={"local_appdata": str(tmp_path / "LA"), "program_data": str(tmp_path / "PD")}
    )


def _find(items, path):
    for i in items:
        if i.path == str(path):
            return i
    return None


def _assert_low_risk_item(item):
    """CleanItem 契约：低风险、永久删除、非仅删内容、目录非空。"""
    assert item.cleaner_id == "browser_logs"
    assert item.risk == "low"
    assert item.to_recycle is False
    assert item.delete_contents_only is False
    assert item.size > 0
    assert item.file_count > 0


def test_scan_chrome_cache(tmp_path):
    la = tmp_path / "LA"
    cache = la / "Google" / "Chrome" / "User Data" / "Default" / "Cache"
    cache.mkdir(parents=True)
    (cache / "f_000001").write_bytes(b"\x00" * 7)
    item = _find(_build_cleaner(tmp_path).scan(), cache)
    assert item is not None
    _assert_low_risk_item(item)


def test_scan_chrome_code_cache_and_gpu_cache(tmp_path):
    la = tmp_path / "LA"
    base = la / "Google" / "Chrome" / "User Data" / "Default"
    (base / "Code Cache").mkdir(parents=True)
    (base / "Code Cache" / "js").write_text("x")
    (base / "GPUCache").mkdir()
    (base / "GPUCache" / "data_0").write_bytes(b"\x00" * 3)
    items = _build_cleaner(tmp_path).scan()
    assert _find(items, base / "Code Cache") is not None
    assert _find(items, base / "GPUCache") is not None


def test_scan_edge_cache(tmp_path):
    la = tmp_path / "LA"
    cache = la / "Microsoft" / "Edge" / "User Data" / "Default" / "Cache"
    cache.mkdir(parents=True)
    (cache / "f_000002").write_bytes(b"\x00" * 9)
    item = _find(_build_cleaner(tmp_path).scan(), cache)
    assert item is not None
    _assert_low_risk_item(item)


def test_scan_firefox_cache2(tmp_path):
    la = tmp_path / "LA"
    cache2 = la / "Mozilla" / "Firefox" / "Profiles" / "abc.default" / "cache2"
    cache2.mkdir(parents=True)
    (cache2 / "entry").write_text("x")
    item = _find(_build_cleaner(tmp_path).scan(), cache2)
    assert item is not None
    _assert_low_risk_item(item)


def test_scan_firefox_startup_cache(tmp_path):
    la = tmp_path / "LA"
    startup = la / "Mozilla" / "Firefox" / "Profiles" / "abc.default" / "startupCache"
    startup.mkdir(parents=True)
    (startup / "scriptCache.bin").write_bytes(b"\x00" * 2)
    items = _build_cleaner(tmp_path).scan()
    assert _find(items, startup) is not None


def test_scan_wer_reportarchive(tmp_path):
    pd = tmp_path / "PD"
    wer = pd / "Microsoft" / "Windows" / "WER" / "ReportArchive"
    wer.mkdir(parents=True)
    (wer / "report.wer").write_text("wer")
    item = _find(_build_cleaner(tmp_path).scan(), wer)
    assert item is not None
    _assert_low_risk_item(item)


def test_scan_wer_reportqueue(tmp_path):
    pd = tmp_path / "PD"
    queue = pd / "Microsoft" / "Windows" / "WER" / "ReportQueue"
    queue.mkdir(parents=True)
    (queue / "report.wer").write_text("wer")
    items = _build_cleaner(tmp_path).scan()
    assert _find(items, queue) is not None


def test_scan_crashdumps(tmp_path):
    la = tmp_path / "LA"
    cd = la / "CrashDumps"
    cd.mkdir(parents=True)
    (cd / "app.exe.dmp").write_bytes(b"\x00" * 3)
    item = _find(_build_cleaner(tmp_path).scan(), cd)
    assert item is not None
    _assert_low_risk_item(item)


def test_scan_empty_cache_dir_skipped(tmp_path):
    """glob 命中但目录为空：make_dir_item 返回 None，不产生项。"""
    la = tmp_path / "LA"
    cache = la / "Google" / "Chrome" / "User Data" / "Default" / "Cache"
    cache.mkdir(parents=True)  # 目录存在但没有任何文件
    items = _build_cleaner(tmp_path).scan()
    assert _find(items, cache) is None


def test_scan_all_missing_returns_empty(tmp_path):
    c = BrowserLogsCleaner(root_overrides={"local_appdata": str(tmp_path / "缺"), "program_data": str(tmp_path / "PD缺")})
    assert c.scan() == []
