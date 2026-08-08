"""已卸载软件残留检测（孤儿目录）。"""
from __future__ import annotations

import difflib
import os
import re
import subprocess
import time
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
    # Windows 遗留 junction 目录名（Application Data → AppData 等），非软件残留
    "applicationdata",
    "localsettings",
    "mydocuments",
    "recent",
    "sendto",
    "templates",
    "startmenu",
    "nethood",
    "printhood",
    "history",
    "temporaryinternetfiles",
    "cookies",
    # 更多系统自带目录
    "referenceassemblies",
    "windowspowershell",
    "windowsphotoviewer",
    "oem",
    "dotnet",
    "difx",
}

FUZZY_THRESHOLD = 0.6


def normalize(name: str) -> str:
    """小写并只保留字母数字，用于比较。"""
    return "".join(ch for ch in name.lower() if ch.isalnum())


def _tokens(name: str) -> list[str]:
    """按非字母数字切分小写名称，返回长度 >= 3 的词元（如 "NVIDIA Corporation" → [nvidia, corporation]）。"""
    return [t for t in re.split(r"[^a-z0-9]+", name.lower()) if len(t) >= 3]


def _matches_installed(nname: str, norm_installed: set[str]) -> bool:
    """目录名是否与任一已安装程序名匹配（相等/子串/模糊）。"""
    for ins in norm_installed:
        if nname == ins or nname in ins or ins in nname:
            return True
    return any(
        difflib.SequenceMatcher(None, nname, ins).ratio() >= FUZZY_THRESHOLD
        for ins in norm_installed
    )


def _path_under(candidate: str, paths: Iterable[str]) -> bool:
    """candidate 是任一 path 的父目录（或自身）→ 该目录正被使用，不算残留。"""
    cc = os.path.normcase(candidate)
    for p in paths:
        if not p:
            continue
        pc = os.path.normcase(p)
        if pc == cc or pc.startswith(cc + os.sep):
            return True
    return False


def _subdir_matches_installed(full: str, norm_installed: set[str]) -> bool:
    """候选目录的一级子目录名是已装程序名 → 是厂商目录（DAUM/PotPlayer、Tencent/TIM）。

    只匹配子目录且要求整名匹配（相等/子串），不用词元：Electron 应用的
    extensions/resources/locales 等基础设施目录不是程序名，词元匹配会
    系统性放过所有基于 Electron 的真残留。
    """
    try:
        names = os.listdir(full)
    except OSError:
        return False
    for name in names:
        sub = os.path.join(full, name)
        try:
            if not os.path.isdir(sub):
                continue
        except OSError:
            continue
        sn = normalize(name)
        if not sn:
            continue
        if any(sn == ins or sn in ins or ins in sn for ins in norm_installed):
            return True
    return False


def _recently_active(path: str, max_idle_days: int) -> bool:
    """目录树内是否有 max_idle_days 天内修改过的文件（有 → 在用，不算残留）。

    找到新文件即提前返回；剪 junction，避免重解析自环。
    """
    if max_idle_days <= 0:
        return False
    cutoff = time.time() - max_idle_days * 86400
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = [
                d for d in dirnames
                if not os.path.islink(os.path.join(dirpath, d))
                and not os.path.isjunction(os.path.join(dirpath, d))
            ]
            for name in filenames:
                fp = os.path.join(dirpath, name)
                try:
                    if os.path.getmtime(fp) >= cutoff:
                        return True
                except OSError:
                    pass
    except OSError:
        pass
    return False


def detect_orphans(
    installed_names: Iterable[str],
    root_dirs: Iterable[str],
    cleaner_id: str,
    whitelist: Optional[set[str]] = None,
    installed_locations: Iterable[str] = (),
    running_paths: Iterable[str] = (),
    max_idle_days: int = 180,
) -> list[CleanItem]:
    """枚举 root_dirs 第一级目录，返回疑似未卸载残留。

    排除规则（任一命中即视为正常软件，宁漏勿误）：
    1. 目录名/子目录名词元匹配已装程序名（NVIDIA Corporation → nvidia）
    2. 目录是已装程序 InstallLocation 或运行中进程的父目录
    3. 目录树内 max_idle_days 天内有文件修改（在用的软件）
    """
    # 剔除 SDK 开发组件：其名字含通用词（extensions、sdk、100 等），
    # 会让任何 Electron 应用目录的 extensions 子目录都命中"已装程序"而漏报残留
    norm_installed = {
        nn for n in installed_names
        if n and (nn := normalize(n)) and "sdk" not in nn
    }
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
            # 词元匹配：目录名的任一词元（>=3 字符）出现在已安装程序名中即视为正常软件
            # （如 "NVIDIA Corporation" 的词元 nvidia 匹配 "NVIDIA 图形驱动程序 610.62"）
            if any(
                any(t in ins for ins in norm_installed)
                for t in _tokens(name)
            ):
                continue
            # 子目录匹配：厂商目录下是已装程序（DAUM/PotPlayer、Tencent/TIM）
            if _subdir_matches_installed(full, norm_installed):
                continue
            # InstallLocation 父目录 / 运行中进程路径
            if _path_under(full, installed_locations) or _path_under(full, running_paths):
                continue
            # 最近有文件活动 → 在用
            if _recently_active(full, max_idle_days):
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
        # 只扫安装目录：AppData/ProgramData 是正常软件的数据目录，不算残留
        roots = []
        for key in ("ProgramFiles", "ProgramFiles(x86)"):
            path = self.p(key, key)
            if path:
                roots.append(path)
        installed = self._installed_names()
        locations = self._installed_locations()
        running = self._running_paths()
        return detect_orphans(
            installed, roots, self.id,
            installed_locations=locations, running_paths=running,
        )

    def _registry_values(self, value_name: str) -> list[str]:
        """从 HKLM Uninstall（64/32 位视角）读取指定值。"""
        values: list[str] = []
        subkey = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
        for flags in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey, 0, winreg.KEY_READ | flags) as k:
                    count = winreg.QueryInfoKey(k)[0]
                    for i in range(count):
                        try:
                            with winreg.OpenKey(k, winreg.EnumKey(k, i)) as s:
                                try:
                                    val = winreg.QueryValueEx(s, value_name)[0]
                                    if val:
                                        values.append(val)
                                except OSError:
                                    pass
                        except OSError:
                            pass
            except OSError:
                pass
        return values

    def _installed_names(self) -> list[str]:
        """测试可用 root_overrides["installed_names"] 覆盖。"""
        if "installed_names" in self.root_overrides:
            return list(self.root_overrides["installed_names"])
        return self._registry_values("DisplayName")

    def _installed_locations(self) -> list[str]:
        """已安装程序的 InstallLocation（测试可用 root_overrides["installed_locations"] 覆盖）。"""
        if "installed_locations" in self.root_overrides:
            return list(self.root_overrides["installed_locations"])
        return self._registry_values("InstallLocation")

    def _running_paths(self) -> list[str]:
        """运行中进程的可执行文件路径（测试可用 root_overrides["running_paths"] 覆盖）。"""
        if "running_paths" in self.root_overrides:
            return list(self.root_overrides["running_paths"])
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-Process | Select-Object -ExpandProperty Path"],
                capture_output=True, timeout=15,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired):
            return []
        # PowerShell 5.1 管道输出为 UTF-16LE，PowerShell 7 为 UTF-8；按 \x00 探测
        raw = out.stdout
        text = raw.decode("utf-16-le") if b"\x00" in raw else raw.decode("utf-8", "replace")
        paths = []
        for line in text.splitlines():
            line = line.strip().rstrip("\r")
            if line and os.path.isabs(line):
                paths.append(line)
        return paths
