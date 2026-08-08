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
        la = self.p("local_appdata", "LOCALAPPDATA")
        pd = self.p("program_data", "ProgramData")

        # 浏览器缓存：chrome/edge 的 Cache|Code Cache|GPUCache，firefox 的 cache2|startupCache
        for base in (
            os.path.join(la, "Google", "Chrome", "User Data") if la else None,
            os.path.join(la, "Microsoft", "Edge", "User Data") if la else None,
        ):
            if base:
                for sub in ("Cache", "Code Cache", "GPUCache"):
                    for path in glob.glob(os.path.join(base, "*", sub)):
                        item = make_dir_item(path, self.id, f"浏览器缓存 {path}", RISK_LOW, False)
                        if item:
                            items.append(item)
        if la:
            firefox_profiles = os.path.join(la, "Mozilla", "Firefox", "Profiles")
            for sub in ("cache2", "startupCache"):
                for path in glob.glob(os.path.join(firefox_profiles, "*", sub)):
                    item = make_dir_item(path, self.id, f"Firefox 缓存 {path}", RISK_LOW, False)
                    if item:
                        items.append(item)

        # 诊断日志：WER 报告与崩溃转储
        if pd:
            for sub in ("ReportArchive", "ReportQueue"):
                wer = os.path.join(pd, "Microsoft", "Windows", "WER", sub)
                item = make_dir_item(wer, self.id, f"Windows 错误报告 {wer}", RISK_LOW, False)
                if item:
                    items.append(item)
        if la:
            cd = os.path.join(la, "CrashDumps")
            item = make_dir_item(cd, self.id, f"崩溃转储 {cd}", RISK_LOW, False)
            if item:
                items.append(item)

        return items
