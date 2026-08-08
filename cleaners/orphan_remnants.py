"""已卸载软件残留检测（孤儿目录）。"""
from __future__ import annotations

import difflib
import os
import winreg
from typing import Iterable, Optional

from cleaners.base import RISK_HIGH, CleanItem, Cleaner
from core.scanner import dir_size

# 系统自有、永远不算残留的目录名（normalize 之后的小写字母数字）
WHITELIST = {
    "commonfiles",
    "internetexplorer",
    "windowskits",
    "microsoft",
    "microsoftshared",
    "windowsnt",
    "uninstallinformation",
    "msbuild",
    "packages",
    "packagecache",
    "usoshared",
    "windowsapps",
}

FUZZY_THRESHOLD = 0.6


def normalize(name: str) -> str:
    """小写并只保留字母数字，用于比较。"""
    return "".join(ch for ch in name.lower() if ch.isalnum())


def _matches_installed(nname: str, norm_installed: set[str]) -> bool:
    """目录名是否与任一已安装程序名匹配（相等/子串/模糊）。"""
    for ins in norm_installed:
        if nname == ins or nname in ins or ins in nname:
            return True
    return any(
        difflib.SequenceMatcher(None, nname, ins).ratio() >= FUZZY_THRESHOLD
        for ins in norm_installed
    )


def detect_orphans(
    installed_names: Iterable[str],
    root_dirs: Iterable[str],
    cleaner_id: str,
    whitelist: Optional[set[str]] = None,
) -> list[CleanItem]:
    """枚举 root_dirs 第一级目录，返回疑似未卸载残留。"""
    norm_installed = {nn for n in installed_names if n and (nn := normalize(n))}
    wl = whitelist or WHITELIST
    items: list[CleanItem] = []
    for root in root_dirs:
        if not os.path.isdir(root):
            continue
        try:
            entries = sorted(os.listdir(root))
        except OSError:
            continue
        for name in entries:
            if name.startswith("."):
                continue
            full = os.path.join(root, name)
            try:
                if not os.path.isdir(full):
                    continue
            except OSError:
                continue
            nname = normalize(name)
            if not nname or nname in wl:
                continue
            if _matches_installed(nname, norm_installed):
                continue
            size, count = dir_size(full)
            if count == 0:
                continue  # 空目录不算残留
            items.append(
                CleanItem(
                    path=full,
                    cleaner_id=cleaner_id,
                    label=f"疑似已卸载软件残留 {full}",
                    size=size,
                    file_count=count,
                    risk=RISK_HIGH,
                    allowed_prefixes=(os.path.dirname(full),),
                    to_recycle=True,  # 高风险，默认移入回收站
                )
            )
    return items


class OrphanRemnantsCleaner(Cleaner):
    id = "orphan_remnants"
    display_name = "已卸载软件残留"

    def scan(self) -> list[CleanItem]:
        roots = []
        for key, env in (
            ("ProgramFiles", "ProgramFiles"),
            ("ProgramFiles(x86)", "ProgramFiles(x86)"),
            ("ProgramData", "ProgramData"),
            ("LOCALAPPDATA", "LOCALAPPDATA"),
            ("APPDATA", "APPDATA"),
        ):
            path = self.p(key, env)
            if path:
                roots.append(path)
        installed = self._installed_names()
        return detect_orphans(installed, roots, self.id)

    def _installed_names(self) -> list[str]:
        """测试可用 root_overrides["installed_names"] 覆盖。"""
        if "installed_names" in self.root_overrides:
            return list(self.root_overrides["installed_names"])
        names: list[str] = []
        subkey = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
        for flags in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey, 0, winreg.KEY_READ | flags) as k:
                    count = winreg.QueryInfoKey(k)[0]
                    for i in range(count):
                        try:
                            sub = winreg.EnumKey(k, i)
                            with winreg.OpenKey(k, sub) as s:
                                try:
                                    name = winreg.QueryValueEx(s, "DisplayName")[0]
                                    if name:
                                        names.append(name)
                                except OSError:
                                    pass
                        except OSError:
                            pass
            except OSError:
                pass
        return names
