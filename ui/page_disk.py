# -*- coding: utf-8 -*-
"""磁盘清理页：垃圾清理 / 大文件 / 空间分析"""
import os
import time
import tkinter as tk
from tkinter import ttk, messagebox

from ui import theme as T
from ui.widgets import (Card, RoundButton, label, hint, CheckTree,
                        SectionTitle, Badge, _hs)


class Page(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=T.BG)
        self.app = app
        self.junk = []
        self.large = []
        self._tab = "junk"
        self._build()

    # ========================================================
    def _build(self):
        head = tk.Frame(self, bg=T.BG)
        head.pack(fill="x", padx=24, pady=(18, 0))
        label(head, "磁盘清理", font=T.F_TITLE, bg=T.BG).pack(side="left")

        hint(self, "先看清楚磁盘里到底有什么，再决定删什么。所有删除都是你自己勾的，"
                   "工具不会自作主张。",
             bg=T.BG).pack(anchor="w", padx=24, pady=(8, 0))

        # 切换
        tabs = tk.Frame(self, bg=T.BG)
        tabs.pack(fill="x", padx=24, pady=(14, 10))
        self.tab_btns = {}
        for key, text, w in (("junk", "垃圾清理", 96),
                             ("large", "大文件", 84),
                             ("tree", "空间分析", 96),
                             ("inv", "分盘盘点", 96)):
            b = RoundButton(tabs, text, lambda k=key: self.switch(k),
                            kind="ghost", width=w, height=32, font=T.F_SMALL)
            b.pack(side="left", padx=(0, 8))
            self.tab_btns[key] = b

        self.area = tk.Frame(self, bg=T.BG)
        self.area.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        self.frames = {
            "junk": self._build_junk(self.area),
            "large": self._build_large(self.area),
            "tree": self._build_tree(self.area),
            "inv": self._build_inv(self.area),
        }
        self.switch("junk")

    def on_show(self):
        # 没扫过垃圾且首页体检没有结果时，不自动扫描，交给用户点按钮
        pass

    def switch(self, key):
        self._tab = key
        for k, b in self.tab_btns.items():
            b.set_kind("soft" if k == key else "ghost")
        for k, f in self.frames.items():
            f.pack_forget()
        self.frames[key].pack(fill="both", expand=True)
        if key == "tree":
            self._load_drives_tree()

    # ========================================================
    # 视图 1：垃圾清理
    # ========================================================
    def _build_junk(self, parent):
        f = tk.Frame(parent, bg=T.BG)

        bar = tk.Frame(f, bg=T.BG)
        bar.pack(fill="x", pady=(0, 8))

        self.btn_jscan = RoundButton(bar, "扫描垃圾", self.scan_junk,
                                     kind="primary", width=104, height=34)
        self.btn_jscan.pack(side="left")

        self.jcnt = hint(bar, "尚未扫描", font=T.F_SMALL)
        self.jcnt.pack(side="left", padx=12)

        self.btn_jclean = RoundButton(bar, "清理选中", self.clean_junk,
                                      kind="danger", width=104, height=34)
        self.btn_jclean.pack(side="right")
        self.btn_jclean.set_enabled(False)

        RoundButton(bar, "全不选", lambda: (self.jtree.set_all(False),
                                           self._jcount()),
                    kind="ghost", width=70, height=34).pack(side="right", padx=(0, 8))
        RoundButton(bar, "全选", lambda: (self.jtree.set_all(True),
                                          self._jcount()),
                    kind="ghost", width=64, height=34).pack(side="right", padx=(0, 8))

        box = Card(f, padx=0, pady=0)
        box.pack(fill="both", expand=True)
        self.jtree = CheckTree(box.inner, ["项目", "大小", "说明"],
                               widths=[230, 90, 500], height=13,
                               on_toggle=lambda i, c: self._jcount())
        self.jtree.pack(fill="both", expand=True, padx=8, pady=8)

        self.jnote = hint(f, "", fg=T.TEXT_MUTED, font=T.F_TINY)
        self.jnote.pack(anchor="w", pady=(8, 0))
        return f

    def scan_junk(self):
        self.btn_jscan.set_enabled(False)
        self.btn_jscan.set_text("扫描中…")
        from core import mod_disk
        pcb = self.app.progress_cb

        def done(items):
            self.junk = items
            self.app.state["junk"] = items
            self.btn_jscan.set_enabled(True)
            self.btn_jscan.set_text("重新扫描")
            self._render_junk(items)

        self.app.run_async(lambda: mod_disk.scan_junk(progress=pcb), on_done=done)

    def _render_junk(self, items):
        self.jtree.clear()
        self._jmap = {}
        for it in items:
            iid = it["key"]
            self._jmap[iid] = it
            size = _hs(it["size"])
            desc = it["desc"]
            if it["files"] > 0:
                desc += "（%d 个文件）" % it["files"]
            tag = {"safe": "", "careful": "[谨慎] ", "danger": "[不建议] "}.get(it["level"], "")
            self.jtree.add(iid, it["name"], [size, tag + desc],
                           checked=it["selected"])
        self._jcount()
        total = sum(i["size"] for i in items)
        self.jnote.configure(text="共找到 %s 可清理内容。标记[谨慎]的项目会移入隔离区而不是直接删除，"
                                  "可以还原。" % _hs(total))

    def _jcount(self):
        sel = sum(self._jmap[i]["size"] for i in self.jtree.get_checked()
                  if i in getattr(self, "_jmap", {}))
        n = self.jtree.checked_count()
        self.jcnt.configure(text="已选 %d 项 · 可释放 %s" % (n, _hs(sel)))
        self.btn_jclean.set_enabled(n > 0)
        self.btn_jclean.set_text("清理选中" if not n else "清理 %s" % _hs(sel))

    def clean_junk(self):
        ids = self.jtree.get_checked()
        if not ids:
            return
        sel = [self._jmap[i] for i in ids]
        total = sum(i["size"] for i in sel)

        risky = [i["name"] for i in sel if i["level"] in ("careful", "danger")]
        msg = "将清理 %d 项，预计释放 %s。\n\n" % (len(sel), _hs(total))
        if risky:
            msg += "以下项目会先移到隔离区（可还原）：\n" + "\n".join("  · " + r for r in risky[:6])
            msg += "\n\n"
        msg += "继续吗？"
        if not messagebox.askyesno("确认清理", msg):
            return

        from core import mod_disk, utils
        pcb = self.app.progress_cb
        batch = utils.BackupBatch(title="磁盘垃圾清理（%d 项，%s）" % (len(sel), _hs(total)))

        self.btn_jclean.set_enabled(False)
        self.app.set_status("正在清理…")

        def done(res):
            freed, ok, fail, msgs = res
            messagebox.showinfo("清理完成",
                                "释放了 %s\n成功 %d 项，失败 %d 项。\n\n"
                                "提示：部分缓存文件正被程序占用，关掉浏览器再扫一次能清得更干净。"
                                % (_hs(freed), ok, fail))
            self.app.set_status("清理完成，释放 %s" % _hs(freed))
            self.scan_junk()

        self.app.run_async(lambda: mod_disk.clean_junk(sel, batch, progress=pcb),
                           on_done=done)

    # ========================================================
    # 视图 2：大文件
    # ========================================================
    def _build_large(self, parent):
        f = tk.Frame(parent, bg=T.BG)

        bar = tk.Frame(f, bg=T.BG)
        bar.pack(fill="x", pady=(0, 8))

        self.btn_lscan = RoundButton(bar, "扫描大文件", self.scan_large,
                                     kind="primary", width=116, height=34)
        self.btn_lscan.pack(side="left")

        hint(bar, "最小", bg=T.BG, font=T.F_TINY).pack(side="left", padx=(12, 4))
        self.min_var = tk.StringVar(value="100 MB")
        cb = ttk.Combobox(bar, textvariable=self.min_var, width=9, state="readonly",
                          values=["50 MB", "100 MB", "500 MB", "1 GB"], font=T.F_SMALL)
        cb.pack(side="left")

        self.lcnt = hint(bar, "尚未扫描", font=T.F_SMALL)
        self.lcnt.pack(side="left", padx=12)

        self.btn_ldel = RoundButton(bar, "删除到回收站", self.del_large,
                                    kind="danger", width=124, height=34)
        self.btn_ldel.pack(side="right")
        self.btn_ldel.set_enabled(False)

        box = Card(f, padx=0, pady=0)
        box.pack(fill="both", expand=True)

        cols = ("size", "time", "folder")
        self.ltree = ttk.Treeview(box.inner, columns=cols, show="tree headings",
                                  style="CM.Treeview", selectmode="extended")
        self.ltree.column("#0", width=250, stretch=True)
        self.ltree.heading("#0", text="文件名", anchor="w")
        for c, w, t in (("size", 90, "大小"), ("time", 130, "修改时间"),
                        ("folder", 420, "所在目录")):
            self.ltree.column(c, width=w, stretch=(c == "folder"), anchor="w")
            self.ltree.heading(c, text=t, anchor="w")

        vsb = ttk.Scrollbar(box.inner, orient="vertical", command=self.ltree.yview)
        self.ltree.configure(yscrollcommand=vsb.set)
        self.ltree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        vsb.pack(side="right", fill="y", pady=8, padx=(0, 8))

        self.ltree.bind("<<TreeviewSelect>>", lambda e: self._lsel())
        self.lmap = {}

        hint(f, "删除的只是你勾选的文件，会先进回收站，随时能找回来。"
                "系统目录下的大文件不会被列出，避免误删。",
             fg=T.TEXT_MUTED, font=T.F_TINY).pack(anchor="w", pady=(8, 0))
        return f

    def scan_large(self):
        self.btn_lscan.set_enabled(False)
        self.btn_lscan.set_text("扫描中…")
        from core import mod_disk
        pcb = self.app.progress_cb
        try:
            mb = int(float(self.min_var.get().split()[0]) *
                     (1024 if "GB" in self.min_var.get() else 1))
        except Exception:
            mb = 100

        def done(files):
            self.large = files
            self.btn_lscan.set_enabled(True)
            self.btn_lscan.set_text("重新扫描")
            self._render_large(files)

        self.app.run_async(
            lambda: mod_disk.scan_large_files(min_mb=mb, progress=pcb), on_done=done)

    def _render_large(self, files):
        for iid in self.ltree.get_children(""):
            self.ltree.delete(iid)
        self.lmap.clear()
        for i, it in enumerate(files):
            iid = str(i)
            self.lmap[iid] = it
            self.ltree.insert("", "end", iid=iid,
                              text=os.path.basename(it["path"]),
                              values=(_hs(it["size"]),
                                      time.strftime("%Y-%m-%d %H:%M",
                                                    time.localtime(it["mtime"])),
                                      os.path.dirname(it["path"])))
        total = sum(x["size"] for x in files)
        self.lcnt.configure(text="%d 个文件 · 共 %s" % (len(files), _hs(total)))
        self.btn_ldel.set_enabled(False)

    def _lsel(self):
        sel = self.ltree.selection()
        if not sel:
            self.btn_ldel.set_enabled(False)
            return
        total = sum(self.lmap[i]["size"] for i in sel if i in self.lmap)
        self.btn_ldel.set_enabled(True)
        self.btn_ldel.set_text("删除 (%s)" % _hs(total))

    def del_large(self):
        sel = self.ltree.selection()
        if not sel:
            return
        total = sum(self.lmap[i]["size"] for i in sel if i in self.lmap)
        if not messagebox.askyesno(
                "删除到回收站",
                "将把 %d 个文件（共 %s）移到回收站。\n\n"
                "回收站里的文件仍占用磁盘空间，确认没问题后记得清空回收站。\n\n继续吗？"
                % (len(sel), _hs(total))):
            return

        from core import mod_disk
        ok = fail = 0
        for iid in sel:
            it = self.lmap.get(iid)
            if not it:
                continue
            if mod_disk.delete_to_recyclebin(it["path"]):
                ok += 1
                try:
                    self.ltree.delete(iid)
                except Exception:
                    pass
            else:
                fail += 1
        self.lcnt.configure(text="已删除 %d 个（失败 %d），释放约 %s"
                            % (ok, fail, _hs(total)))
        self.btn_ldel.set_enabled(False)
        self.app.set_status("已移到回收站 %d 个文件，约 %s" % (ok, _hs(total)))

    # ========================================================
    # 视图 3：空间分析
    # ========================================================
    def _build_tree(self, parent):
        f = tk.Frame(parent, bg=T.BG)

        bar = tk.Frame(f, bg=T.BG)
        bar.pack(fill="x", pady=(0, 8))
        hint(bar, "点击左侧箭头逐级展开，看清楚每个文件夹占了多少。", bg=T.BG).pack(side="left")

        box = Card(f, padx=0, pady=0)
        box.pack(fill="both", expand=True)

        cols = ("size", "pct")
        self.ttree = ttk.Treeview(box.inner, columns=cols, show="tree headings",
                                  style="CM.Treeview")
        self.ttree.column("#0", width=380, stretch=True)
        self.ttree.heading("#0", text="文件夹", anchor="w")
        self.ttree.column("size", width=100, stretch=False, anchor="e")
        self.ttree.heading("size", text="大小", anchor="e")
        self.ttree.column("pct", width=80, stretch=False, anchor="e")
        self.ttree.heading("pct", text="占本层", anchor="e")

        vsb = ttk.Scrollbar(box.inner, orient="vertical", command=self.ttree.yview)
        self.ttree.configure(yscrollcommand=vsb.set)
        self.ttree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        vsb.pack(side="right", fill="y", pady=8, padx=(0, 8))

        self.ttree.bind("<<TreeviewOpen>>", self._on_open)
        self._loaded = set()
        return f

    def _load_drives_tree(self):
        if self._loaded:
            return
        from core import mod_disk
        self.ttree.delete(*self.ttree.get_children(""))
        self._loaded.clear()
        for d in mod_disk.scan_drives():
            iid = d["letter"] + "\\"
            pct = d["pct"]
            self.ttree.insert("", "end", iid=iid, text="%s 盘" % d["letter"],
                              values=(_hs(d["used"]), "%.0f%% 已用" % pct),
                              open=False)
            self.ttree.insert(iid, "end", iid=iid + "|ph", text="正在读取…")

    def _on_open(self, e):
        iid = self.ttree.focus()
        if not iid or not os.path.isdir(iid):
            return
        if iid in self._loaded:
            return
        self._loaded.add(iid)
        # 删占位
        for c in self.ttree.get_children(iid):
            self.ttree.delete(c)

        from core import mod_disk
        kids = mod_disk.list_children(iid, max_seconds=6)
        total = sum(k[2] for k in kids if k[2] > 0) or 1
        for name, full, size, is_dir in kids[:80]:
            if not is_dir:
                continue
            pct = size / total * 100 if size > 0 else 0
            node = self.ttree.insert(iid, "end", iid=full, text=name,
                                     values=(_hs(size) if size >= 0 else "…",
                                             "%.0f%%" % pct if size > 0 else ""))
            if is_dir and size > 0:
                self.ttree.insert(node, "end", iid=full + "|ph", text="正在读取…")
        # 文件也列出来（按大小排序后取前面的）
        files = [k for k in kids if not k[3]][:20]
        if files:
            grp = self.ttree.insert(iid, "end", text="（文件）", values=("", ""))
            for name, full, size, _ in files:
                self.ttree.insert(grp, "end", iid=full, text=name,
                                  values=(_hs(size), ""))

    # ========================================================
    # 视图 4：分盘盘点（v2）
    # ========================================================
    def _build_inv(self, parent):
        f = tk.Frame(parent, bg=T.BG)

        bar = tk.Frame(f, bg=T.BG)
        bar.pack(fill="x", pady=(0, 8))

        self.btn_iscan = RoundButton(bar, "盘点所有磁盘", self.scan_inv,
                                     kind="primary", width=120, height=34)
        self.btn_iscan.pack(side="left")

        self.icnt = hint(bar, "对每个磁盘分别列出：装了哪些软件、有哪些大文件、空间被谁占了",
                         font=T.F_SMALL)
        self.icnt.pack(side="left", padx=12)

        self.btn_idel = RoundButton(bar, "删除选中文件到回收站", self.del_inv_file,
                                    kind="danger", width=168, height=34)
        self.btn_idel.pack(side="right")
        self.btn_idel.set_enabled(False)

        box = Card(f, padx=0, pady=0)
        box.pack(fill="both", expand=True)

        cols = ("detail", "size", "info")
        self.itree = ttk.Treeview(box.inner, columns=cols, show="tree headings",
                                  style="CM.Treeview")
        self.itree.column("#0", width=330, stretch=True)
        self.itree.heading("#0", text="磁盘 / 项目", anchor="w")
        self.itree.column("detail", width=330, stretch=True)
        self.itree.heading("detail", text="说明", anchor="w")
        self.itree.column("size", width=90, stretch=False, anchor="e")
        self.itree.heading("size", text="大小", anchor="e")
        self.itree.column("info", width=180, stretch=False, anchor="w")
        self.itree.heading("info", text="备注", anchor="w")

        vsb = ttk.Scrollbar(box.inner, orient="vertical", command=self.itree.yview)
        self.itree.configure(yscrollcommand=vsb.set)
        self.itree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        vsb.pack(side="right", fill="y", pady=8, padx=(0, 8))

        self.itree.tag_configure("risk", foreground=T.DANGER)
        self.itree.tag_configure("hdr", font=T.F_SMALL)
        self.itree.bind("<<TreeviewSelect>>", lambda e: self._inv_sel())

        self._inv_data = []
        self._inv_file_map = {}
        return f

    def scan_inv(self):
        self.btn_iscan.set_enabled(False)
        self.btn_iscan.set_text("盘点中…")
        from core import mod_disk
        pcb = self.app.progress_cb

        def done(data):
            self._inv_data = data or []
            self.btn_iscan.set_enabled(True)
            self.btn_iscan.set_text("重新盘点")
            self._render_inv()

        self.app.run_async(lambda: mod_disk.drive_inventory(progress=pcb),
                           on_done=done)

    def _render_inv(self):
        self.itree.delete(*self.itree.get_children(""))
        self._inv_file_map.clear()
        for d in self._inv_data:
            # 盘符节点
            drv = "inv_drive_" + d["letter"]
            self.itree.insert("", "end", iid=drv, open=True,
                              text="%s 盘（总 %s / 剩余 %s / 已用 %.0f%%）"
                                   % (d["letter"], _hs(d["total"]),
                                      _hs(d["free"]), d["pct"]),
                              values=("", "", ""), tags=("hdr",))

            # --- 文件构成 ---
            types = d.get("types") or []
            if types:
                scanned = d.get("scanned_size") or sum(t["size"] for t in types) or 1
                g_ty = self.itree.insert(
                    drv, "end", open=True,
                    text="  文件构成（共 %d 个文件，%s）"
                         % (d.get("file_count", 0), _hs(scanned)),
                    values=("", "", ""))
                for t in types:
                    pct = t["size"] / scanned * 100
                    self.itree.insert(g_ty, "end", open=False,
                                      text="  · %s" % t["label"],
                                      values=("%.1f%%" % pct, _hs(t["size"]),
                                              "%d 个文件" % t["count"]))
            else:
                self.itree.insert(drv, "end", open=False,
                                  text="  文件构成（未扫描）",
                                  values=("", "", ""))

            # --- 软件 ---
            g_sw = self.itree.insert(drv, "end", open=True,
                                     text="  安装在这个盘的软件（%d 个）" % len(d["software"]),
                                     values=("", "", ""))
            if not d["software"]:
                self.itree.insert(g_sw, "end", open=False,
                                  text="  （没有软件安装在此盘）", values=("", "", ""))
            for s in d["software"][:40]:
                risk = ""
                tag = ()
                if s["level"] in ("high", "mid"):
                    risk = "风险 %d 分" % s["score"]
                    tag = ("risk",)
                self.itree.insert(g_sw, "end", open=False,
                                  text="  · " + s["name"],
                                  values=(s["publisher"] or "",
                                          _hs(s["size"]) if s.get("size") else "-",
                                          risk), tags=tag)

            # --- 大文件 ---
            g_bf = self.itree.insert(
                drv, "end", open=False,
                text="  大文件（共 %d 个 ≥100MB，列出前 %d 个）"
                     % (d.get("big_count", len(d["big_files"])), len(d["big_files"])),
                values=("", "", ""))
            for i, bf in enumerate(d["big_files"]):
                iid = "invfile|%s" % bf["path"]
                self._inv_file_map[iid] = bf
                self.itree.insert(g_bf, "end", iid=iid, open=False,
                                  text="  □ " + os.path.basename(bf["path"]),
                                  values=(os.path.dirname(bf["path"]),
                                          _hs(bf["size"]), "勾选后可删除"))
                self.itree.selection_remove(iid)

            # --- 一级目录占用 ---
            g_dir = self.itree.insert(drv, "end", open=False,
                                      text="  空间大头（一级目录）",
                                      values=("", "", ""))
            for name, full, size, is_dir in d["top_dirs"]:
                if size <= 0:
                    continue
                self.itree.insert(g_dir, "end", open=False,
                                  text="  · " + name + ("/" if is_dir else ""),
                                  values=(full, _hs(size) if size > 0 else "…", ""))

        n_files = len(self._inv_file_map)
        self.icnt.configure(text="盘点完成：%d 个磁盘，%d 个可管理的大文件"
                            % (len(self._inv_data), n_files))

    def _inv_sel(self):
        sel = [i for i in self.itree.selection() if i.startswith("invfile|")]
        if not sel:
            self.btn_idel.set_enabled(False)
            return
        total = sum(self._inv_file_map[i]["size"] for i in sel if i in self._inv_file_map)
        self.btn_idel.set_enabled(True)
        self.btn_idel.set_text("删除选中到回收站 (%s)" % _hs(total))

    def del_inv_file(self):
        sel = [i for i in self.itree.selection() if i.startswith("invfile|")]
        if not sel:
            return
        total = sum(self._inv_file_map[i]["size"] for i in sel if i in self._inv_file_map)
        if not messagebox.askyesno(
                "删除到回收站",
                "将把 %d 个文件（共 %s）移到回收站。\n\n继续吗？" % (len(sel), _hs(total))):
            return
        from core import mod_disk
        ok = 0
        for iid in sel:
            it = self._inv_file_map.get(iid)
            if it and mod_disk.delete_to_recyclebin(it["path"]):
                ok += 1
                try:
                    self.itree.delete(iid)
                except Exception:
                    pass
        self.app.set_status("已移到回收站 %d 个文件，约 %s" % (ok, _hs(total)))
        self.btn_idel.set_enabled(False)
