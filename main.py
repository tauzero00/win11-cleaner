"""C盘清理工具入口：提权 → 单实例 → 启动 GUI。"""
from __future__ import annotations

import ctypes
import sys

from core.elevation import acquire_single_instance, elevate, is_admin


def _warn(msg: str):
    try:
        ctypes.windll.user32.MessageBoxW(0, msg, "C盘清理工具", 0x30)  # 0x30 = 警告图标
    except Exception:
        pass


def main():
    if not is_admin():
        if not elevate():
            _warn("已拒绝管理员权限，无法清理系统目录。请以管理员身份重新运行。")
        sys.exit(0)  # 提权后本进程退出，由新进程继续
    if not acquire_single_instance():
        _warn("清理工具已在运行。")
        sys.exit(1)
    from ui.app import main as run_app
    run_app()


if __name__ == "__main__":
    main()
