"""清理线程异常兜底测试：worker 崩溃不能让 UI 永久卡死。"""
import queue

from cleaners.base import CleanItem
from ui.threads import CleanWorker


def _item(path="C:/tmp/x"):
    return CleanItem(path=path, cleaner_id="test", label=path,
                     size=100, allowed_prefixes=(path,))


def test_clean_worker_normal_flow_emits_finished():
    class FakeDeleter:
        def delete(self, item):
            return True, "", 100

    q = queue.Queue()
    CleanWorker([_item("C:/tmp/a"), _item("C:/tmp/b")], FakeDeleter(), q).run()
    msgs = [q.get_nowait() for _ in range(q.qsize())]
    assert [m[0] for m in msgs] == ["item_done", "item_done", "clean_finished"]
    assert msgs[2] == ("clean_finished",)


def test_clean_worker_crash_still_emits_finished():
    """deleter 抛非 OSError 异常时：clean_error 入队 + clean_finished 必须到达，
    否则 UI _busy 永远为 True、按钮永久禁用。"""

    class BadDeleter:
        def delete(self, item):
            raise RuntimeError("boom")

    q = queue.Queue()
    CleanWorker([_item()], BadDeleter(), q).run()
    msgs = [q.get_nowait() for _ in range(q.qsize())]
    assert msgs[0][0] == "clean_error"
    assert "boom" in msgs[0][1]
    assert msgs[1] == ("clean_finished",)


def test_clean_worker_partial_progress_then_crash():
    """前几项成功、中间崩溃：进度消息照发，最后仍有 clean_finished。"""

    class FlakyDeleter:
        def __init__(self):
            self.n = 0

        def delete(self, item):
            self.n += 1
            if self.n == 2:
                raise ValueError("second item failed")
            return True, "", 100

    q = queue.Queue()
    items = [_item("C:/tmp/a"), _item("C:/tmp/b"), _item("C:/tmp/c")]
    CleanWorker(items, FlakyDeleter(), q).run()
    msgs = [q.get_nowait() for _ in range(q.qsize())]
    assert [m[0] for m in msgs] == ["item_done", "clean_error", "clean_finished"]
    assert msgs[2] == ("clean_finished",)
