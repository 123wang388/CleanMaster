# -*- coding: utf-8 -*-
"""广告查杀页：找出并清除弹广告的东西"""
import tkinter as tk
from tkinter import messagebox

from ui import theme as T
from ui.widgets import Card, RoundButton, label, hint, CheckTree, Badge


class Page(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=T.BG)
        self.app = app
        self.items = {}
        self._build()

    def _build(self):
        head = tk.Frame(self, bg=T.BG)
        head.pack(fill="x", padx=24, pady=(18, 0))
        label(head, "广告查杀", font=T.F_TITLE, bg=T.BG).pack(side="left")
        Badge(head, "网页通知 · 弹窗 · 推送", "warn", bg=T.BG).pack(
            side="left", padx=(10, 0), pady=(6, 0))

        hint(self, "现在电脑上的弹窗广告，大部分其实来自「网页通知」——某个网站被你允许发通知，"
                   "关掉页面它照样弹。这类弹窗杀毒软件查不出来，因为它就是个正常网页。\n"
                   "剩下的是开机自启的推广程序、定时弹资讯的计划任务、以及 Windows 自带的推荐内容。"
                   "这里一次全查，每条都写清楚它凭什么弹广告。",
             bg=T.BG).pack(anchor="w", padx=24, pady=(8, 0))

        bar = tk.Frame(self, bg=T.BG)
        bar.pack(fill="x", padx=24, pady=(14, 8))

        self.btn_scan = RoundButton(bar, "开始扫描", self.scan,
                                    kind="primary", width=110, height=34)
        self.btn_scan.pack(side="left")

        self.cnt_lbl = hint(bar, "尚未扫描", font=T.F_SMALL)
        self.cnt_lbl.pack(side="left", padx=12)

        self.btn_kill = RoundButton(bar, "一键查杀", self.do_kill,
                                    kind="danger", width=104, height=34)
        self.btn_kill.pack(side="right")
        self.btn_kill.set_enabled(False)

        RoundButton(bar, "全不选", lambda: self.tree.set_all(False),
                    kind="ghost", width=70, height=34).pack(side="right", padx=(0, 8))
        RoundButton(bar, "全选", lambda: self.tree.set_all(True),
                    kind="ghost", width=64, height=34).pack(side="right", padx=(0, 8))

        box = Card(self, padx=0, pady=0)
        box.pack(fill="both", expand=True, padx=24, pady=(0, 8))
        self.tree = CheckTree(box.inner, ["项目", "来源", "详情"],
                              widths=[240, 100, 600], height=14,
                              on_toggle=lambda i, c: self._update_count())
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)

        hint(self, "提示：删除计划任务和服务需要管理员权限，普通模式下可能部分失败。",
             bg=T.BG, fg=T.TEXT_MUTED, font=T.F_TINY).pack(
            anchor="w", padx=24, pady=(0, 16))

    # ========================================================
    def scan(self):
        self.btn_scan.set_enabled(False)
        self.btn_scan.set_text("扫描中…")
        from core import mod_ads
        pcb = self.app.progress_cb

        def done(items):
            self.btn_scan.set_enabled(True)
            self.btn_scan.set_text("重新扫描")
            self._render(items)

        self.app.run_async(lambda: mod_ads.scan(progress=pcb), on_done=done,
                           on_error=lambda e: (self.btn_scan.set_enabled(True),
                                               self.btn_scan.set_text("重新扫描"),
                                               messagebox.showerror("扫描失败", str(e))))

    def _render(self, items):
        self.tree.clear()
        self.items.clear()
        for it in items:
            self.tree.add(it["id"], it["name"],
                          [it["category"], it["detail"].replace("\n", "  ")],
                          checked=bool(it.get("default_checked",
                                              it["level"] == "high")))
            self.items[it["id"]] = it
        n_high = len([x for x in items if x["level"] == "high"])
        n_def = len([x for x in items if x.get("default_checked")])
        if items:
            self.cnt_lbl.configure(
                text="发现 %d 项广告来源（高度可疑 %d 项，已预选 %d 项）"
                     % (len(items), n_high, n_def))
        else:
            self.cnt_lbl.configure(text="✓ 没有发现广告来源，电脑很干净")
        self._update_count()

    def _update_count(self):
        n = self.tree.checked_count()
        self.btn_kill.set_enabled(n > 0)
        self.btn_kill.set_text("一键查杀 (%d)" % n if n else "一键查杀")

    # ========================================================
    def do_kill(self):
        ids = self.tree.get_checked()
        if not ids:
            return
        sel = [self.items[i] for i in ids]

        if not messagebox.askyesno(
                "确认查杀",
                "将清除 %d 项广告来源。\n\n"
                "· 自启项/计划任务/服务会被删除（先备份）\n"
                "· 快捷方式会移入隔离区（可还原）\n"
                "· 相关的弹窗进程会被结束\n\n继续吗？" % len(sel)):
            return

        from core import utils, mod_ads
        pcb = self.app.progress_cb
        batch = utils.BackupBatch(title="广告查杀（%d 项）" % len(sel))

        self.btn_kill.set_enabled(False)
        self.app.set_status("正在查杀…")

        def done(res):
            ok, fail, msgs = res
            errs = [m for m in msgs if m.startswith("✗")]
            body = "清除成功 %d 项，失败 %d 项。" % (ok, fail)
            if errs:
                body += "\n\n失败：\n" + "\n".join(errs[:6])
            body += "\n\n备份批次：%s（失败多为权限问题，可点右上角以管理员身份重启后再扫）" % batch.batch_id
            if fail:
                messagebox.showwarning("查杀完成", body)
            else:
                messagebox.showinfo("查杀完成", body)
            self.app.set_status("广告查杀完成：成功 %d，失败 %d" % (ok, fail))
            self.scan()

        self.app.run_async(lambda: mod_ads.kill(sel, batch, progress=pcb),
                           on_done=done)
