"""后台清理线程。"""
from __future__ import annotations

import queue
import threading

from cleaners.base import CleanItem
from core.deleter import Deleter


class CleanWorker(threading.Thread):
    """逐项删除勾选的项目，进度经 queue 回传。

    消息格式：
    ("item_done", 序号, 总数, item, 成功, 原因, 释放字节)
    ("clean_finished",)
    """

    def __init__(self, items: list[CleanItem], deleter: Deleter, msg_queue: queue.Queue):
        super().__init__(daemon=True)
        self.items = items
        self.deleter = deleter
        self.msg_queue = msg_queue

    def run(self):
        total = len(self.items)
        for i, item in enumerate(self.items, 1):
            ok, reason, freed = self.deleter.delete(item)
            self.msg_queue.put(("item_done", i, total, item, ok, reason, freed))
        self.msg_queue.put(("clean_finished",))
