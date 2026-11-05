# -*- coding: utf-8 -*-
"""概览页：一键体检 + 结果汇总"""
import tkinter as tk
from tkinter import messagebox

from ui import theme as T
from ui.widgets import (Card, RoundButton, label, hint, ScrollFrame,
                        SectionTitle, Badge, _hs)


class Page(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=T.BG)
        self.app = app
        self.sf = ScrollFrame(self)
        self.sf.pack(fill="both", expand=True)
        self.body = tk.Frame(self.sf.body, bg=T.BG)
        self.body.pack(fill="both", expand=True, padx=24, pady=18)

        self._build()

    # ========================================================
    def _build(self):
        head = tk.Frame(self.body, bg=T.BG)
        head.pack(fill="x")
        label(head, "电脑体检", font=T.F_TITLE, bg=T.BG).pack(anchor="w")
        hint(head, "一次扫描，找出占着电脑的 360 残留、流氓软件和可清理的垃圾文件",
             bg=T.BG).pack(anchor="w", pady=(4, 0))

        # ---- 体检主卡 ----
        main = Card(self.body, padx=22, pady=18)
        main.pack(fill="x", pady=(16, 0))
        row = tk.Frame(main.inner, bg=T.CARD)
        row.pack(fill="x")

        lf = tk.Frame(row, bg=T.CARD)
        lf.pack(side="left", fill="x", expand=True)
        self.title_lbl = label(lf, "点击开始体检", font=T.F_H1)
        self.title_lbl.pack(anchor="w")
        self.desc_lbl = hint(lf, "会依次检查：360 残留 · 浏览器劫持 · 流氓软件 · 磁盘垃圾\n"
                                "全程只读，不会改动任何东西", font=T.F_SMALL)
        self.desc_lbl.pack(anchor="w", pady=(6, 0))

        self.btn_scan = RoundButton(row, "开始体检", self.do_scan,
                                    kind="primary", width=132, height=40,
                                    font=(T.FONT_FAMILY, 11, "bold"))
        self.btn_scan.pack(side="right", padx=(16, 0))

        # ---- 三张结果卡 ----
        grid = tk.Frame(self.body, bg=T.BG)
        grid.pack(fill="x", pady=(14, 0))
        for i in range(4):
            grid.columnconfigure(i, weight=1, uniform="c")

        self.cards = {}
        specs = [
            ("res360", "360 残留", "项", T.DANGER, "clean360"),
            ("ads", "广告来源", "项", "#A06400", "ads"),
            ("rogue", "可疑软件", "个", T.WARN, "software"),
            ("junk", "可清理空间", "", T.PRIMARY, "disk"),
        ]
        for i, (key, title, unit, color, page) in enumerate(specs):
            c = Card(grid, padx=18, pady=14)
            c.grid(row=0, column=i, sticky="nsew",
                   padx=(0 if i == 0 else 10, 0))
            label(c.inner, title, font=T.F_SMALL, fg=T.TEXT_SUB).pack(anchor="w")
            num_row = tk.Frame(c.inner, bg=T.CARD)
            num_row.pack(anchor="w", pady=(6, 0))
            num = tk.Label(num_row, text="—", font=T.F_BIG_NUM, fg=color, bg=T.CARD)
            num.pack(side="left")
            ul = tk.Label(num_row, text=unit, font=T.F_SMALL, fg=T.TEXT_SUB, bg=T.CARD)
            ul.pack(side="left", padx=(4, 0), pady=(8, 0))
            sub = hint(c.inner, "尚未扫描", font=T.F_TINY, fg=T.TEXT_MUTED)
            sub.pack(anchor="w", pady=(2, 0))
            go = RoundButton(c.inner, "去处理 →",
                             lambda p=page: self.app.show_page(p),
                             kind="soft", width=92, height=26, font=T.F_TINY)
            go.pack(anchor="w", pady=(10, 0))
            self.cards[key] = {"num": num, "sub": sub, "unit": ul}

        # ---- 磁盘概况 ----
        disk_card = Card(self.body, padx=20, pady=16)
        disk_card.pack(fill="x", pady=(14, 0))
        top = tk.Frame(disk_card.inner, bg=T.CARD)
        top.pack(fill="x")
        label(top, "磁盘空间", font=T.F_H2).pack(side="left")
        RoundButton(top, "查看详情", lambda: self.app.show_page("disk"),
                    kind="ghost", width=84, height=26, font=T.F_TINY).pack(side="right")

        self.disk_box = tk.Frame(disk_card.inner, bg=T.CARD)
        self.disk_box.pack(fill="x", pady=(12, 0))

        # ---- 最近备份 ----
        self.bk_card = Card(self.body, padx=20, pady=16)
        self.bk_card.pack(fill="x", pady=(14, 18))
        t2 = tk.Frame(self.bk_card.inner, bg=T.CARD)
        t2.pack(fill="x")
        label(t2, "最近操作记录", font=T.F_H2).pack(side="left")
        RoundButton(t2, "恢复中心", lambda: self.app.show_page("backup"),
                    kind="ghost", width=84, height=26, font=T.F_TINY).pack(side="right")
        self.bk_box = tk.Frame(self.bk_card.inner, bg=T.CARD)
        self.bk_box.pack(fill="x", pady=(10, 0))

    # ========================================================
    def on_show(self):
        self._refresh_disks()
        self._refresh_backups()

    def _refresh_disks(self):
        for w in self.disk_box.winfo_children():
            w.destroy()
        from core import mod_disk
        drives = mod_disk.scan_drives()
        if not drives:
            hint(self.disk_box, "未检测到磁盘").pack(anchor="w")
            return
        for d in drives:
            row = tk.Frame(self.disk_box, bg=T.CARD)
            row.pack(fill="x", pady=4)

            label(row, "%s 盘" % d["letter"], font=T.F_H2, width=6,
                  anchor="w").pack(side="left")

            c = tk.Canvas(row, height=8, bg=T.CARD, highlightthickness=0)
            c.pack(side="left", fill="x", expand=True, padx=12)
            color = T.DANGER if d["pct"] > 90 else (T.WARN if d["pct"] > 75 else T.PRIMARY)

            def _draw(e, c=c, d=d, color=color):
                w = e.width
                c.delete("all")
                c.create_rectangle(0, 0, w, 8, fill="#EDEFF2", outline="")
                c.create_rectangle(0, 0, max(2, int(w * d["pct"] / 100)), 8,
                                   fill=color, outline="")
            c.bind("<Configure>", _draw)

            hint(row, "剩余 %s / 共 %s" % (_hs(d["free"]), _hs(d["total"])),
                 fg=T.TEXT_SUB).pack(side="right")

    def _refresh_backups(self):
        for w in self.bk_box.winfo_children():
            w.destroy()
        from core import utils
        batches = utils.list_batches()[:3]
        if not batches:
            hint(self.bk_box, "还没有清理记录。每次清理都会自动生成一个可还原的备份。",
                 fg=T.TEXT_MUTED).pack(anchor="w")
            return
        for b in batches:
            row = tk.Frame(self.bk_box, bg=T.CARD)
            row.pack(fill="x", pady=3)
            dot = "●" if not b.get("restored") else "○"
            col = T.PRIMARY if not b.get("restored") else T.TEXT_MUTED
            tk.Label(row, text=dot, font=T.F_TINY, fg=col, bg=T.CARD).pack(side="left")
            label(row, b.get("title") or "清理操作", font=T.F_SMALL).pack(side="left", padx=8)
            hint(row, b.get("created_str", "") + "   " + _hs(b.get("_size", 0)),
                 fg=T.TEXT_MUTED).pack(side="right")

    # ========================================================
    def do_scan(self):
        self.btn_scan.set_enabled(False)
        self.btn_scan.set_text("扫描中…")
        self.title_lbl.configure(text="正在体检…")
        self.desc_lbl.configure(text="第一次扫描需要一两分钟，请不要关闭窗口")

        from core import mod_360, mod_edge, mod_software, mod_disk, mod_ads
        pcb = self.app.progress_cb

        def task():
            res = {}

            pcb("检查 360 残留…", 5)
            try:
                r360 = mod_360.scan()
                res["res360"] = r360
            except Exception as e:
                res["res360"] = []
                res["err360"] = str(e)

            pcb("检查浏览器劫持…", 25)
            try:
                rb = mod_edge.scan()
                res["browser"] = rb
            except Exception as e:
                res["browser"] = []

            pcb("查广告来源…", 45)
            try:
                res["ads"] = mod_ads.scan()
            except Exception as e:
                res["ads"] = []

            pcb("识别流氓软件…", 65)
            try:
                softs = mod_software.list_installed()
                res["software"] = softs
            except Exception as e:
                res["software"] = []

            pcb("统计磁盘垃圾…", 85)
            try:
                junk = mod_disk.scan_junk()
                res["junk"] = junk
            except Exception as e:
                res["junk"] = []

            pcb("完成", 100)
            return res

        self.app.run_async(task, on_done=self._on_scan_done,
                           on_error=self._on_scan_err)

    def _on_scan_err(self, e):
        self.btn_scan.set_enabled(True)
        self.btn_scan.set_text("重新体检")
        self.title_lbl.configure(text="体检失败")
        self.desc_lbl.configure(text=str(e))

    def _on_scan_done(self, res):
        st = self.app.state
        st["scan360"] = res.get("res360", [])
        st["scanbrowser"] = res.get("browser", [])
        st["ads"] = res.get("ads", [])
        st["software"] = res.get("software", [])
        st["junk"] = res.get("junk", [])

        n360 = len(st["scan360"])
        nbr = len(st["scanbrowser"])
        nads = len(st["ads"])
        ads_def = len([a for a in st["ads"] if a.get("default_checked")])
        rogue = [s for s in st["software"] if s["level"] in ("high", "mid")]
        junk_bytes = sum(j["size"] for j in st["junk"])
        junk_sel = sum(j["size"] for j in st["junk"] if j.get("selected"))

        # 更新卡片
        c = self.cards["res360"]
        c["num"].configure(text=str(n360 + nbr))
        c["sub"].configure(text=("360 项 %d · 浏览器劫持 %d" % (n360, nbr)) if (n360 or nbr)
                           else "未发现 360 残留")

        c = self.cards["ads"]
        c["num"].configure(text=str(nads))
        c["sub"].configure(text=("已预选 %d 项可清" % ads_def) if nads
                           else "没有发现弹窗广告源")

        c = self.cards["rogue"]
        high = [s for s in st["software"] if s["level"] == "high"]
        c["num"].configure(text=str(len(high)))
        c["sub"].configure(text=("共 %d 个软件，%d 个需注意" % (len(st["software"]), len(rogue)))
                           if st["software"] else "未发现可疑软件")

        c = self.cards["junk"]
        c["num"].configure(text=_hs(junk_bytes).split(" ")[0])
        c["unit"].configure(text=_hs(junk_bytes).split(" ")[1] if " " in _hs(junk_bytes) else "")
        c["sub"].configure(text="默认勾选 %s 可释放" % _hs(junk_sel))

        # 总体结论
        total_issues = n360 + nbr + len(high)
        if total_issues == 0 and nads == 0 and junk_bytes < 500 * 1024 * 1024:
            self.title_lbl.configure(text="电脑很干净 ✓")
            self.desc_lbl.configure(text="没有发现 360 残留、广告来源和可疑软件，磁盘也很充裕。")
        else:
            parts = []
            if n360:
                parts.append("%d 项 360 残留" % n360)
            if nbr:
                parts.append("%d 项浏览器劫持" % nbr)
            if nads:
                parts.append("%d 项广告来源" % nads)
            if high:
                parts.append("%d 个高风险软件" % len(high))
            if junk_bytes > 100 * 1024 * 1024:
                parts.append("%s 可清理垃圾" % _hs(junk_bytes))
            self.title_lbl.configure(text="发现 " + "、".join(parts))
            self.desc_lbl.configure(
                text="建议顺序：先清 360 → 修浏览器 → 查杀广告 → 最后清磁盘。每一步都能还原。")

        self.btn_scan.set_enabled(True)
        self.btn_scan.set_text("重新体检")
        self.app.set_status(
            "体检完成 · 360 相关 %d 项 · 广告源 %d 项 · 可疑软件 %d 个 · 可清理 %s"
            % (n360 + nbr, nads, len(high), _hs(junk_bytes)))
