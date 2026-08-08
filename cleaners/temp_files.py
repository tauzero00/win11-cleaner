"""系统临时文件清理器。"""
from __future__ import annotations

import glob
import os
from typing import Optional

from cleaners.base import RISK_LOW, CleanItem, Cleaner, make_dir_item


class TempFilesCleaner(Cleaner):
    id = "temp_files"
    display_name = "系统临时文件"

    def scan(self) -> list[CleanItem]:
        items: list[CleanItem] = []
        items.extend(self._scan_user_temp())
        items.extend(self._scan_system_temp())
        items.extend(self._scan_thumbnails())
        items.extend(self._scan_prefetch())
        return items

    def _scan_user_temp(self) -> list[CleanItem]:
        path = self.p("user_temp", "TEMP")
        item = make_dir_item(path, self.id, f"用户临时文件 {path}", RISK_LOW, False)
        return [item] if item else []

    def _scan_system_temp(self) -> list[CleanItem]:
        path = self.p("system_temp") or os.path.join(
            os.environ.get("SystemRoot", "C:\\Windows"), "Temp"
        )
        item = make_dir_item(path, self.id, f"系统临时文件 {path}", RISK_LOW, False, delete_contents_only=True)
        return [item] if item else []

    def _scan_thumbnails(self) -> list[CleanItem]:
        explorer = self.p("explorer_dir") or os.path.join(
            os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Explorer"
        )
        items: list[CleanItem] = []
        for pattern in ("thumbcache_*.db", "iconcache_*.db"):
            for fp in glob.glob(os.path.join(explorer, pattern)):
                try:
                    size = os.path.getsize(fp)
                except OSError:
                    continue
                items.append(
                    CleanItem(
                        path=fp,
                        cleaner_id=self.id,
                        label=f"缩略图缓存 {os.path.basename(fp)}",
                        size=size,
                        file_count=1,
                        risk=RISK_LOW,
                        allowed_prefixes=(explorer,),
                    )
                )
        return items

    def _scan_prefetch(self) -> list[CleanItem]:
        path = self.p("prefetch") or os.path.join(
            os.environ.get("SystemRoot", "C:\\Windows"), "Prefetch"
        )
        item = make_dir_item(path, self.id, f"预读取文件 {path}", RISK_LOW, False, delete_contents_only=True)
        return [item] if item else []
