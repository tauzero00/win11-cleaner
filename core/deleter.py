"""删除引擎：删除前校验 + 永久删除/回收站 + 释放空间统计。"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from typing import Iterable, Optional

import send2trash

# 永不删除的系统关键目录（含其下所有内容）。
SYSTEM_CRITICAL_DIRS = [
    "C:\\Windows\\System32",
    "C:\\Windows\\SysWOW64",
    "C:\\Windows\\WinSxS",
    "C:\\Windows\\Servicing",
    "C:\\Windows\\Installer",
    "C:\\Program Files\\Common Files",
    "C:\\Program Files (x86)\\Common Files",
    "C:\\ProgramData\\Microsoft\\Windows\\Start Menu",
]

# 禁止删除的目录本体
SYSTEM_DIR_BODIES = ["C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)", "C:\\ProgramData"]


def _running_process_dirs() -> set[str]:
    """当前运行中进程的 exe 所在目录集合。失败时返回空集。"""
    script = "Get-Process | Where-Object { $_.Path } | Select-Object -ExpandProperty Path"
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=30,
        )
    except Exception:
        return set()
    dirs = set()
    for line in out.stdout.splitlines():
        line = line.strip()
        if line:
            try:
                dirs.add(os.path.normcase(os.path.abspath(os.path.dirname(line))))
            except OSError:
                pass
    return dirs


class Deleter:
    """删除引擎。每个 Deleter 实例缓存一次运行中进程目录列表。"""

    def __init__(self, critical_dirs: Optional[Iterable[str]] = None):
        self.critical = [
            os.path.normcase(os.path.abspath(d)) for d in (critical_dirs or SYSTEM_CRITICAL_DIRS)
        ]
        self._proc_dirs: Optional[set[str]] = None

    def validate(self, item) -> Optional[str]:
        """返回拒绝原因；None 表示通过校验。"""
        p = os.path.normcase(os.path.abspath(item.path))

        # 1. 必须在系统盘（C:）内
        system = os.environ.get("SystemDrive", "C:")
        if not p.startswith(os.path.normcase(system)):
            return "不在系统盘范围内"

        # 2. 必须位于 Cleaner 声明的允许前缀内
        ok = False
        for prefix in item.allowed_prefixes:
            pc = os.path.normcase(os.path.abspath(prefix))
            if p == pc or p.startswith(pc + os.sep):
                ok = True
                break
        if not ok:
            return "超出该清理项声明的允许范围"

        # 3. 系统关键目录黑名单
        for c in self.critical:
            if p == c or p.startswith(c + os.sep):
                return f"位于系统关键目录 {c}"
            # 防御纵深：去掉盘符后的路径后缀匹配，防止伪造系统目录
            # e.g. tmp_path/Windows/System32/config matches C:\Windows\System32
            c_suffix = c.split(":", 1)[1] if ":" in c else c
            p_suffix = p.split(":", 1)[1] if ":" in p else p
            if (p_suffix == c_suffix
                    or p_suffix.startswith(c_suffix + "\\")
                    or (c_suffix + "\\") in p_suffix
                    or p_suffix.endswith(c_suffix)):
                return f"位于系统关键目录 {c}"

        # 4. 系统目录本体
        for t in SYSTEM_DIR_BODIES + [system]:
            tc = os.path.normcase(os.path.abspath(t))
            if p == tc:
                return f"禁止删除系统目录本体 {t}"

        # 5. 正在运行的程序目录（懒加载，缓存一次）
        if self._proc_dirs is None:
            self._proc_dirs = _running_process_dirs()
        for d in self._proc_dirs:
            d_norm = os.path.normcase(d)
            if p == d_norm or p.startswith(d_norm + os.sep):
                return "位于正在运行的程序目录内"

        return None

    def delete(self, item) -> tuple[bool, str, int]:
        """删除一个项。返回 (成功, 原因, 释放字节)。"""
        reason = self.validate(item)
        if reason:
            return False, reason, 0
        if not os.path.exists(item.path):
            return True, "", 0  # 目录不存在：静默跳过，视为成功
        freed = item.size
        try:
            if item.to_recycle:
                send2trash.send2trash(item.path)
            elif item.delete_contents_only:
                self._delete_contents(item.path)
            else:
                self._delete_path(item.path)
            return True, "", freed
        except OSError as exc:
            return False, str(exc), 0

    def _delete_path(self, path: str):
        """删除单个路径（重试 2 次，间隔 1 秒）。"""
        for attempt in range(3):
            try:
                if os.path.isdir(path) and not os.path.islink(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                return
            except OSError:
                if attempt < 2:
                    time.sleep(1)
                else:
                    raise

    def _delete_contents(self, dirpath: str):
        """只删除目录内容，不删除目录本身。全部子项都失败才抛异常。"""
        failed = 0
        for name in os.listdir(dirpath):
            child = os.path.join(dirpath, name)
            try:
                self._delete_path(child)
            except OSError:
                failed += 1
        if failed and failed == len(os.listdir(dirpath)):
            raise OSError(f"{dirpath} 下的 {failed} 个子项均无法删除")
