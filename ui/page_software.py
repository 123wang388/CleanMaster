# -*- coding: utf-8 -*-
"""软件管理页：全部软件 + 流氓软件单独列出"""
import os
import tkinter as tk
from tkinter import ttk, messagebox

from ui import theme as T
from ui.widgets import Card, RoundButton, label, hint, Badge, _hs


FILTERS = [
    ("all", "全部软件"),
    ("high", "高风险"),
    ("mid", "需留意"),
    ("trusted", "可信"),
]


class Page(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=T.BG)
        self.app = app
        self.all_soft = []
        self.view = []
        self.sel = None
        self._build()

    # ========================================================
    def _build(self):
        head = tk.Frame(self, bg=T.BG)
        head.pack(fill="x", padx=24, pady=(18, 0))
        label(head, "软件管理", font=T.F_TITLE, bg=T.BG).pack(side="left")
        hint(self, "读取注册表里的全部已安装软件，用关键词模型给每个软件打风险分，"
                   "把流氓软件、捆绑软件单独标出来。\n评分只看证据，每一条都会写明命中了什么特征。",
             bg=T.BG).pack(anchor="w", padx=24, pady=(8, 0))

        # 工具栏
        bar = tk.Frame(self, bg=T.BG)
        bar.pack(fill="x", padx=24, pady=(14, 8))

        self.btn_scan = RoundButton(bar, "重新读取", self.scan,
                                    kind="primary", width=104, height=34)
        self.btn_scan.pack(side="left")

        self.chips = {}
        chip_box = tk.Frame(bar, bg=T.BG)
        chip_box.pack(side="left", padx=(12, 0))
        for key, text in FILTERS:
            b = RoundButton(chip_box, text, lambda k=key: self.set_filter(k),
                            kind="ghost", width=len(text) * 13 + 22, height=30,
                            font=T.F_SMALL)
            b.pack(side="left", padx=(0, 6))
            self.chips[key] = b

        self.search_var = tk.StringVar()
        ent = ttk.Entry(bar, textvariable=self.search_var, width=20, font=T.F_SMALL)
        ent.pack(side="right")
        self.search_var.trace_add("write", lambda *a: self._apply())
        hint(bar, "搜索", bg=T.BG, font=T.F_TINY).pack(side="right", padx=(0, 6))

        # 主区：左列表 + 右详情
        main = tk.Frame(self, bg=T.BG)
        main.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        left = Card(main, padx=0, pady=0)
        left.pack(side="left", fill="both", expand=True)
        right = Card(main, padx=18, pady=16, width=310)
        right.pack(side="right", fill="y", padx=(12, 0))
        right.pack_propagate(False)

        cols = ("ver", "pub", "risk", "size")
        self.tree = ttk.Treeview(left.inner, columns=cols, show="tree headings",
                                 style="CM.Treeview", selectmode="browse")
        self.tree.column("#0", width=250, stretch=True)
        self.tree.heading("#0", text="软件名称", anchor="w")
        for c, w, t in (("ver", 90, "版本"), ("pub", 170, "发布者"),
                        ("risk", 76, "风险"), ("size", 70, "体积")):
            self.tree.column(c, width=w, stretch=False, anchor="w")
            self.tree.heading(c, text=t, anchor="w")

        vsb = ttk.Scrollbar(left.inner, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        vsb.pack(side="right", fill="y", pady=8, padx=(0, 8))

        self.tree.tag_configure("high", foreground=T.DANGER)
        self.tree.tag_configure("mid", foreground="#A06400")
        self.tree.tag_configure("trusted", foreground=T.TEXT)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # 详情面板
        self.detail = tk.Frame(right.inner, bg=T.CARD)
        self.detail.pack(fill="both", expand=True)
        self._empty_detail()
        self.set_filter("all")

    # ========================================================
    def _empty_detail(self):
        for w in self.detail.winfo_children():
            w.destroy()
        hint(self.detail, "选中左边任意一个软件，\n这里会显示它的风险依据。",
             fg=T.TEXT_MUTED).pack(anchor="w", pady=20)

    def on_show(self):
        if self.app.state.get("software") and not self.all_soft:
            self.all_soft = self.app.state["software"]
            self._apply()
        elif not self.all_soft:
            self.scan()

    def scan(self):
        self.btn_scan.set_enabled(False)
        self.btn_scan.set_text("读取中…")
        from core import mod_software
        pcb = self.app.progress_cb

        def done(softs):
            self.all_soft = softs
            self.app.state["software"] = softs
            self.btn_scan.set_enabled(True)
            self.btn_scan.set_text("重新读取")
            self._apply()
            high = len([s for s in softs if s["level"] == "high"])
            self.app.set_status("共 %d 个软件，其中 %d 个高风险" % (len(softs), high))

        self.app.run_async(lambda: mod_software.list_installed(progress=pcb),
                           on_done=done)

    # ========================================================
    def set_filter(self, key):
        self._filter = key
        for k, b in self.chips.items():
            b.set_kind("soft" if k == key else "ghost")
        self._apply()

    def _apply(self):
        key = getattr(self, "_filter", "all")
        sv = getattr(self, "search_var", None)
        kw = sv.get().strip().lower() if sv is not None else ""

        self.view = []
        for s in self.all_soft:
            if key == "high" and s["level"] != "high":
                continue
            if key == "mid" and s["level"] != "mid":
                continue
            if key == "trusted" and s["level"] != "trusted":
                continue
            if kw:
                blob = ("%s %s %s" % (s["name"], s["publisher"], s["location"])).lower()
                if kw not in blob:
                    continue
            self.view.append(s)

        for iid in self.tree.get_children(""):
            self.tree.delete(iid)

        for s in self.view:
            lv = s["level"]
            risk = ("%d 分" % s["score"]) if lv in ("high", "mid") else \
                {"trusted": "可信", "low": "低"}.get(lv, "-")
            self.tree.insert("", "end", iid=s["name"] + "|" + s["reg_path"],
                             text=s["name"],
                             values=(s["version"] or "-",
                                     s["publisher"] or "（无）",
                                     risk,
                                     _hs(s["size"]) if s["size"] else "-"),
                             tags=(lv,))

    def _on_select(self, e):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        for s in self.view:
            if s["name"] + "|" + s["reg_path"] == iid:
                self.sel = s
                self._show_detail(s)
                return

    def _show_detail(self, s):
        for w in self.detail.winfo_children():
            w.destroy()

        lv = s["level"]
        color = T.LEVEL_COLOR.get(lv, T.TEXT_SUB)

        label(self.detail, s["name"], font=T.F_H2, wraplength=270,
              justify="left").pack(anchor="w")

        row = tk.Frame(self.detail, bg=T.CARD)
        row.pack(anchor="w", pady=(8, 0))
        Badge(row, T.LEVEL_TEXT.get(lv, lv), lv).pack(side="left")
        if lv in ("high", "mid"):
            tk.Label(row, text="  风险分 %d/100" % s["score"], font=T.F_TINY,
                     fg=color, bg=T.CARD).pack(side="left")

        tk.Frame(self.detail, bg=T.BORDER_SOFT, height=1).pack(fill="x", pady=12)

        def kv(k, v):
            f = tk.Frame(self.detail, bg=T.CARD)
            f.pack(fill="x", pady=3)
            tk.Label(f, text=k, font=T.F_TINY, fg=T.TEXT_MUTED, bg=T.CARD,
                     width=7, anchor="w").pack(side="left")
            tk.Label(f, text=v or "—", font=T.F_TINY, fg=T.TEXT, bg=T.CARD,
                     wraplength=210, justify="left", anchor="w").pack(side="left", fill="x")

        kv("版本", s["version"])
        kv("发布者", s["publisher"] or "（未提供）")
        kv("来源", s["scope"])
        kv("体积", _hs(s["size"]) if s["size"] else "未知")
        kv("安装", s["location"] or "未记录")

        tk.Frame(self.detail, bg=T.BORDER_SOFT, height=1).pack(fill="x", pady=12)

        label(self.detail, "判定依据", font=T.F_SMALL, fg=T.TEXT_SUB).pack(anchor="w")
        for r in s["reasons"][:8]:
            f = tk.Frame(self.detail, bg=T.CARD)
            f.pack(fill="x", pady=2)
            tk.Label(f, text="·", font=T.F_TINY, fg=color, bg=T.CARD).pack(side="left")
            tk.Label(f, text=r, font=T.F_TINY, fg=T.TEXT_SUB, bg=T.CARD,
                     wraplength=240, justify="left", anchor="w").pack(side="left", padx=4)

        # 操作
        tk.Frame(self.detail, bg=T.CARD, height=6).pack()
        btns = tk.Frame(self.detail, bg=T.CARD)
        btns.pack(fill="x", side="bottom", pady=(10, 0))

        if s.get("uninstall") or s.get("type") == "uwp":
            RoundButton(btns, "卸载这个软件", lambda: self.do_uninstall(s),
                        kind="danger" if lv == "high" else "ghost",
                        width=132, height=30, font=T.F_SMALL).pack(anchor="w")
        else:
            hint(btns, "该软件没有注册卸载入口，\n可先查残留手动清理",
                 fg=T.TEXT_MUTED, font=T.F_TINY).pack(anchor="w")

        RoundButton(btns, "扫描残留痕迹（注册表/目录/快捷方式）",
                    lambda: self.scan_traces(s),
                    kind="soft", width=252, height=30,
                    font=T.F_SMALL).pack(anchor="w", pady=(6, 0))

        if s.get("location") and os.path.isdir(s["location"]):
            RoundButton(btns, "打开安装目录",
                        lambda: os.startfile(s["location"]),
                        kind="ghost", width=132, height=28,
                        font=T.F_TINY).pack(anchor="w", pady=(6, 0))

    # ========================================================
    def do_uninstall(self, s):
        tip = ("「%s」\n\n发布者：%s\n版本：%s\n\n"
               "会调用它自己的卸载程序，卸载过程需要你手动确认。" % (
                   s["name"], s["publisher"] or "未知", s["version"] or "未知"))
        if s["level"] == "trusted":
            tip += "\n\n⚠ 这是可信软件，确认要卸载吗？"

        if not messagebox.askyesno("确认卸载", tip):
            return

        from core import mod_software
        self.app.set_status("正在启动卸载程序：%s" % s["name"])

        def done(res):
            ok, msg = res
            if ok:
                self.app.set_status("已启动卸载：%s" % s["name"])
                if s.get("type") == "uwp":
                    messagebox.showinfo("完成", "应用已移除。")
                    self.scan()
                else:
                    if messagebox.askyesno(
                            "卸载完成了吗？",
                            "卸载窗口已经弹出来了，按它自己的提示走完。\n\n"
                            "卸载完成后点「是」，我马上扫描它留下的残留——\n"
                            "注册表项、AppData 数据目录、开机自启、服务、计划任务、快捷方式，\n"
                            "扫出来你勾一下就能清干净。\n\n"
                            "（还没卸完的话点「否」，之后在详情里点「扫描并清理残留」也一样）"):
                        self.scan_traces(s)
                        self.scan()
            else:
                messagebox.showwarning("无法卸载", msg)

        self.app.run_async(lambda: mod_software.run_uninstall(s), on_done=done)

    # ========================================================
    # v2: 残留追踪与深度清除
    # ========================================================
    def scan_traces(self, s):
        """扫描某个软件的残留，勾选后清理"""
        top = tk.Toplevel(self)
        top.title("清理残留 - %s" % s["name"])
        top.geometry("840x600")
        top.configure(bg=T.BG)
        try:
            top.transient(self.winfo_toplevel())
        except Exception:
            pass

        head = tk.Frame(top, bg=T.BG)
        head.pack(fill="x", padx=20, pady=(16, 0))
        label(head, s["name"], font=T.F_H2, bg=T.BG).pack(anchor="w")
        st = hint(head, "正在扫描这个软件留下的痕迹…", bg=T.BG)
        st.pack(anchor="w", pady=(4, 0))

        pb = ttk.Progressbar(top, mode="indeterminate", length=320)
        pb.pack(anchor="w", padx=20, pady=6)
        pb.start(12)

        box = Card(top, padx=0, pady=0)
        box.pack(fill="both", expand=True, padx=20, pady=(4, 0))
        tv = CheckTree(box.inner, ["类别", "说明"], widths=[300, 460], height=14,
                       on_toggle=lambda i, c: update_btn())
        tv.pack(fill="both", expand=True, padx=8, pady=8)

        btns = tk.Frame(top, bg=T.BG)
        btns.pack(fill="x", padx=20, pady=12)

        state = {"items": {}}
        KIND_NAME = {"dir": "目录", "reg": "注册表", "run": "开机自启",
                     "service": "服务", "task": "计划任务",
                     "shortcut": "快捷方式"}
        ORDER = ["dir", "reg", "run", "service", "task", "shortcut"]

        def do_async(target, on_done):
            import threading

            def worker():
                try:
                    r = target()
                    self.app.after(0, lambda: on_done(r))
                except Exception as e:
                    self.app.after(0, lambda: messagebox.showerror(
                        "出错", str(e), parent=top))
            threading.Thread(target=worker, daemon=True).start()

        def update_btn():
            n = tv.checked_count()
            btn_del.set_enabled(n > 0)
            btn_del.set_text("清除勾选 (%d)" % n if n else "清除勾选")

        def render(items):
            pb.stop()
            pb.pack_forget()
            tv.clear()
            state["items"].clear()
            items = sorted(items, key=lambda x: ORDER.index(x["kind"])
                           if x["kind"] in ORDER else 9)
            for it in items:
                iid = it["kind"] + "|" + it["target"]
                state["items"][iid] = it
                tv.add(iid, it["label"],
                       [KIND_NAME.get(it["kind"], it["kind"]),
                        it["detail"].replace("\n", "  ")],
                       checked=bool(it.get("default", True)))
            if items:
                st.configure(text="找到 %d 处痕迹，已预选 %d 处。不想删的取消勾选即可。"
                             % (len(items), tv.checked_count()))
            else:
                st.configure(text="✓ 没有发现残留，这个软件卸载得很干净。")
            update_btn()

        def start_scan():
            from core import mod_software
            pcb = lambda msg, pct: self.app.after(
                0, lambda: st.configure(text=msg or "扫描中…"))
            do_async(lambda: mod_software.find_traces(s, progress=pcb), render)

        def remove_sel():
            ids = tv.get_checked()
            if not ids:
                messagebox.showinfo("提示", "还没有勾选任何项。", parent=top)
                return
            sel = [state["items"][i] for i in ids if i in state["items"]]
            if not messagebox.askyesno(
                    "确认清除",
                    "将清除 %d 处痕迹：\n"
                    "· 目录 / 快捷方式 → 移入隔离区，随时能还原\n"
                    "· 注册表 → 先导出备份再删除\n"
                    "· 服务 / 计划任务 → 备份后删除\n\n继续吗？" % len(sel),
                    parent=top):
                return
            from core import utils, mod_software
            batch = utils.BackupBatch(title="清除残留：%s" % s["name"])
            pcb = lambda msg, pct: self.app.after(
                0, lambda: st.configure(text=msg or "清除中…"))

            def done(res):
                okn, failn, msgs = res
                errs = [m for m in msgs if m.startswith("✗")]
                body = "成功 %d 项，失败 %d 项。" % (okn, failn)
                if errs:
                    body += "\n\n失败项（多为正在运行或权限不足）：\n" + \
                            "\n".join(errs[:8])
                body += "\n\n备份批次：%s\n在「恢复中心」可以整体还原。" % batch.batch_id
                if failn:
                    messagebox.showwarning("清除完成", body, parent=top)
                else:
                    messagebox.showinfo("清除完成", body, parent=top)
                start_scan()

            do_async(lambda: mod_software.remove_traces(sel, batch, progress=pcb), done)

        btn_del = RoundButton(btns, "清除勾选", remove_sel, kind="danger",
                              width=136, height=32)
        btn_del.pack(side="left")
        RoundButton(btns, "全不选", lambda: (tv.set_all(False), update_btn()),
                    kind="ghost", width=72, height=32).pack(side="left", padx=(8, 0))
        RoundButton(btns, "重新扫描", start_scan, kind="ghost",
                    width=96, height=32).pack(side="left", padx=(8, 0))
        RoundButton(btns, "关闭", top.destroy, kind="ghost",
                    width=72, height=32).pack(side="right")
        btn_del.set_enabled(False)

        start_scan()
