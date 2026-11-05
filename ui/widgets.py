# -*- coding: utf-8 -*-
"""自定义控件：圆角按钮 / 卡片 / 勾选表格 / 磁盘条 / 滚动容器"""
import tkinter as tk
from tkinter import ttk, font as tkfont

from ui import theme as T


# ============================================================
# 圆角按钮
# ============================================================
class RoundButton(tk.Canvas):
    """
    kind: primary / ghost / danger / soft / success
    """
    STYLES = {
        "primary": dict(bg=T.PRIMARY, fg="#FFFFFF", hover=T.PRIMARY_DK, border=""),
        "ghost":   dict(bg=T.CARD, fg=T.TEXT, hover="#F2F5FA", border=T.BORDER),
        "soft":    dict(bg=T.PRIMARY_LT, fg=T.PRIMARY, hover="#DDE8FF", border=""),
        "danger":  dict(bg=T.DANGER, fg="#FFFFFF", hover="#C93A3F", border=""),
        "success": dict(bg=T.OK, fg="#FFFFFF", hover="#0E8A44", border=""),
        "warn":    dict(bg=T.WARN_LT, fg="#9A6200", hover="#FDEBC8", border=""),
    }

    def __init__(self, master, text="", command=None, kind="primary",
                 width=100, height=34, radius=8, font=None, icon=""):
        super().__init__(master, width=width, height=height,
                         bg=master["bg"] if "bg" in master.keys() else T.CARD,
                         highlightthickness=0, bd=0, cursor="hand2")
        self._text = (icon + " " + text).strip() if icon else text
        self._command = command
        self._kind = kind
        # 注意：不能用 self._w / self._h，那是 tkinter 内部属性
        self._cw, self._ch, self._r = width, height, radius
        self._font = font or T.F_BODY
        self._enabled = True
        self._draw()
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", lambda e: self._hover(True))
        self.bind("<Leave>", lambda e: self._hover(False))

    # ---- 内部 ----
    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
               x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
               x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.create_polygon(pts, smooth=True, **kw)

    def _draw(self, hover=False):
        self.delete("all")
        s = self.STYLES.get(self._kind, self.STYLES["primary"])
        bg = s["hover"] if (hover and self._enabled) else s["bg"]
        if not self._enabled:
            bg = "#EDEFF2"
        fg = s["fg"] if self._enabled else T.TEXT_MUTED
        bd = s["border"]
        self._round_rect(1, 1, self._cw - 1, self._ch - 1, self._r,
                         fill=bg, outline=bd or bg, width=1)
        self.create_text(self._cw / 2, self._ch / 2, text=self._text,
                         fill=fg, font=self._font)

    def _hover(self, on):
        if not self._enabled:
            return
        self._draw(hover=on)

    def _on_click(self, e):
        if self._enabled and self._command:
            self._command()

    # ---- 外部 ----
    def set_enabled(self, v):
        self._enabled = bool(v)
        self._draw()
        self.configure(cursor="hand2" if v else "arrow")

    def set_text(self, text):
        self._text = text
        self._draw()

    def set_kind(self, kind):
        self._kind = kind
        self._draw()


# ============================================================
# 卡片
# ============================================================
class Card(tk.Frame):
    def __init__(self, master, padx=16, pady=14, **kw):
        super().__init__(master, bg=T.CARD, highlightbackground=T.BORDER,
                         highlightthickness=1, bd=0, **kw)
        self.inner = tk.Frame(self, bg=T.CARD)
        self.inner.pack(fill="both", expand=True, padx=padx, pady=pady)


def label(master, text, font=None, fg=None, bg=None, **kw):
    return tk.Label(master, text=text, font=font or T.F_BODY,
                    fg=fg or T.TEXT, bg=bg or T.CARD, **kw)


def hint(master, text, fg=None, bg=None, font=None, **kw):
    return tk.Label(master, text=text, font=font or T.F_SMALL,
                    fg=fg or T.TEXT_SUB, bg=bg or T.CARD, justify="left", **kw)


class Badge(tk.Label):
    COLORS = {
        "high": (T.DANGER_LT, T.DANGER),
        "mid": (T.WARN_LT, "#9A6200"),
        "low": (T.BORDER_SOFT, T.TEXT_SUB),
        "trusted": (T.OK_LT, T.OK),
        "info": (T.PRIMARY_LT, T.PRIMARY),
    }

    def __init__(self, master, text, level="info", bg=None, **kw):
        cbg, cfg = self.COLORS.get(level, self.COLORS["info"])
        super().__init__(master, text=" %s " % text, font=T.F_TINY,
                         bg=bg or cbg, fg=cfg, padx=4, pady=1, **kw)


# ============================================================
# 勾选表格
# ============================================================
ON, OFF = "☑", "☐"


class CheckTree(ttk.Frame):
    """
    带 checkbox 的树/表。点击第一列切换勾选。
    """
    def __init__(self, master, columns, widths=None, height=12,
                 show_tree=False, on_toggle=None):
        super().__init__(master)   # ttk.Frame 不支持 bg 参数
        self._on_toggle = on_toggle
        self._checked = set()
        self._texts = {}
        self._disabled = set()

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("CM.Treeview",
                        background=T.CARD, fieldbackground=T.CARD,
                        foreground=T.TEXT, rowheight=30, borderwidth=0,
                        font=T.F_BODY)
        style.configure("CM.Treeview.Heading",
                        background="#F7F8FA", foreground=T.TEXT_SUB,
                        font=T.F_SMALL, borderwidth=0, relief="flat")
        style.map("CM.Treeview",
                  background=[("selected", T.PRIMARY_LT)],
                  foreground=[("selected", T.TEXT)])
        style.layout("CM.Treeview", [
            ("CM.Treeview.treearea", {"sticky": "nswe"})
        ])
        style.map("CM.Treeview.Heading", background=[("active", "#F0F2F5")])

        col_ids = ["#0"] + ["c%d" % i for i in range(len(columns))]
        show = ("tree", "headings") if show_tree else ("headings",)
        self.tree = ttk.Treeview(self, columns=col_ids[1:], show=show,
                                 style="CM.Treeview", height=height,
                                 selectmode="extended")
        # 首列宽度
        self.tree.column("#0", width=(widths[0] if widths else 320), stretch=True)
        self.tree.heading("#0", text=columns[0] if columns else "", anchor="w")
        for i, (col, w) in enumerate(zip(columns, (widths or [])[1:] if widths else [])):
            cid = "c%d" % i
            self.tree.column(cid, width=w, stretch=False, anchor="w")
            self.tree.heading(cid, text=col, anchor="w")

        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        self.vsb.pack(side="right", fill="y")

        self.tree.bind("<Button-1>", self._on_click, add="+")
        self.tree.bind("<space>", self._on_space)
        # 斑马纹
        self.tree.tag_configure("odd", background="#FBFCFD")
        self.tree.tag_configure("even", background=T.CARD)

    # ---- 数据 ----
    def clear(self):
        for iid in self.tree.get_children(""):
            self.tree.delete(iid)
        self._checked.clear()
        self._texts.clear()
        self._disabled.clear()

    def add(self, iid, text, values, checked=False, level=None, disabled=False):
        self._texts[iid] = text
        if disabled:
            self._disabled.add(iid)
        mark = OFF if (disabled or not checked) else ON
        self.tree.insert("", "end", iid=iid,
                         text="%s  %s" % (mark, text),
                         values=values)
        if checked and not disabled:
            self._checked.add(iid)
        self._restripe()

    def _restripe(self):
        for i, iid in enumerate(self.tree.get_children("")):
            tags = list(self.tree.item(iid, "tags"))
            tags = [t for t in tags if t not in ("odd", "even")]
            tags.append("odd" if i % 2 else "even")
            self.tree.item(iid, tags=tags)

    def toggle(self, iid):
        if iid in self._disabled:
            return
        if iid in self._checked:
            self._checked.discard(iid)
            mark = OFF
        else:
            self._checked.add(iid)
            mark = ON
        self.tree.item(iid, text="%s  %s" % (mark, self._texts.get(iid, "")))
        if self._on_toggle:
            self._on_toggle(iid, iid in self._checked)

    def set_checked(self, iid, val):
        if iid in self._disabled:
            return
        if val:
            self._checked.add(iid)
        else:
            self._checked.discard(iid)
        self.tree.item(iid, text="%s  %s" % (ON if val else OFF,
                                             self._texts.get(iid, "")))

    def set_all(self, val, only_visible=True):
        for iid in self.tree.get_children(""):
            if iid in self._disabled:
                continue
            self.set_checked(iid, val)

    def get_checked(self):
        return [i for i in self.tree.get_children("") if i in self._checked]

    def count(self):
        return len(self.tree.get_children(""))

    def checked_count(self):
        return len([i for i in self.tree.get_children("") if i in self._checked])

    # ---- 事件 ----
    def _on_click(self, ev):
        region = self.tree.identify_region(ev.x, ev.y)
        col = self.tree.identify_column(ev.x)
        row = self.tree.identify_row(ev.y)
        if region == "cell" and col == "#0" and row:
            self.toggle(row)
            return "break"

    def _on_space(self, ev):
        for iid in self.tree.selection():
            self.toggle(iid)
        return "break"

    # ---- 过滤 ----
    def filter(self, keyword):
        kw = (keyword or "").strip().lower()
        for iid in self.tree.get_children(""):
            txt = (self._texts.get(iid, "") + " " +
                   " ".join(str(v) for v in self.tree.item(iid, "values"))).lower()
            if not kw or kw in txt:
                self.tree.reattach(iid, "", "end")
                self.tree.item(iid, tags=[t for t in self.tree.item(iid, "tags")])
            else:
                self.tree.detach(iid)


# ============================================================
# 磁盘占用条
# ============================================================
class DiskBar(tk.Frame):
    def __init__(self, master, letter, total, used, free, pct, width=260):
        super().__init__(master, bg=T.CARD)
        self.letter = letter
        top = tk.Frame(self, bg=T.CARD)
        top.pack(fill="x")
        label(top, "%s 盘" % letter, font=T.F_H2).pack(side="left")
        label(top, "%s / %s" % (_hs(used), _hs(total)),
              font=T.F_SMALL, fg=T.TEXT_SUB).pack(side="right")

        c = tk.Canvas(self, width=width, height=8, bg=T.CARD,
                      highlightthickness=0)
        c.pack(fill="x", pady=(6, 2))
        c.create_rectangle(0, 0, width, 8, fill="#EDEFF2", outline="")
        w = max(2, int(width * pct / 100))
        color = T.DANGER if pct > 90 else (T.WARN if pct > 75 else T.PRIMARY)
        c.create_rectangle(0, 0, w, 8, fill=color, outline="")

        label(self, "剩余 %s （已用 %.0f%%）" % (_hs(free), pct),
              font=T.F_TINY, fg=T.TEXT_SUB).pack(anchor="w")


def _hs(n):
    n = float(n or 0)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return ("%.0f %s" % (n, u)) if u == "B" else ("%.1f %s" % (n, u))
        n /= 1024.0
    return "%.1f PB" % n


# ============================================================
# 滚动容器
# ============================================================
class ScrollFrame(tk.Frame):
    def __init__(self, master, bg=None):
        super().__init__(master, bg=bg or T.BG)
        self.canvas = tk.Canvas(self, bg=bg or T.BG, highlightthickness=0, bd=0)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vsb.pack(side="right", fill="y")

        self.body = tk.Frame(self.canvas, bg=bg or T.BG)
        self._win = self.canvas.create_window((0, 0), window=self.body, anchor="nw")

        self.body.bind("<Configure>", self._on_conf)
        self.canvas.bind("<Configure>", self._on_canvas)
        self.canvas.bind_all("<MouseWheel>", self._on_wheel, add="+")

    def _on_conf(self, e):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas(self, e):
        self.canvas.itemconfig(self._win, width=e.width)

    def _on_wheel(self, e):
        try:
            if self.winfo_containing(e.x_root, e.y_root) is None:
                return
            w = self.winfo_containing(e.x_root, e.y_root)
            # 只在自己可见时滚动
            if not self.winfo_ismapped():
                return
            self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        except Exception:
            pass


# ============================================================
# 分区标题
# ============================================================
class SectionTitle(tk.Frame):
    def __init__(self, master, title, desc="", bg=None):
        super().__init__(master, bg=bg or T.BG)
        label(self, title, font=T.F_H1, bg=bg or T.BG).pack(anchor="w")
        if desc:
            label(self, desc, font=T.F_SMALL, fg=T.TEXT_SUB,
                  bg=bg or T.BG).pack(anchor="w", pady=(3, 0))
