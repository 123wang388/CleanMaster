# -*- coding: utf-8 -*-
"""恢复中心：每一次清理的备份批次，可回滚"""
import os
import tkinter as tk
from tkinter import ttk, messagebox

from ui import theme as T
from ui.widgets import Card, RoundButton, label, hint, Badge, _hs


class Page(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=T.BG)
        self.app = app
        self.batches = []
        self.sel = None
        self._build()

    def _build(self):
        head = tk.Frame(self, bg=T.BG)
        head.pack(fill="x", padx=24, pady=(18, 0))
        label(head, "恢复中心", font=T.F_TITLE, bg=T.BG).pack(side="left")
        hint(self, "每次清理都会生成一个备份批次：注册表导出成 .reg 文件，被移走的文件放在隔离区。\n"
                   "选一个批次点「还原」，它会把这些改动按倒序恢复回去。",
             bg=T.BG).pack(anchor="w", padx=24, pady=(8, 0))

        bar = tk.Frame(self, bg=T.BG)
        bar.pack(fill="x", padx=24, pady=(14, 8))
        RoundButton(bar, "刷新", self.refresh, kind="ghost",
                    width=72, height=32, font=T.F_SMALL).pack(side="left")
        self.cnt = hint(bar, "", font=T.F_SMALL)
        self.cnt.pack(side="left", padx=12)

        self.btn_restore = RoundButton(bar, "还原这个批次", self.do_restore,
                                       kind="primary", width=132, height=32)
        self.btn_restore.pack(side="right")
        self.btn_restore.set_enabled(False)

        self.btn_del = RoundButton(bar, "删除备份", self.del_batch,
                                   kind="ghost", width=90, height=32, font=T.F_SMALL)
        self.btn_del.pack(side="right", padx=(0, 8))
        self.btn_del.set_enabled(False)

        # 左右分栏
        main = tk.Frame(self, bg=T.BG)
        main.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        left = Card(main, padx=0, pady=0)
        left.pack(side="left", fill="both", expand=True)

        cols = ("time", "count", "size", "state")
        self.tree = ttk.Treeview(left.inner, columns=cols, show="tree headings",
                                 style="CM.Treeview", selectmode="browse", height=14)
        self.tree.column("#0", width=280, stretch=True)
        self.tree.heading("#0", text="操作", anchor="w")
        for c, w, t in (("time", 140, "时间"), ("count", 60, "改动"),
                        ("size", 80, "占用"), ("state", 80, "状态")):
            self.tree.column(c, width=w, stretch=False, anchor="w")
            self.tree.heading(c, text=t, anchor="w")

        vsb = ttk.Scrollbar(left.inner, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        vsb.pack(side="right", fill="y", pady=8, padx=(0, 8))
        self.tree.bind("<<TreeviewSelect>>", self._on_sel)

        right = Card(main, padx=16, pady=14, width=320)
        right.pack(side="right", fill="y", padx=(12, 0))
        right.pack_propagate(False)
        self.detail = tk.Frame(right.inner, bg=T.CARD)
        self.detail.pack(fill="both", expand=True)

    # ========================================================
    def on_show(self):
        self.refresh()

    def refresh(self):
        from core import utils
        self.batches = utils.list_batches()
        for iid in self.tree.get_children(""):
            self.tree.delete(iid)
        for i, b in enumerate(self.batches):
            state = "已还原" if b.get("restored") else "可还原"
            n = len([a for a in b.get("actions", []) if a.get("type") != "note"])
            self.tree.insert("", "end", iid=str(i),
                             text=b.get("title") or "清理操作",
                             values=(b.get("created_str", ""), "%d 项" % n,
                                     _hs(b.get("_size", 0)), state))
        self.cnt.configure(text="共 %d 个批次" % len(self.batches))
        self.btn_restore.set_enabled(False)
        self.btn_del.set_enabled(False)
        self._empty()

    def _empty(self):
        for w in self.detail.winfo_children():
            w.destroy()
        hint(self.detail, "选择左边一个批次，\n可以看到它具体改了什么。",
             fg=T.TEXT_MUTED).pack(anchor="w", pady=20)

    def _on_sel(self, e):
        s = self.tree.selection()
        if not s:
            return
        b = self.batches[int(s[0])]
        self.sel = b
        self.btn_restore.set_enabled(not b.get("restored"))
        self.btn_del.set_enabled(True)
        self._show(b)

    def _show(self, b):
        for w in self.detail.winfo_children():
            w.destroy()

        label(self.detail, b.get("title") or "清理操作", font=T.F_H2,
              wraplength=280, justify="left").pack(anchor="w")
        hint(self.detail, b.get("created_str", ""), fg=T.TEXT_MUTED,
             font=T.F_TINY).pack(anchor="w", pady=(4, 0))

        row = tk.Frame(self.detail, bg=T.CARD)
        row.pack(anchor="w", pady=(8, 0))
        Badge(row, "已还原" if b.get("restored") else "可还原",
              "trusted" if b.get("restored") else "info").pack(side="left")
        tk.Label(row, text="  包体 %s" % _hs(b.get("_size", 0)), font=T.F_TINY,
                 fg=T.TEXT_SUB, bg=T.CARD).pack(side="left")

        tk.Frame(self.detail, bg=T.BORDER_SOFT, height=1).pack(fill="x", pady=10)

        label(self.detail, "改动清单", font=T.F_SMALL, fg=T.TEXT_SUB).pack(anchor="w")

        box = tk.Frame(self.detail, bg=T.CARD)
        box.pack(fill="both", expand=True, pady=(6, 0))

        cv = tk.Canvas(box, bg=T.CARD, highlightthickness=0)
        vs = ttk.Scrollbar(box, orient="vertical", command=cv.yview)
        inner = tk.Frame(cv, bg=T.CARD)
        cv.create_window((0, 0), window=inner, anchor="nw", width=272)
        cv.configure(yscrollcommand=vs.set)
        cv.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        inner.bind("<Configure>",
                   lambda e: cv.configure(scrollregion=cv.bbox("all")))

        acts = b.get("actions", [])
        if not acts:
            hint(inner, "（无记录）").pack(anchor="w")
        for a in acts[:120]:
            f = tk.Frame(inner, bg=T.CARD)
            f.pack(fill="x", pady=1)
            icon = {"reg_key": "▤", "reg_value": "▤", "file": "▣",
                    "file_copy": "▣", "note": "·"}.get(a.get("type"), "·")
            col = T.TEXT_MUTED if a.get("type") == "note" else T.PRIMARY
            tk.Label(f, text=icon, font=T.F_TINY, fg=col, bg=T.CARD).pack(side="left")
            tk.Label(f, text=str(a.get("label", ""))[:60], font=T.F_TINY,
                     fg=T.TEXT_SUB if a.get("type") == "note" else T.TEXT,
                     bg=T.CARD, anchor="w", justify="left",
                     wraplength=240).pack(side="left", padx=4, fill="x")

    # ========================================================
    def do_restore(self):
        b = self.sel
        if not b:
            return
        if not messagebox.askyesno(
                "确认还原",
                "将把「%s」的全部改动恢复原状：\n\n"
                "· 注册表项会重新导入\n"
                "· 隔离区的文件会移回原位置\n"
                "· 快捷方式 / 浏览器配置会还原\n\n"
                "注意：如果之后系统又发生了变化，还原可能覆盖新状态。继续吗？"
                % (b.get("title") or b["batch_id"])):
            return

        from core import utils
        pcb = self.app.progress_cb
        bid = b["batch_id"]

        def done(res):
            ok, fail, fails = res
            if fail == 0:
                messagebox.showinfo("还原完成", "成功恢复 %d 项改动。" % ok)
            else:
                messagebox.showwarning(
                    "部分还原",
                    "成功 %d 项，失败 %d 项。\n\n%s" % (ok, fail, "\n".join(fails[:8])))
            self.app.set_status("还原完成：成功 %d，失败 %d" % (ok, fail))
            self.refresh()

        self.app.set_status("正在还原…")
        self.btn_restore.set_enabled(False)
        self.app.run_async(
            lambda: utils.restore_batch(bid, progress=lambda a: None),
            on_done=done)

    def del_batch(self):
        b = self.sel
        if not b:
            return
        if not messagebox.askyesno(
                "删除备份",
                "删除「%s」的备份记录和文件（%s）。\n\n"
                "删除后这个批次就无法再还原了。确定吗？"
                % (b.get("title") or b["batch_id"], _hs(b.get("_size", 0)))):
            return
        import shutil
        from core import utils
        d = b.get("_dir") or os.path.join(utils.BACKUP_DIR, b["batch_id"])
        # 安全限制：只能删备份目录内的
        if not os.path.abspath(d).startswith(os.path.abspath(utils.BACKUP_DIR)):
            messagebox.showerror("拒绝", "路径不在备份目录内，已取消。")
            return
        try:
            shutil.rmtree(d, ignore_errors=True)
            self.app.set_status("已删除备份 %s" % b["batch_id"])
            self.refresh()
        except Exception as e:
            messagebox.showerror("删除失败", str(e))
