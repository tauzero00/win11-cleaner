"""运行中进程路径枚举测试（固定 UTF-8 解码，覆盖中文路径）。"""
import os
import subprocess

from core.processes import running_process_paths


class _FakeResult:
    def __init__(self, text: str):
        self.stdout = text


def test_parses_utf8_chinese_paths(monkeypatch):
    """PS 输出含中文路径（UTF-8）也能完整解析——曾因 GBK/OEM 编码解成乱码。"""
    chinese = "C:\\Program Files\\OEM\\机械革命电竞控制台\\UniwillService\\MyControlCenter\\OSDTpDetect.exe"

    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        # 模拟 subprocess.run(encoding="utf-8") 的返回：str，且 mock 侧按 UTF-8 解码
        return _FakeResult((chinese + "\r\n").encode("utf-8").decode("utf-8"))

    monkeypatch.setattr(subprocess, "run", fake_run)
    paths = running_process_paths()

    # PS 命令必须前置 UTF-8 输出编码，Python 侧必须显式 utf-8 解码（不依赖 locale）
    assert "OutputEncoding" in captured["args"][-1]
    assert captured["kwargs"].get("encoding") == "utf-8"
    assert os.path.normcase(chinese) in paths


def test_failure_returns_empty_set(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("powershell 不存在")

    monkeypatch.setattr(subprocess, "run", boom)
    assert running_process_paths() == set()
