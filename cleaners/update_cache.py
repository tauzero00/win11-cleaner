"""更新缓存与旧系统残留清理器。"""
from __future__ import annotations

import os

from cleaners.base import RISK_HIGH, RISK_MEDIUM, CleanItem, Cleaner, make_dir_item


class UpdateCacheCleaner(Cleaner):
    id = "update_cache"
    display_name = "更新与旧系统残留"

    def scan(self) -> list[CleanItem]:
        items: list[CleanItem] = []
        items.extend(self._scan_download_dir())
        items.extend(self._scan_delivery_optimization())
        items.extend(self._scan_windows_old())
        return items

    def _system_root(self) -> str:
        return self.p("system_root", "SystemRoot") or "C:\\Windows"

    def _scan_download_dir(self) -> list[CleanItem]:
        path = os.path.join(self._system_root(), "SoftwareDistribution", "Download")
        item = make_dir_item(path, self.id, f"Windows 更新下载缓存 {path}", RISK_MEDIUM, False)
        return [item] if item else []

    def _scan_delivery_optimization(self) -> list[CleanItem]:
        ns_cache = os.path.join(
            self._system_root(), "ServiceProfiles", "NetworkService", "AppData", "Local",
            "Microsoft", "Windows", "DeliveryOptimization", "Cache",
        )
        if os.path.isdir(ns_cache):
            item = make_dir_item(ns_cache, self.id, f"传递优化缓存 {ns_cache}", RISK_MEDIUM, False)
            return [item] if item else []
        pd = self.p("program_data", "ProgramData")
        if pd:
            pd_do = os.path.join(pd, "Microsoft", "Windows", "DeliveryOptimization")
            item = make_dir_item(pd_do, self.id, f"传递优化缓存 {pd_do}", RISK_MEDIUM, False)
            return [item] if item else []
        return []

    def _scan_windows_old(self) -> list[CleanItem]:
        path = self.p("windows_old") or "C:\\Windows.old"
        item = make_dir_item(path, self.id, f"旧系统文件 Windows.old（{path}）", RISK_HIGH, False)
        if item:
            item.checked = False  # 高风险，默认不勾选，需用户明确选择
        return [item] if item else []
