"""浏览器缓存与诊断日志清理器。"""
from __future__ import annotations

import glob
import os

from cleaners.base import RISK_LOW, CleanItem, Cleaner, make_dir_item


class BrowserLogsCleaner(Cleaner):
    id = "browser_logs"
    display_name = "浏览器与诊断日志"

    def scan(self) -> list[CleanItem]:
        items: list[CleanItem] = []
        items.extend(self._scan_chromium_caches())
        items.extend(self._scan_firefox_caches())
        items.extend(self._scan_wer_reports())
        items.extend(self._scan_crash_dumps())
        return items

    def _scan_chromium_caches(self) -> list[CleanItem]:
        """Chrome/Edge 的 Cache|Code Cache|GPUCache。"""
        la = self.p("local_appdata", "LOCALAPPDATA")
        if not la:
            return []
        items: list[CleanItem] = []
        for base in (
            os.path.join(la, "Google", "Chrome", "User Data"),
            os.path.join(la, "Microsoft", "Edge", "User Data"),
        ):
            for sub in ("Cache", "Code Cache", "GPUCache"):
                for path in glob.glob(os.path.join(base, "*", sub)):
                    item = make_dir_item(path, self.id, f"浏览器缓存 {path}", RISK_LOW, False)
                    if item:
                        items.append(item)
        return items

    def _scan_firefox_caches(self) -> list[CleanItem]:
        """Firefox 的 cache2|startupCache。"""
        la = self.p("local_appdata", "LOCALAPPDATA")
        if not la:
            return []
        items: list[CleanItem] = []
        profiles = os.path.join(la, "Mozilla", "Firefox", "Profiles")
        for sub in ("cache2", "startupCache"):
            for path in glob.glob(os.path.join(profiles, "*", sub)):
                item = make_dir_item(path, self.id, f"Firefox 缓存 {path}", RISK_LOW, False)
                if item:
                    items.append(item)
        return items

    def _scan_wer_reports(self) -> list[CleanItem]:
        """Windows 错误报告 ReportArchive|ReportQueue。"""
        pd = self.p("program_data", "ProgramData")
        if not pd:
            return []
        items: list[CleanItem] = []
        for sub in ("ReportArchive", "ReportQueue"):
            wer = os.path.join(pd, "Microsoft", "Windows", "WER", sub)
            item = make_dir_item(wer, self.id, f"Windows 错误报告 {wer}", RISK_LOW, False)
            if item:
                items.append(item)
        return items

    def _scan_crash_dumps(self) -> list[CleanItem]:
        """崩溃转储 CrashDumps。"""
        la = self.p("local_appdata", "LOCALAPPDATA")
        if not la:
            return []
        cd = os.path.join(la, "CrashDumps")
        item = make_dir_item(cd, self.id, f"崩溃转储 {cd}", RISK_LOW, False)
        return [item] if item else []
