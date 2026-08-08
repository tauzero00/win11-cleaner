"""主窗口。"""
from __future__ import annotations

import queue
import sys

import tkinter as tk
import tkinter.messagebox  # 显式导入：无此导入 tk.messagebox 是 AttributeError（清理确认框不弹）
import tkinter.ttk as ttk

from cleaners import get_cleaners
from cleaners.base import CleanItem
from core.deleter import Deleter
from core.scanner import ScanWorker, human_size
from ui.threads import CleanWorker


class CleanerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("C盘清理工具")
        self.geometry("920x620")
        self.minsize(760, 480)

        self.cleaners = get_cleaners()
        self._cleaner_names = {c.id: c.display_name for c in self.cleaners}
        self.category_vars: dict[str, tk.BooleanVar] = {}
        self.items: dict[str, CleanItem] = {}     # path -> item
        self.row_ids: dict[str, str] = {}          # path -> treeview iid
        self.iid_to_path: dict[str, str] = {}       # treeview iid -> path
        self.msg_queue = queue.Queue()
        self._busy = False
        self._result_ok: list = []
        self._result_fail: list = []
        self._result_freed: list = []

        self._build_ui()
        self.after(100, self._poll)
        self.start_scan()

    # ---------- UI 构建 ----------

    def _build_ui(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # 左：类别
        left = ttk.Frame(self, padding=8)
        left.grid(row=0, column=0, sticky="nsw")
        ttk.Label(left, text="清理类别", font=("", 10, "bold")).pack(anchor="w")
        self.cat_buttons = {}
        for c in self.cleaners:
            var = tk.BooleanVar(value=True)
            self.category_vars[c.id] = var
            btn = ttk.Checkbutton(
                left, text=f"{c.display_name}  (计算中…)",
                variable=var, command=lambda cid=c.id: self._toggle_category(cid),
            )
            btn.pack(anchor="w", pady=3)
            self.cat_buttons[c.id] = btn

        # 右：结果列表
        right = ttk.Frame(self, padding=8)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        columns = ("check", "path", "size")
        self.tree = ttk.Treeview(right, columns=columns, show="headings", selectmode="none")
        self.tree.heading("check", text="✓")
        self.tree.heading("path", text="路径")
        self.tree.heading("size", text="大小")
        self.tree.column("check", width=36, anchor="center", stretch=False)
        self.tree.column("path", width=560)
        self.tree.column("size", width=90, anchor="e")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<Button-1>", self._on_tree_click)
        scroll = ttk.Scrollbar(right, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)

        # 底部
        bottom = ttk.Frame(self, padding=8)
        bottom.grid(row=1, column=0, columnspan=2, sticky="ew")
        bottom.columnconfigure(3, weight=1)
        self.summary_var = tk.StringVar(value="已选 0 B / 共 0 B")
        ttk.Label(bottom, textvariable=self.summary_var).grid(row=0, column=0, sticky="w")
        self.status_var = tk.StringVar(value="正在扫描…")
        ttk.Label(bottom, textvariable=self.status_var).grid(row=0, column=1, padx=12)
        self.progress = ttk.Progressbar(bottom, mode="determinate", maximum=100, length=160)
        self.progress.grid(row=0, column=2, padx=12)
        self.rescan_btn = ttk.Button(bottom, text="重新扫描", command=self.start_scan)
        self.rescan_btn.grid(row=0, column=3, sticky="e", padx=6)
        self.clean_btn = ttk.Button(bottom, text="开始清理", command=self.start_clean)
        self.clean_btn.grid(row=0, column=4, sticky="e")
        self.rescan_btn.state(["disabled"])

    # ---------- 扫描 ----------

    def start_scan(self):
        if self._busy:
            return
        self._busy = True
        self.rescan_btn.state(["disabled"])
        self.clean_btn.state(["disabled"])
        self.tree.delete(*self.tree.get_children())
        self.items.clear()
        self.row_ids.clear()
        self.iid_to_path.clear()
        for c in self.cleaners:
            self.cat_buttons[c.id].configure(text=f"{c.display_name}  (扫描中…)")
        self.progress.configure(mode="indeterminate")
        self.progress.start(20)
        ScanWorker(self.cleaners, self.msg_queue).start()

    def _on_category_done(self, cleaner_id: str, items: list[CleanItem]):
        total = 0
        for item in items:
            self.items[item.path] = item
            total += item.size
        self.cat_buttons[cleaner_id].configure(
            text=f"{self._cat_name(cleaner_id)}  ({human_size(total)})"
        )
        # 按大小降序插入
        for item in sorted(items, key=lambda i: i.size, reverse=True):
            mark = "☑" if item.checked else "☐"
            iid = self.tree.insert("", "end", values=(mark, item.label, human_size(item.size)))
            self.row_ids[item.path] = iid
            self.iid_to_path[iid] = item.path
        self._refresh_summary()

    def _on_category_error(self, cleaner_id: str, err: str):
        self.cat_buttons[cleaner_id].configure(text=f"{self._cat_name(cleaner_id)}  (错误: {err})")

    def _cat_name(self, cleaner_id: str) -> str:
        return self._cleaner_names.get(cleaner_id, cleaner_id)

    def _on_scan_finished(self):
        self._busy = False
        self.progress.stop()
        self.progress.configure(mode="determinate", value=0)
        self.rescan_btn.state(["!disabled"])
        self.clean_btn.state(["!disabled"])
        self.status_var.set("扫描完成")

    # ---------- 勾选 ----------

    def _toggle_category(self, cleaner_id: str):
        if self._busy:
            return
        checked = self.category_vars[cleaner_id].get()
        for path, item in self.items.items():
            if item.cleaner_id == cleaner_id:
                item.checked = checked
                iid = self.row_ids[path]
                self.tree.set(iid, "check", "☑" if checked else "☐")
        self._refresh_summary()

    def _on_tree_click(self, event):
        if self._busy:
            return
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        path = self.iid_to_path.get(iid)
        if path is None:
            return
        item = self.items[path]
        item.checked = not item.checked
        self.tree.set(iid, "check", "☑" if item.checked else "☐")
        # 同步类别勾选框状态（该类别有未勾选项则类别不勾选）
        cid = item.cleaner_id
        all_checked = all(i.checked for i in self.items.values() if i.cleaner_id == cid)
        self.category_vars[cid].set(all_checked)
        self._refresh_summary()

    def _refresh_summary(self):
        selected = sum(i.size for i in self.items.values() if i.checked)
        total = sum(i.size for i in self.items.values())
        self.summary_var.set(f"已选 {human_size(selected)} / 共 {human_size(total)}")

    # ---------- 清理 ----------

    def start_clean(self):
        if self._busy:
            return
        selected = [i for i in self.items.values() if i.checked]
        if not selected:
            tk.messagebox.showinfo("C盘清理工具", "没有勾选任何清理项。")
            return
        freed = sum(i.size for i in selected)
        permanent = sum(1 for i in selected if not i.to_recycle)
        if not tk.messagebox.askyesno(
            "确认清理",
            f"将清理 {len(selected)} 项，预计释放 {human_size(freed)}。\n\n"
            f"高风险项（软件残留）会移入回收站，可恢复；"
            f"其余 {permanent} 项（含 Windows.old 等）将被永久删除、无法恢复。\n\n继续？",
        ):
            return
        self._busy = True
        self.rescan_btn.state(["disabled"])
        self.clean_btn.state(["disabled"])
        self.progress.configure(mode="determinate", maximum=len(selected), value=0)
        self.status_var.set("正在清理…")
        self._result_ok = []
        self._result_fail = []
        self._result_freed = []
        CleanWorker(selected, Deleter(), self.msg_queue).start()

    def _on_item_done(self, i: int, total: int, item: CleanItem, ok: bool, reason: str, freed: int):
        self.progress.configure(value=i)
        if ok:
            self.status_var.set(f"正在清理… {i}/{total}")
            self._result_ok.append(item)
            self._result_freed.append(freed)
        else:
            self.status_var.set(f"清理失败: {item.label}（{reason}）")
            self._result_fail.append((item, reason))

    def _on_clean_finished(self):
        self.progress.configure(value=0)
        self.status_var.set("清理完成，重新扫描以查看结果")
        self._show_result()
        self._busy = False
        self.rescan_btn.state(["!disabled"])
        self.clean_btn.state(["!disabled"])

    def _show_result(self):
        # 汇总统计（从消息队列读取完整明细，见 _handle 的收集）
        win = tk.Toplevel(self)
        win.title("清理结果")
        win.geometry("560x400")
        text = tk.Text(win, wrap="none")
        scroll = ttk.Scrollbar(win, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        total_freed = sum(self._result_freed)
        ok_count = len(self._result_ok)
        fail_count = len(self._result_fail)
        lines = [
            f"成功：{ok_count} 项",
            f"失败：{fail_count} 项",
            f"预计释放空间（按扫描大小统计）：{human_size(total_freed)}",
            "",
            "失败明细：",
        ]
        for item, reason in self._result_fail:
            lines.append(f"  ✗ {item.label} — {reason}")
        text.insert("1.0", "\n".join(lines))
        text.configure(state="disabled")

    # ---------- 消息泵 ----------

    def _poll(self):
        try:
            while True:
                self._handle(self.msg_queue.get_nowait())
        except queue.Empty:
            pass
        except Exception as exc:
            # 消息泵不能被一条坏消息杀死：记录并继续，UI 状态不能冻结
            print(f"消息处理异常: {exc}", file=sys.stderr)
        finally:
            self.after(100, self._poll)

    def _handle(self, msg):
        kind = msg[0]
        if kind == "category_start":
            pass
        elif kind == "category_done":
            self._on_category_done(msg[1], msg[2])
        elif kind == "category_error":
            self._on_category_error(msg[1], msg[2])
        elif kind == "scan_finished":
            self._on_scan_finished()
        elif kind == "item_done":
            self._on_item_done(msg[1], msg[2], msg[3], msg[4], msg[5], msg[6])
        elif kind == "clean_finished":
            self._on_clean_finished()
        elif kind == "clean_error":
            self.status_var.set(f"清理异常: {msg[1]}")



def main():
    app = CleanerApp()
    app.mainloop()
