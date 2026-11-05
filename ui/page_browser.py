# -*- coding: utf-8 -*-
"""浏览器劫持修复页（Edge 为重点）"""
import os
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
        label(head, "浏览器劫持修复", font=T.F_TITLE, bg=T.BG).pack(side="left")
        Badge(head, "Edge / Chrome", "info", bg=T.BG).pack(side="left", padx=(10, 0), pady=(6, 0))

        hint(self, "360 劫持浏览器只靠三招：改快捷方式参数、写组策略、改用户配置。\n"
                   "组策略优先级最高——这就是为什么你在 Edge 设置里怎么改都会被改回来。"
                   "这里把三处一起查出来，逐条恢复。",
             bg=T.BG).pack(anchor="w", padx=24, pady=(8, 0))

        bar = tk.Frame(self, bg=T.BG)
        bar.pack(fill="x", padx=24, pady=(14, 8))

        self.btn_scan = RoundButton(bar, "开始检查", self.scan,
                                    kind="primary", width=110, height=34)
        self.btn_scan.pack(side="left")

        self.cnt_lbl = hint(bar, "尚未检查", font=T.F_SMALL)
        self.cnt_lbl.pack(side="left", padx=12)

        self.btn_fix = RoundButton(bar, "一键修复", self.do_fix,
                                   kind="danger", width=104, height=34)
        self.btn_fix.pack(side="right")
        self.btn_fix.set_enabled(False)

        self.btn_reset = RoundButton(bar, "彻底恢复原始浏览器", self.do_full_reset,
                                     kind="soft", width=156, height=34)
        self.btn_reset.pack(side="right", padx=(0, 8))

        RoundButton(bar, "全不选", lambda: self.tree.set_all(False),
                    kind="ghost", width=70, height=34).pack(side="right", padx=(0, 8))
        RoundButton(bar, "全选", lambda: self.tree.set_all(True),
                    kind="ghost", width=64, height=34).pack(side="right", padx=(0, 8))

        box = Card(self, padx=0, pady=0)
        box.pack(fill="both", expand=True, padx=24, pady=(0, 8))
        self.tree = CheckTree(box.inner, ["项目", "类型", "具体情况"],
                              widths=[280, 92, 560], height=14,
                              on_toggle=lambda i, c: self._update_count())
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)

        foot = tk.Frame(self, bg=T.BG)
        foot.pack(fill="x", padx=24, pady=(0, 16))
        hint(foot, "修复前请先完全退出 Edge（任务栏图标右键 → 退出，或任务管理器结束 msedge.exe），"
                   "否则浏览器的改动会被它自己写回。", bg=T.BG, fg=T.TEXT_SUB,
             font=T.F_TINY).pack(anchor="w")

    # ========================================================
    def on_show(self):
        if self.app.state.get("scanbrowser") is not None and not self.items:
            self._render(self.app.state["scanbrowser"])

    def scan(self):
        self.btn_scan.set_enabled(False)
        self.btn_scan.set_text("检查中…")
        from core import mod_edge
        pcb = self.app.progress_cb

        def done(items):
            self.app.state["scanbrowser"] = items
            self.btn_scan.set_enabled(True)
            self.btn_scan.set_text("重新检查")
            self._render(items)

        self.app.run_async(lambda: mod_edge.scan(progress=pcb), on_done=done,
                           on_error=lambda e: (self.btn_scan.set_enabled(True),
                                               self.btn_scan.set_text("重新检查"),
                                               messagebox.showerror("检查失败", str(e))))

    def _render(self, items):
        self.tree.clear()
        self.items.clear()
        for it in items:
            self.tree.add(it["id"], it["name"],
                          [it["category"], it["detail"].replace("\n", "  ")],
                          checked=bool(it.get("default_checked",
                                              it["level"] == "high")))
            self.items[it["id"]] = it
        if items:
            n_def = len([x for x in items if x.get("default_checked")])
            self.cnt_lbl.configure(text="发现 %d 处异常（已预选 %d 处）"
                                        % (len(items), n_def))
        else:
            self.cnt_lbl.configure(text="✓ 没有发现劫持痕迹")
        self._update_count()

    def _update_count(self):
        n = self.tree.checked_count()
        self.btn_fix.set_enabled(n > 0)
        self.btn_fix.set_text("一键修复 (%d)" % n if n else "一键修复")

    # ========================================================
    def do_fix(self):
        ids = self.tree.get_checked()
        if not ids:
            return
        sel = [self.items[i] for i in ids]

        from core import mod_edge
        if mod_edge._browser_running():
            if not messagebox.askyesno("浏览器还在运行",
                                       "检测到 Edge/Chrome 正在运行。\n\n"
                                       "现在修复的话，部分设置可能在浏览器重启后被覆盖。\n"
                                       "建议先关闭浏览器。\n\n仍要继续吗？"):
                return

        if not messagebox.askyesno("确认修复",
                                   "将修复 %d 处设置，全部可还原。\n\n"
                                   "· 组策略会被删除（这是关键，它是浏览器里改不掉的原因）\n"
                                   "· 快捷方式参数会被清空\n"
                                   "· 主页/启动页/默认搜索会被重置\n\n继续吗？" % len(sel)):
            return

        from core import utils
        pcb = self.app.progress_cb
        batch = utils.BackupBatch(title="修复浏览器劫持（%d 处）" % len(sel))

        self.btn_fix.set_enabled(False)
        self.app.set_status("正在修复…")

        def done(res):
            ok, fail, msgs = res
            warns = [m for m in msgs if m.startswith("⚠")]
            errs = [m for m in msgs if m.startswith("✗")]
            body = "成功修复 %d 处，失败 %d 处。" % (ok, fail)
            if errs:
                body += "\n\n失败：\n" + "\n".join(errs[:6])
            if warns:
                body += "\n\n" + "\n".join(warns)
            body += "\n\n备份批次：%s" % batch.batch_id
            if fail:
                messagebox.showwarning("修复完成", body)
            else:
                messagebox.showinfo("修复完成", body)

            self.app.set_status("浏览器修复完成：成功 %d，失败 %d" % (ok, fail))
            self.scan()   # 复查

        self.app.run_async(lambda: mod_edge.fix(sel, batch, progress=pcb),
                           on_done=done)

    # ========================================================
    def do_full_reset(self):
        """一键把 Edge/Chrome 恢复出厂状态"""
        if not messagebox.askyesno(
                "彻底恢复原始浏览器",
                "这一步会把 Edge 和 Chrome 恢复到刚装好的状态：\n\n"
                "· 删除全部浏览器组策略（包括锁主页、锁搜索、强制扩展）\n"
                "· 清空所有快捷方式里的劫持参数\n"
                "· 重置所有用户配置：启动页/主页/新标签页/默认搜索引擎\n"
                "· 文件关联恢复为 Edge 打开\n\n"
                "⚠ 你自己的个性化设置（自定义主页等）也会一并重置。\n"
                "所有改动先备份，可在「恢复中心」还原。\n\n继续吗？"):
            return

        from core import mod_edge
        if mod_edge._browser_running():
            if not messagebox.askyesno("浏览器还在运行",
                                       "检测到 Edge/Chrome 正在运行。\n\n"
                                       "不关闭的话配置可能被浏览器写回覆盖。\n"
                                       "建议先退出浏览器。\n\n仍要继续吗？"):
                return

        from core import utils
        pcb = self.app.progress_cb
        batch = utils.BackupBatch(title="彻底恢复原始浏览器")

        self.btn_reset.set_enabled(False)
        self.app.set_status("正在恢复浏览器…")

        def done(res):
            ok, fail, msgs = res
            errs = [m for m in msgs if m.startswith("✗")]
            body = "处理 %d 项：成功 %d，失败 %d。\n\n" % (ok + fail, ok, fail)
            body += "\n".join(msgs[:14])
            if len(msgs) > 14:
                body += "\n…（详见日志）"
            body += "\n\n备份批次：%s" % batch.batch_id
            if fail:
                messagebox.showwarning("恢复完成", body)
            else:
                messagebox.showinfo("恢复完成", body)
            self.app.set_status("浏览器已恢复原始状态（成功 %d，失败 %d）" % (ok, fail))
            self.btn_reset.set_enabled(True)
            self.scan()

        self.app.run_async(lambda: mod_edge.full_reset(batch, progress=pcb),
                           on_done=done)
