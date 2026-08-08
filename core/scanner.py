"""目录大小计算、格式化与后台扫描线程。"""
from __future__ import annotations

import os
import queue
import threading


def dir_size(path: str) -> tuple[int, int]:
    """递归计算目录大小（字节）与文件数。跳过无权限、不存在、符号链接的子项。"""
    if not os.path.isdir(path):
        return 0, 0
    total = 0
    count = 0
    for dirpath, dirnames, filenames in os.walk(path, topdown=True):
        # 剪掉符号链接目录，避免循环
        dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]
        for name in filenames:
            fp = os.path.join(dirpath, name)
            try:
                if os.path.islink(fp):
                    continue
                total += os.path.getsize(fp)
                count += 1
            except OSError:
                pass
    return total, count


def human_size(n: int) -> str:
    """把字节数格式化为人类可读字符串。"""
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(n)
    for unit in units:
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024


class ScanWorker(threading.Thread):
    """后台扫描线程：依次运行所有 cleaner，进度经 queue 回传。

    消息格式：
    ("category_start", cleaner_id, display_name)
    ("category_done", cleaner_id, list[CleanItem])
    ("category_error", cleaner_id, 错误信息)
    ("scan_finished", None, None)
    """

    def __init__(self, cleaners: list, msg_queue: queue.Queue):
        super().__init__(daemon=True)
        self.cleaners = cleaners
        self.msg_queue = msg_queue

    def run(self):
        for cleaner in self.cleaners:
            self.msg_queue.put(("category_start", cleaner.id, cleaner.display_name))
            try:
                items = cleaner.scan()
            except Exception as exc:  # 单个类别失败不拖垮整个扫描
                self.msg_queue.put(("category_error", cleaner.id, str(exc)))
                continue
            self.msg_queue.put(("category_done", cleaner.id, items))
        self.msg_queue.put(("scan_finished", None, None))
