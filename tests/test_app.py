"""主窗口 UI 逻辑测试（不依赖显示器，withdrawn 窗口）。"""
from __future__ import annotations

import tkinter as tk
from unittest.mock import MagicMock

import pytest

from cleaners.base import CleanItem
from ui.app import CleanerApp


# 使用真实 cleaner ID，确保 cat_buttons 查表命中。
_CID = "temp_files"


def _make_items(*paths: str) -> list[CleanItem]:
    """构建一组全勾选的 CleanItem，大小升序便于验证排序。"""
    items: list[CleanItem] = []
    for i, p in enumerate(paths):
        items.append(CleanItem(
            path=p, cleaner_id=_CID, label=p,
            size=(i + 1) * 1000,
            allowed_prefixes=(p,), checked=True,
        ))
    return items


def _populate_tree(app, items: list[CleanItem]):
    """辅助：把 items 插入 tree 并注册到 app.items/row_ids/iid_to_path。"""
    from core.scanner import human_size
    for item in sorted(items, key=lambda i: i.size, reverse=True):
        mark = "☑" if item.checked else "☐"
        iid = app.tree.insert("", "end", values=(mark, item.label, human_size(item.size)))
        app.items[item.path] = item
        app.row_ids[item.path] = iid
        app.iid_to_path[iid] = item.path


# ---------------------------------------------------------------------------
# session-scoped app fixture（避免 Tcl destroy/recreate 竞态）
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def app():
    """创建 withdrawn 应用实例（不启动真实扫描线程，整个 session 复用）。"""
    original = CleanerApp.start_scan
    CleanerApp.start_scan = lambda self: None  # no-op，阻止 __init__ 启动扫描
    a = None
    try:
        a = CleanerApp()
        a.withdraw()
        a.update_idletasks()
        yield a
    finally:
        CleanerApp.start_scan = original
        if a is not None:
            try:
                a.destroy()
            except tk.TclError:
                pass


@pytest.fixture(autouse=True)
def _reset_app_state(app):
    """每项测试前重置应用状态。"""
    app.items.clear()
    app.row_ids.clear()
    app.iid_to_path.clear()
    app._busy = False
    app.tree.delete(*app.tree.get_children())
    app._result_ok = []
    app._result_fail = []
    app._result_freed = []
    app.summary_var.set("已选 0 B / 共 0 B")
    app.status_var.set("")
    app.progress.configure(mode="determinate", value=0)
    for var in app.category_vars.values():
        var.set(True)
    # 清理手动插入的 dummy cat_button
    for cid in list(app.cat_buttons.keys()):
        if cid not in app.category_vars:
            del app.cat_buttons[cid]
    yield


# ---------------------------------------------------------------------------
# 消息分发
# ---------------------------------------------------------------------------

class TestMessageDispatch:

    def test_category_done_populates_items_and_tree(self, app):
        items = _make_items("C:/tmp/a", "C:/tmp/b", "C:/tmp/c")
        # 使用真实 cleaner ID 以命中 cat_buttons
        for it in items:
            it.cleaner_id = _CID
        app._handle(("category_done", _CID, items))

        assert len(app.items) == 3
        assert set(app.items.keys()) == {"C:/tmp/a", "C:/tmp/b", "C:/tmp/c"}
        assert len(app.row_ids) == 3
        assert len(app.iid_to_path) == 3

        # 按大小降序：c(3000) > b(2000) > a(1000)
        children = app.tree.get_children()
        assert app.tree.item(children[0], "values")[1] == "C:/tmp/c"
        assert app.tree.item(children[2], "values")[1] == "C:/tmp/a"

    def test_category_done_unchecked_item_shows_empty_check(self, app):
        items = [CleanItem(path="C:/tmp/x", cleaner_id=_CID, label="x",
                           size=100, allowed_prefixes=("C:/tmp/x",), checked=False)]
        app._handle(("category_done", _CID, items))
        iid = app.tree.get_children()[0]
        assert app.tree.item(iid, "values")[0] == "☐"

    def test_category_error_updates_button(self, app):
        app._handle(("category_error", _CID, "权限不足"))
        assert "错误: 权限不足" in app.cat_buttons[_CID]["text"]

    def test_scan_finished_enables_buttons(self, app):
        app._busy = True
        app.progress.configure(mode="indeterminate")
        app.progress.start(20)

        app._handle(("scan_finished", None, None))

        assert not app._busy
        assert app.rescan_btn.instate(["!disabled"])
        assert app.clean_btn.instate(["!disabled"])
        assert app.status_var.get() == "扫描完成"


# ---------------------------------------------------------------------------
# item_done 收集
# ---------------------------------------------------------------------------

class TestItemDoneCollection:

    def test_item_done_ok_collects_result(self, app):
        item = CleanItem(path="C:/tmp/d", cleaner_id=_CID, label="d",
                         size=5000, allowed_prefixes=("C:/tmp/d",))
        app._handle(("item_done", 1, 3, item, True, "", 5000))
        assert app._result_ok == [item]
        assert app._result_freed == [5000]
        assert app._result_fail == []
        assert "正在清理… 1/3" in app.status_var.get()

    def test_item_done_fail_collects_result(self, app):
        item = CleanItem(path="C:/tmp/e", cleaner_id=_CID, label="e",
                         size=100, allowed_prefixes=("C:/tmp/e",))
        app._handle(("item_done", 2, 3, item, False, "拒绝访问", 0))
        assert app._result_ok == []
        assert app._result_freed == []
        assert app._result_fail == [(item, "拒绝访问")]
        assert "清理失败" in app.status_var.get()


# ---------------------------------------------------------------------------
# _toggle_category 勾选联动
# ---------------------------------------------------------------------------

class TestToggleCategory:

    def test_toggle_unchecks_all_items_in_category(self, app):
        items = _make_items("C:/tmp/a", "C:/tmp/b")
        _populate_tree(app, items)

        assert all(i.checked for i in app.items.values())

        app.category_vars[_CID].set(False)
        app._toggle_category(_CID)

        assert not any(i.checked for i in app.items.values())
        for path in ("C:/tmp/a", "C:/tmp/b"):
            iid = app.row_ids[path]
            assert app.tree.item(iid, "values")[0] == "☐"

    def test_toggle_rechecks_all_items_in_category(self, app):
        items = _make_items("C:/tmp/a")
        _populate_tree(app, items)

        app.category_vars[_CID].set(False)
        app._toggle_category(_CID)
        assert app.items["C:/tmp/a"].checked is False

        app.category_vars[_CID].set(True)
        app._toggle_category(_CID)
        assert app.items["C:/tmp/a"].checked is True
        iid = app.row_ids["C:/tmp/a"]
        assert app.tree.item(iid, "values")[0] == "☑"


# ---------------------------------------------------------------------------
# _on_tree_click 单项勾选 + 同步类别勾选框
# ---------------------------------------------------------------------------

class TestTreeClick:

    @staticmethod
    def _click_event(app, path: str):
        """构造一个能让 _on_tree_click 命中指定 path 的 mock 事件。"""
        iid = app.row_ids[path]
        event = MagicMock()
        event.y = 0
        event.widget = app.tree
        # 因为 withdrawn 窗口的 tree.bbox() 返回空串，我们 mock identify_row
        original_identify = app.tree.identify_row
        app.tree.identify_row = lambda y: iid
        return event, original_identify

    def test_click_toggles_single_item(self, app):
        items = _make_items("C:/tmp/a")
        _populate_tree(app, items)

        item = app.items["C:/tmp/a"]
        assert item.checked is True

        iid = app.row_ids["C:/tmp/a"]
        event, orig = self._click_event(app, "C:/tmp/a")
        app._on_tree_click(event)
        app.tree.identify_row = orig  # 恢复

        assert item.checked is False
        assert app.tree.item(iid, "values")[0] == "☐"

    def test_click_syncs_category_var(self, app):
        items = _make_items("C:/tmp/a", "C:/tmp/b")
        _populate_tree(app, items)

        assert app.category_vars[_CID].get() is True

        event, orig = self._click_event(app, "C:/tmp/a")
        app._on_tree_click(event)

        assert app.category_vars[_CID].get() is False

        app._on_tree_click(event)
        app.tree.identify_row = orig

        assert app.category_vars[_CID].get() is True

    def test_click_on_empty_area_is_noop(self, app):
        items = _make_items("C:/tmp/a")
        _populate_tree(app, items)

        # mock identify_row 返回空串模拟空白区点击
        original = app.tree.identify_row
        app.tree.identify_row = lambda y: ""
        event = MagicMock()
        event.y = 0
        event.widget = app.tree
        app._on_tree_click(event)
        app.tree.identify_row = original
        assert app.items["C:/tmp/a"].checked is True


# ---------------------------------------------------------------------------
# _refresh_summary 计算
# ---------------------------------------------------------------------------

class TestRefreshSummary:

    def test_summary_reflects_all_checked(self, app):
        _populate_tree(app, _make_items("C:/tmp/a", "C:/tmp/b"))
        app._refresh_summary()
        assert "2.9 KB" in app.summary_var.get()

    def test_summary_after_uncheck(self, app):
        _populate_tree(app, _make_items("C:/tmp/a", "C:/tmp/b"))
        app.items["C:/tmp/a"].checked = False
        app._refresh_summary()
        assert "2.0 KB" in app.summary_var.get()


# ---------------------------------------------------------------------------
# busy 守卫
# ---------------------------------------------------------------------------

class TestBusyGuard:

    def test_start_scan_guarded_when_busy(self, app):
        app.items["dummy"] = CleanItem(path="x", cleaner_id=_CID, label="x",
                                       size=0, allowed_prefixes=("x",))
        app._busy = True
        app.start_scan()
        assert "dummy" in app.items

    def test_start_clean_guarded_when_busy(self, app, monkeypatch):
        app._busy = True
        called = []

        def fake_info(*args, **kwargs):
            called.append("info")

        monkeypatch.setattr("tkinter.messagebox.showinfo", fake_info)
        app.start_clean()
        assert not called
        assert app._busy is True

    def test_toggle_category_guarded_when_busy(self, app):
        _populate_tree(app, _make_items("C:/tmp/a"))
        app._busy = True
        app.category_vars[_CID].set(False)
        app._toggle_category(_CID)
        assert app.items["C:/tmp/a"].checked is True

    def test_on_tree_click_guarded_when_busy(self, app):
        _populate_tree(app, _make_items("C:/tmp/a"))
        app._busy = True

        iid = app.row_ids["C:/tmp/a"]
        original = app.tree.identify_row
        app.tree.identify_row = lambda y: iid
        event = MagicMock()
        event.y = 0
        event.widget = app.tree
        app._on_tree_click(event)
        app.tree.identify_row = original

        assert app.items["C:/tmp/a"].checked is True


# ---------------------------------------------------------------------------
# start_clean 确认路径
# ---------------------------------------------------------------------------

class TestStartClean:

    def test_start_clean_no_selection_shows_info(self, app, monkeypatch):
        called = []

        def fake_showinfo(title, msg):
            called.append((title, msg))

        monkeypatch.setattr("tkinter.messagebox.showinfo", fake_showinfo)
        app.start_clean()
        assert len(called) == 1
        assert "没有勾选" in called[0][1]

    def test_start_clean_rejected_cancel(self, app, monkeypatch):
        _populate_tree(app, _make_items("C:/tmp/a"))
        monkeypatch.setattr("tkinter.messagebox.askyesno", lambda *a, **kw: False)
        app.start_clean()
        assert app._busy is False

    def test_start_clean_confirmed_sets_busy(self, app, monkeypatch):
        _populate_tree(app, _make_items("C:/tmp/a"))
        monkeypatch.setattr("tkinter.messagebox.askyesno", lambda *a, **kw: True)
        monkeypatch.setattr("ui.app.CleanWorker.start", lambda self: None)
        app.start_clean()

        assert app._busy is True
        assert app._result_ok == []
        assert app._result_fail == []
        assert app._result_freed == []
        assert app.rescan_btn.instate(["disabled"])
        assert app.clean_btn.instate(["disabled"])


# ---------------------------------------------------------------------------
# _show_result（验证不抛异常）
# ---------------------------------------------------------------------------

class TestShowResult:

    def test_show_result_creates_toplevel(self, app):
        app._result_ok = []
        app._result_fail = []
        app._result_freed = []
        app._show_result()
        toplevels = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)]
        assert len(toplevels) == 1
        assert toplevels[0].title() == "清理结果"
        toplevels[0].destroy()


# ---------------------------------------------------------------------------
# clean_finished 协议
# ---------------------------------------------------------------------------

class TestCleanFinishedProtocol:

    def test_clean_finished_single_element_tuple(self, app):
        app._result_ok = []
        app._result_fail = []
        app._result_freed = []

        called = []
        app._show_result = lambda: called.append("show_result")
        app._busy = True

        app._handle(("clean_finished",))

        assert called == ["show_result"]
        assert app._busy is False
