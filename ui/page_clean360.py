# -*- coding: utf-8 -*-
"""360 专清页"""
import os
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

from ui import theme as T
from ui.widgets import (Card, RoundButton, label, hint, CheckTree,
                        SectionTitle, Badge)


CATS = ["全部", "进程", "服务/驱动", "启动项", "计划任务",
        "安装目录", "注册表残留", "右键菜单", "浏览器扩展", "系统策略"]


class Page(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=T.BG)
        self.app = app
        self.items = {}          # iid -> item
        self._raw = []
        self._build()

    # ========================================================
    def _build(self):
        # 顶部
        head = tk.Frame(self, bg=T.BG)
        head.pack(fill="x", padx=24, pady=(18, 0))
        label(head, "360 全家桶专清", font=T.F_TITLE, bg=T.BG).pack(side="left")
        badge = Badge(head, "深度扫描", "info", bg=T.BG)
        badge.pack(side="left", padx=(10, 0), pady=(6, 0))

        hint_txt = ("扫描 360 的进程、服务、驱动、启动项、计划任务、安装目录、注册表残留、"
                    "右键菜单、浏览器扩展和系统策略。\n每条都标注了具体位置，勾选后清理，"
                    "清理前自动备份，误删可在「恢复中心」还原。")
        hint(self, hint_txt, bg=T.BG).pack(anchor="w", padx=24, pady=(8, 0))

        # 工具栏
        bar = tk.Frame(self, bg=T.BG)
        bar.pack(fill="x", padx=24, pady=(14, 8))

        self.btn_scan = RoundButton(bar, "开始扫描", self.scan,
                                    kind="primary", width=110, height=34)
        self.btn_scan.pack(side="left")

        self.cat_var = tk.StringVar(value="全部")
        self.cb = ttk.Combobox(bar, textvariable=self.cat_var, values=CATS,
                               state="readonly", width=12, font=T.F_SMALL)
        self.cb.pack(side="left", padx=(10, 0))
        self.cb.bind("<<ComboboxSelected>>", lambda e: self._apply_filter())

        self.search_var = tk.StringVar()
        ent = ttk.Entry(bar, textvariable=self.search_var, width=22, font=T.F_SMALL)
        ent.pack(side="left", padx=(8, 0))
        ent.insert(0, "")
        self.search_var.trace_add("write", lambda *a: self._apply_filter())

        self.btn_clear = RoundButton(bar, "清理选中", self.do_clean,
                                     kind="danger", width=104, height=34)
        self.btn_clear.pack(side="right")
        self.btn_clear.set_enabled(False)

        RoundButton(bar, "全不选", lambda: self.tree.set_all(False),
                    kind="ghost", width=70, height=34).pack(side="right", padx=(0, 8))
        RoundButton(bar, "全选", lambda: self.tree.set_all(True),
                    kind="ghost", width=64, height=34).pack(side="right", padx=(0, 8))

        self.cnt_lbl = hint(bar, "尚未扫描", font=T.F_SMALL)
        self.cnt_lbl.pack(side="right", padx=(0, 14))

        # 列表
        box = Card(self, padx=0, pady=0)
        box.pack(fill="both", expand=True, padx=24, pady=(0, 8))
        self.tree = CheckTree(box.inner, ["项目", "类型", "说明"],
                              widths=[300, 92, 520], height=14,
                              on_toggle=self._on_toggle)
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)

        # 底部提示
        foot = tk.Frame(self, bg=T.BG)
        foot.pack(fill="x", padx=24, pady=(0, 16))

        warn = tk.Frame(foot, bg=T.WARN_LT, highlightbackground="#F5E0B0",
                        highlightthickness=1)
        warn.pack(fill="x", pady=(0, 8))
        inner = tk.Frame(warn, bg=T.WARN_LT)
        inner.pack(fill="x", padx=12, pady=8)
        tk.Label(inner, text="⚠", font=T.F_BODY, fg="#9A6200", bg=T.WARN_LT).pack(side="left")
        hint(inner, "360 开启自我保护时，进程和服务可能删不掉。建议先在 360 里关闭自我保护，"
                    "或直接用下面的官方卸载器卸载主程序。",
             fg="#8A5A00", bg=T.WARN_LT, font=T.F_TINY).pack(side="left", padx=8)

        act = tk.Frame(foot, bg=T.BG)
        act.pack(fill="x")
        RoundButton(act, "调用 360 官方卸载器", self.run_official_uninstall,
                    kind="ghost", width=170, height=30, font=T.F_SMALL).pack(side="left")
        hint(act, "官方卸载更彻底，卸载完再回来扫残留", bg=T.BG,
             font=T.F_TINY).pack(side="left", padx=10)

    # ========================================================
    def on_show(self):
        if self.app.state.get("scan360") is not None and not self.items:
            self._render(self.app.state["scan360"])

    # ========================================================
    def scan(self):
        self.btn_scan.set_enabled(False)
        self.btn_scan.set_text("扫描中…")
        self.app.set_status("正在扫描 360 残留…")

        from core import mod_360
        pcb = self.app.progress_cb

        def task():
            return mod_360.scan(progress=pcb)

        self.app.run_async(task, on_done=self._on_scan, on_error=self._scan_err)

    def _scan_err(self, e):
        self.btn_scan.set_enabled(True)
        self.btn_scan.set_text("重新扫描")
        messagebox.showerror("扫描失败", str(e))

    def _on_scan(self, items):
        self.app.state["scan360"] = items
        self.btn_scan.set_enabled(True)
        self.btn_scan.set_text("重新扫描")
        self._render(items)

    def _render(self, items):
        self._raw = items
        self.tree.clear()
        self.items.clear()
        for it in items:
            iid = it["id"]
            # 默认只勾高风险的
            checked = it["level"] == "high"
            self.tree.add(iid, it["name"],
                          [it["category"], it["detail"].replace("\n", "  ")],
                          checked=checked)
            self.items[iid] = it
        self._apply_filter()
        self._update_count()

        if not items:
            self.app.set_status("没有发现 360 残留，很干净")
            self.cnt_lbl.configure(text="未发现 360 残留")

    def _apply_filter(self):
        cat = self.cat_var.get()
        kw = self.search_var.get().strip().lower()
        for iid in self.tree.tree.get_children(""):
            it = self.items.get(iid, {})
            ok_cat = (cat == "全部") or (it.get("category") == cat)
            blob = (it.get("name", "") + it.get("detail", "") + it.get("extra", "")).lower()
            ok_kw = (not kw) or (kw in blob)
            if ok_cat and ok_kw:
                self.tree.tree.reattach(iid, "", "end")
            else:
                self.tree.tree.detach(iid)
        self.tree._restripe() if hasattr(self.tree, "_restripe") else None

    def _on_toggle(self, iid, checked):
        self._update_count()

    def _update_count(self):
        n = self.tree.checked_count()
        total = self.tree.count()
        self.cnt_lbl.configure(text="共 %d 项 · 已选 %d 项" % (total, n))
        self.btn_clear.set_enabled(n > 0)
        self.btn_clear.set_text("清理选中 (%d)" % n if n else "清理选中")

    # ========================================================
    def do_clean(self):
        ids = self.tree.get_checked()
        if not ids:
            messagebox.showinfo("提示", "还没有勾选任何项目。")
            return

        sel = [self.items[i] for i in ids]
        cats = {}
        for it in sel:
            cats[it["category"]] = cats.get(it["category"], 0) + 1
        detail = "\n".join("  · %s  %d 项" % (k, v) for k, v in cats.items())

        if not messagebox.askyesno(
                "确认清理",
                "即将处理 %d 个项目：\n\n%s\n\n"
                "所有改动都会先备份（注册表导出 + 文件移到隔离区），\n"
                "万一出问题可以在「恢复中心」一键还原。\n\n"
                "继续吗？" % (len(sel), detail)):
            return

        from core import mod_360, utils
        pcb = self.app.progress_cb
        batch = utils.BackupBatch(title="清理 360 残留（%d 项）" % len(sel))

        def task():
            return mod_360.clean(sel, batch, progress=pcb)

        self.btn_clear.set_enabled(False)
        self.app.set_status("正在清理…")
        self.app.run_async(task, on_done=lambda r: self._done(r, batch, ids))

    def _done(self, res, batch, ids):
        ok, fail, msgs = res
        for iid in ids:
            try:
                self.tree.tree.delete(iid)
                self.items.pop(iid, None)
            except Exception:
                pass
        self._update_count()

        if fail == 0:
            messagebox.showinfo("清理完成",
                                "成功处理 %d 项。\n\n备份批次：%s\n"
                                "如需还原请到「恢复中心」。" % (ok, batch.batch_id))
        else:
            fails = [m for m in msgs if m.startswith("✗")]
            messagebox.showwarning(
                "部分完成",
                "成功 %d 项，失败 %d 项。\n\n失败项通常是正在运行 / 有自我保护的程序：\n\n%s\n\n"
                "建议：先在 360 里关闭自我保护，或以管理员身份重启本工具后重试。"
                % (ok, fail, "\n".join(fails[:8])))

        self.app.set_status("清理完成：成功 %d，失败 %d（备份 %s）"
                            % (ok, fail, batch.batch_id))

    # ========================================================
    def run_official_uninstall(self):
        from core import mod_360
        self.app.set_status("正在查找 360 卸载程序…")

        def task():
            return mod_360.find_all_uninstallers()

        def done(lst):
            if not lst:
                messagebox.showinfo(
                    "没有找到",
                    "没有找到 360 的官方卸载程序。\n\n"
                    "可能是已经卸载过、只剩残留，或者安装位置比较特殊。\n"
                    "这种情况下直接用上面的扫描 + 清理处理残留即可。")
                return
            names = "\n".join("%d. %s\n    %s" % (i + 1, x.get("name") or os.path.basename(x["dir"]) or x["dir"],
                                                 x["uninstaller"])
                              for i, x in enumerate(lst[:9]))
            if messagebox.askyesno(
                    "找到 %d 个卸载程序" % len(lst),
                    "%s\n\n现在启动第一个吗？\n（会弹出 360 自己的卸载界面，按提示操作即可）"
                    % names):
                try:
                    subprocess.Popen('"%s"' % lst[0]["uninstaller"], shell=True)
                    self.app.set_status("已启动 360 卸载程序")
                except Exception as e:
                    messagebox.showerror("启动失败", str(e))

        self.app.run_async(task, on_done=done)
