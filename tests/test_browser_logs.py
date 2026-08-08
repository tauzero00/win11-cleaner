"""BrowserLogsCleaner 扫描测试（root_overrides 注入假路径）。"""
from cleaners.browser_logs import BrowserLogsCleaner


def test_scan_chrome_cache(tmp_path):
    la = tmp_path / "LA"
    cache = la / "Google" / "Chrome" / "User Data" / "Default" / "Cache"
    cache.mkdir(parents=True)
    (cache / "f_000001").write_bytes(b"\x00" * 7)
    c = BrowserLogsCleaner(root_overrides={"local_appdata": str(la), "program_data": str(tmp_path / "PD")})
    items = c.scan()
    assert any(i.path == str(cache) for i in items)


def test_scan_firefox_cache2(tmp_path):
    la = tmp_path / "LA"
    cache2 = la / "Mozilla" / "Firefox" / "Profiles" / "abc.default" / "cache2"
    cache2.mkdir(parents=True)
    (cache2 / "entry").write_text("x")
    c = BrowserLogsCleaner(root_overrides={"local_appdata": str(la), "program_data": str(tmp_path / "PD")})
    items = c.scan()
    assert any(i.path == str(cache2) for i in items)


def test_scan_wer_reportarchive(tmp_path):
    pd = tmp_path / "PD"
    wer = pd / "Microsoft" / "Windows" / "WER" / "ReportArchive"
    wer.mkdir(parents=True)
    (wer / "report.wer").write_text("wer")
    c = BrowserLogsCleaner(root_overrides={"local_appdata": str(tmp_path / "LA"), "program_data": str(pd)})
    items = c.scan()
    assert any(i.path == str(wer) for i in items)


def test_scan_crashdumps(tmp_path):
    la = tmp_path / "LA"
    cd = la / "CrashDumps"
    cd.mkdir(parents=True)
    (cd / "app.exe.dmp").write_bytes(b"\x00" * 3)
    c = BrowserLogsCleaner(root_overrides={"local_appdata": str(la), "program_data": str(tmp_path / "PD")})
    items = c.scan()
    assert any(i.path == str(cd) for i in items)


def test_scan_all_missing_returns_empty(tmp_path):
    c = BrowserLogsCleaner(root_overrides={"local_appdata": str(tmp_path / "缺"), "program_data": str(tmp_path / "PD缺")})
    assert c.scan() == []
