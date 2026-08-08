"""清理器注册表。"""
from cleaners.browser_logs import BrowserLogsCleaner
from cleaners.orphan_remnants import OrphanRemnantsCleaner
from cleaners.temp_files import TempFilesCleaner
from cleaners.update_cache import UpdateCacheCleaner


def get_cleaners() -> list:
    """返回全部清理器实例（界面按此顺序展示）。"""
    return [
        TempFilesCleaner(),
        UpdateCacheCleaner(),
        BrowserLogsCleaner(),
        OrphanRemnantsCleaner(),
    ]
