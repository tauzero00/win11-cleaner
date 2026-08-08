"""UAC 提权与单实例锁测试。"""
import ctypes
import sys

from core.elevation import acquire_single_instance


def test_acquire_uses_global_mutex(monkeypatch):
    """互斥名须带 Global\\ 前缀：会话级互斥在 RDP 多会话下可同时运行两个实例。"""
    captured = {}

    def fake_create_mutex(sa, b, name):
        captured["name"] = name
        return 1

    monkeypatch.setattr(ctypes.windll.kernel32, "CreateMutexW", fake_create_mutex)
    monkeypatch.setattr(ctypes.windll.kernel32, "GetLastError", lambda: 0)
    assert acquire_single_instance() is True
    assert captured["name"] == "Global\\Win11Cleaner_SingleInstance"


def test_acquire_false_when_already_running(monkeypatch):
    monkeypatch.setattr(ctypes.windll.kernel32, "CreateMutexW", lambda *a, **k: 1)
    monkeypatch.setattr(ctypes.windll.kernel32, "GetLastError", lambda: 183)
    assert acquire_single_instance() is False


def test_acquire_tolerates_errors(monkeypatch):
    def boom(*a, **k):
        raise OSError("no kernel32")

    monkeypatch.setattr(ctypes.windll.kernel32, "CreateMutexW", boom)
    assert acquire_single_instance() is True  # 拿不到锁信息时不阻塞启动


def test_elevate_escapes_quotes(monkeypatch):
    """elevate 的参数拼接须用 list2cmdline：含引号/空格参数不会被截断。"""
    from core import elevation

    captured = {}

    def fake_shell_execute(hwnd, verb, file, params, cwd, show):
        captured["params"] = params
        return 42

    monkeypatch.setattr(ctypes.windll.shell32, "ShellExecuteW", fake_shell_execute)
    monkeypatch.setattr(elevation.sys, "argv", ["main.py", '引"号 参数'])
    assert elevation.elevate() is True
    # list2cmdline 会正确转义内嵌引号，而不是原样拼接导致命令行截断
    assert '\\"' in captured["params"] or captured["params"].count('"') == 2
