# -*- coding: utf-8 -*-
"""
CleanMaster — Windows 清理与反流氓工具
主程序：窗口框架 / 左侧导航 / 全局状态 / 异步任务
"""
import os
import sys
import traceback
import threading
import tkinter as tk
from tkinter import ttk, messagebox

# 保证以脚本方式启动时能 import 包内模块
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from ui import theme as T
from ui.widgets import RoundButton, label, hint, ScrollFrame

APP_TITLE = "CleanMaster · 电脑清理与反流氓工具"
APP_VERSION = "2.0.0"

NAV = [
    ("home",     "概览",       "◎"),
    ("clean360", "360 专清",   "◍"),
    ("browser",  "浏览器修复", "◈"),
    ("ads",      "广告查杀",   "⚡"),
    ("software", "软件管理",   "▤"),
    ("disk",     "磁盘清理",   "▣"),
    ("backup",   "恢复中心",   "↺"),
]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1180x780")
        self.minsize(1020, 680)
        self.configure(bg=T.BG)

        # 无界面自检模式（自动化测试用）
        if os.environ.get("CM_HEADLESS"):
            self.withdraw()

        try:
            self.iconbitmap(default="")
        except Exception:
            pass

        self._pages = {}
        self._nav_btns = {}
        self._current = None
        self._task_running = False

        # 共享状态
        self.state = {
            "scan360": None,
            "scanbrowser": None,
            "software": None,
            "junk": None,
            "health": {},
        }

        self._setup_style()
        self._build_topbar()
        self._build_body()
        self._build_statusbar()
        self._setup_exception_hook()

        self.show_page("home")

    # ========================================================
    # 样式
    # ========================================================
    def _setup_style(self):
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except Exception:
            pass
        try:
            self.option_add("*Font", T.F_BODY)
            self.option_add("*TCombobox*Listbox.font", T.F_BODY)
        except Exception:
            pass
        st.configure("TProgressbar", troughcolor="#EDEFF2", background=T.PRIMARY,
                     bordercolor="#EDEFF2", lightcolor=T.PRIMARY,
                     darkcolor=T.PRIMARY, thickness=4)
        st.configure("TScrollbar", background="#D8DCE2", troughcolor=T.BG,
                     borderwidth=0, arrowsize=12, relief="flat")
        st.map("TScrollbar", background=[("active", "#C2C8D0")])
        st.configure("TEntry", fieldbackground=T.CARD, bordercolor=T.BORDER,
                     lightcolor=T.BORDER, darkcolor=T.BORDER,
                     padding=6, relief="flat")
        st.configure("TCombobox", fieldbackground=T.CARD, bordercolor=T.BORDER,
                     padding=5)

    # ========================================================
    # 顶部栏
    # ========================================================
    def _build_topbar(self):
        bar = tk.Frame(self, bg=T.CARD, height=60)
        bar.pack(side="top", fill="x")
        bar.pack_propagate(False)
        tk.Frame(self, bg=T.BORDER, height=1).pack(side="top", fill="x")

        left = tk.Frame(bar, bg=T.CARD)
        left.pack(side="left", padx=20)

        # logo 方块
        cv = tk.Canvas(left, width=32, height=32, bg=T.CARD, highlightthickness=0)
        cv.pack(side="left", pady=14)
        cv.create_rectangle(2, 2, 30, 30, fill=T.PRIMARY, outline="")
        cv.create_text(16, 16, text="C", fill="#fff",
                       font=(T.FONT_FAMILY, 15, "bold"))

        t = tk.Frame(left, bg=T.CARD)
        t.pack(side="left", padx=(10, 0))
        label(t, "CleanMaster", font=(T.FONT_FAMILY, 13, "bold")).pack(anchor="w")
        hint(t, "清理 360 · 识别流氓软件 · 释放磁盘", font=T.F_TINY).pack(anchor="w")

        right = tk.Frame(bar, bg=T.CARD)
        right.pack(side="right", padx=20)

        self.admin_lbl = tk.Label(right, text="", font=T.F_TINY, bg=T.CARD)
        self.admin_lbl.pack(side="right", padx=(10, 0))
        self.admin_btn = RoundButton(right, "以管理员身份重启", self.ask_admin,
                                     kind="soft", width=140, height=30,
                                     font=T.F_TINY)
        self.admin_btn.pack(side="right")
        self._refresh_admin()
        label(right, "v" + APP_VERSION, font=T.F_TINY,
              fg=T.TEXT_MUTED).pack(side="right", padx=(0, 12))

    def _refresh_admin(self):
        from core import utils
        if utils.is_admin():
            self.admin_lbl.configure(text="● 管理员模式", fg=T.OK)
            self.admin_btn.pack_forget()
        else:
            self.admin_lbl.configure(text="○ 普通模式", fg=T.WARN)
            self.admin_btn.pack(side="right")

    def ask_admin(self):
        from core import utils
        if messagebox.askyesno("需要管理员权限",
                               "清理 360 服务、驱动和系统级残留需要管理员权限。\n"
                               "现在以管理员身份重新启动吗？\n\n"
                               "（不重启也能扫描，但部分项目无法清理）"):
            if utils.relaunch_as_admin():
                self.destroy()
            else:
                messagebox.showerror("提权失败", "未能获取管理员权限，可能是被安全软件拦截。")

    # ========================================================
    # 主体
    # ========================================================
    def _build_body(self):
        body = tk.Frame(self, bg=T.BG)
        body.pack(side="top", fill="both", expand=True)

        # 侧边栏
        side = tk.Frame(body, bg=T.SIDEBAR, width=196)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Frame(body, bg=T.BORDER, width=1).pack(side="left", fill="y")

        wrap = tk.Frame(side, bg=T.SIDEBAR)
        wrap.pack(fill="x", pady=(14, 0))

        for key, text, icon in NAV:
            holder = tk.Frame(wrap, bg=T.SIDEBAR)
            holder.pack(fill="x", padx=10, pady=1)
            b = _NavItem(holder, icon, text, lambda k=key: self.show_page(k))
            b.pack(fill="x")
            self._nav_btns[key] = b

        # 底部提示
        foot = tk.Frame(side, bg=T.SIDEBAR)
        foot.pack(side="bottom", fill="x", padx=16, pady=14)
        hint(foot, "所有清理动作都会先备份\n可在「恢复中心」一键还原",
             fg=T.TEXT_MUTED, bg=T.SIDEBAR, font=T.F_TINY).pack(anchor="w")

        # 内容区
        self.container = tk.Frame(body, bg=T.BG)
        self.container.pack(side="left", fill="both", expand=True)

    # ========================================================
    # 状态栏
    # ========================================================
    def _build_statusbar(self):
        tk.Frame(self, bg=T.BORDER, height=1).pack(side="bottom", fill="x")
        bar = tk.Frame(self, bg=T.CARD, height=34)
        bar.pack(side="bottom", fill="x")
        bar.pack_propagate(False)

        self.status_lbl = tk.Label(bar, text="就绪", font=T.F_TINY,
                                   fg=T.TEXT_SUB, bg=T.CARD, anchor="w")
        self.status_lbl.pack(side="left", padx=16)

        self.pbar = ttk.Progressbar(bar, mode="determinate", length=180)
        self._pbar_visible = False

    def set_status(self, text):
        self.status_lbl.configure(text=text)

    def set_progress(self, msg=None, pct=None):
        def _do():
            if msg is not None:
                self.status_lbl.configure(text=msg)
            if pct is not None:
                if not self._pbar_visible:
                    self.pbar.pack(side="right", padx=16)
                    self._pbar_visible = True
                self.pbar["value"] = pct
                if pct >= 100:
                    self.after(600, self._hide_pbar)
        self.after(0, _do)

    def _hide_pbar(self):
        try:
            self.pbar.pack_forget()
            self._pbar_visible = False
        except Exception:
            pass

    # ========================================================
    # 页面切换
    # ========================================================
    def show_page(self, key):
        if self._current == key:
            return
        # 懒加载
        if key not in self._pages:
            try:
                mod = __import__("ui.page_" + key, fromlist=["Page"])
                self._pages[key] = mod.Page(self.container, app=self)
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("页面加载失败", "%s\n\n%s" % (key, e))
                return

        for k, b in self._nav_btns.items():
            b.set_active(k == key)

        if self._current and self._current in self._pages:
            self._pages[self._current].pack_forget()
        self._pages[key].pack(fill="both", expand=True)
        self._current = key

        # 每次进入刷新一次
        try:
            fn = getattr(self._pages[key], "on_show", None)
            if fn:
                fn()
        except Exception:
            traceback.print_exc()

    # ========================================================
    # 异步执行
    # ========================================================
    def run_async(self, target, on_done=None, on_error=None):
        if self._task_running:
            messagebox.showinfo("请稍候", "上一个任务还在进行中。")
            return
        self._task_running = True

        def worker():
            try:
                r = target()
                self.after(0, lambda: self._async_done(r, on_done))
            except Exception as e:
                tb = traceback.format_exc()
                self.after(0, lambda: self._async_err(e, tb, on_error))

        threading.Thread(target=worker, daemon=True).start()

    def _async_done(self, result, cb):
        self._task_running = False
        self._hide_pbar()
        if cb:
            try:
                cb(result)
            except Exception:
                traceback.print_exc()

    def _async_err(self, e, tb, cb):
        self._task_running = False
        self._hide_pbar()
        from core import utils
        utils.log("异步任务异常: %s\n%s" % (e, tb), "ERR")
        if cb:
            cb(e)
        else:
            self.set_status("出错：%s" % e)
            messagebox.showerror("出错了", "%s\n\n详情已写入日志。" % e)

    def progress_cb(self, msg, pct):
        """传给后台线程用的进度回调"""
        self.after(0, lambda: self.set_progress(msg, pct if pct is not None else None))

    # ========================================================
    # 异常钩子
    # ========================================================
    def _setup_exception_hook(self):
        def hook(exc_type, exc_value, exc_tb):
            tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            try:
                from core import utils
                utils.log("未捕获异常:\n" + tb, "ERR")
            except Exception:
                pass
            sys.__excepthook__(exc_type, exc_value, exc_tb)
        sys.excepthook = hook


class _NavItem(tk.Frame):
    def __init__(self, master, icon, text, command):
        super().__init__(master, bg=T.SIDEBAR, cursor="hand2")
        self._active = False
        self._cmd = command

        self.bar = tk.Frame(self, bg=T.SIDEBAR, width=3)
        self.bar.pack(side="left", fill="y")

        self.row = tk.Frame(self, bg=T.SIDEBAR)
        self.row.pack(side="left", fill="both", expand=True)

        self.icon = tk.Label(self.row, text=icon, font=(T.FONT_FAMILY, 11),
                             bg=T.SIDEBAR, fg=T.TEXT_SUB)
        self.icon.pack(side="left", padx=(12, 8), pady=9)
        self.txt = tk.Label(self.row, text=text, font=T.F_BODY,
                            bg=T.SIDEBAR, fg=T.TEXT_SUB)
        self.txt.pack(side="left")

        for w in (self, self.row, self.icon, self.txt):
            w.bind("<Button-1>", lambda e: self._cmd())
            w.bind("<Enter>", lambda e: self._hover(True))
            w.bind("<Leave>", lambda e: self._hover(False))

    def _hover(self, on):
        if self._active:
            return
        bg = "#F7F9FC" if on else T.SIDEBAR
        for w in (self, self.row, self.icon, self.txt):
            w.configure(bg=bg)

    def set_active(self, v):
        self._active = v
        bg = T.SIDEBAR_SEL if v else T.SIDEBAR
        fg = T.PRIMARY if v else T.TEXT_SUB
        fgf = T.PRIMARY if v else T.TEXT
        for w in (self, self.row, self.icon, self.txt):
            w.configure(bg=bg)
        self.icon.configure(fg=fg)
        self.txt.configure(fg=fgf, font=(T.FONT_FAMILY, 10, "bold" if v else "normal"))
        self.bar.configure(bg=T.PRIMARY if v else bg)


def main():
    # 高 DPI 适配
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
