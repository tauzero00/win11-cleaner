"""运行中进程的可执行文件路径枚举。"""
from __future__ import annotations

import os
import subprocess

# 前置 OutputEncoding=UTF8：Windows PowerShell 5.1 管道默认按 OEM/GBK 输出，
# 中文路径（如 OEM\\机械革命电竞控制台）会被解成乱码，导致"运行中程序目录
# 不可删"的保护在中文路径下失效。显式 UTF-8 后 Python 侧固定按 utf-8 解码。
_SCRIPT = (
    "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
    "Get-Process | Where-Object { $_.Path } | Select-Object -ExpandProperty Path"
)


def running_process_paths() -> set[str]:
    """运行中进程的 exe 完整路径集合（normcase + abspath）。失败/超时返回空集。"""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", _SCRIPT],
            capture_output=True, encoding="utf-8", errors="replace", timeout=30,
        )
    except Exception:
        return set()
    paths = set()
    for line in out.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            paths.add(os.path.normcase(os.path.abspath(line)))
        except OSError:
            pass
    return paths
