"""UAC 自动提权与单实例锁。"""
from __future__ import annotations

import ctypes
import sys

_SINGLE_INSTANCE_NAME = "Win11Cleaner_SingleInstance"
_ERROR_ALREADY_EXISTS = 183


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def elevate() -> bool:
    """以管理员身份重启自身。用户拒绝返回 False。"""
    try:
        params = " ".join(f'"{a}"' for a in sys.argv)
        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
        return ret > 32
    except Exception:
        return False


def acquire_single_instance() -> bool:
    """获取命名互斥锁；已有实例在运行时返回 False。"""
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW(None, False, _SINGLE_INSTANCE_NAME)
        return kernel32.GetLastError() != _ERROR_ALREADY_EXISTS
    except Exception:
        return True  # 拿不到锁信息时不阻塞启动
