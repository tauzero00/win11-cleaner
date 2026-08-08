"""UAC 自动提权与单实例锁。"""
from __future__ import annotations

import ctypes
import subprocess
import sys

# Global\ 前缀：跨会话共享互斥锁。无前缀时锁落在会话命名空间，
# RDP 多会话可同时启动两个实例，造成删除竞态。
_SINGLE_INSTANCE_NAME = "Global\\Win11Cleaner_SingleInstance"
_ERROR_ALREADY_EXISTS = 183


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def elevate() -> bool:
    """以管理员身份重启自身。用户拒绝返回 False。"""
    try:
        # list2cmdline 正确转义内嵌引号，防命令行截断
        params = subprocess.list2cmdline(sys.argv)
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
