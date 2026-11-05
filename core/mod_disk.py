# -*- coding: utf-8 -*-
"""
磁盘清理与分析

三块能力：
  1. 垃圾扫描：按 JUNK_LOCATIONS 规则算出每类可清理内容的体积
  2. 大文件扫描：找出占空间的大文件，用户自己决定
  3. 目录占用分析：一级目录树，可逐级下钻
"""
import os
import re
import time
import ctypes
import shutil
import threading

from core import utils
from core.rules import JUNK_LOCATIONS, LARGE_FILE_MB, HUGE_FILE_MB
from core.utils import human_size


# ============================================================
# 磁盘概况
# ============================================================
def scan_drives():
    out = []
    for letter, total, used, free in utils.get_drives():
        pct = (used / total * 100) if total else 0
        out.append({
            "letter": letter,
            "total": total,
            "used": used,
            "free": free,
            "pct": pct,
        })
    return out


# ============================================================
# 回收站
# ============================================================
def recyclebin_size():
    total = 0
    for letter, _, _, _ in utils.get_drives():
        p = os.path.join(letter + "\\", "$Recycle.Bin")
        if os.path.isdir(p):
            total += utils.dir_size(p, max_seconds=3)
    return total


def empty_recyclebin():
    try:
        SHERB_NOCONFIRMATION = 0x00000001
        SHERB_NOPROGRESSUI = 0x00000002
        SHERB_NOSOUND = 0x00000004
        r = ctypes.windll.shell32.SHEmptyRecycleBinW(
            None, None, SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND)
        return r == 0
    except Exception as e:
        utils.log("清空回收站失败: %s" % e, "ERR")
        return False


def delete_to_recyclebin(path):
    """删除到回收站（用户可恢复）"""
    try:
        class SHFILEOPSTRUCTW(ctypes.Structure):
            _fields_ = [
                ("hwnd", ctypes.c_void_p),
                ("wFunc", ctypes.c_uint),
                # 注意：这里是 BOOL(4字节)，写成 c_bool 会让后面字段错位
                ("pFrom", ctypes.c_wchar_p),
                ("pTo", ctypes.c_wchar_p),
                ("fFlags", ctypes.c_ushort),
                ("fAnyOperationsAborted", ctypes.c_int),
                ("hNameMappings", ctypes.c_void_p),
                ("lpszProgressTitle", ctypes.c_wchar_p),
            ]
        FO_DELETE = 3
        FOF_ALLOWUNDO = 0x0040
        FOF_NOCONFIRMATION = 0x0010
        FOF_SILENT = 0x0004
        FOF_NOERRORUI = 0x0400

        # pFrom 必须是「双 null 结尾」的字符串列表
        buf = ctypes.create_unicode_buffer(len(path) + 2)
        buf.value = path

        op = SHFILEOPSTRUCTW()
        op.hwnd = None
        op.wFunc = FO_DELETE
        op.pFrom = ctypes.cast(buf, ctypes.c_wchar_p)
        op.pTo = None
        op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
        op.fAnyOperationsAborted = 0

        r = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        if r == 0 and not op.fAnyOperationsAborted:
            return True
        # 容错：文件确实已经不在了，就当成功（部分情况下 API 返回码不可靠）
        return not os.path.exists(path)
    except Exception as e:
        utils.log("删到回收站失败 %s: %s" % (path, e), "ERR")
        return False


# ============================================================
# 垃圾扫描
# ============================================================
def _expand(p):
    """展开环境变量，并修正写死的 C: 盘符"""
    p = os.path.expandvars(p)
    sd = os.environ.get("SystemDrive", "C:")
    if sd.upper() != "C:" and p.upper().startswith("C:\\"):
        p = sd + p[2:]
    return p


def _walk_size(paths, max_seconds=6):
    """统计一组路径的总大小和文件数"""
    total = 0
    count = 0
    t0 = time.time()
    for root_path in paths:
        if not os.path.exists(root_path):
            continue
        if os.path.isfile(root_path):
            try:
                total += os.path.getsize(root_path)
                count += 1
            except Exception:
                pass
            continue
        for root, dirs, files in os.walk(root_path, onerror=lambda e: None):
            for f in files:
                try:
                    fp = os.path.join(root, f)
                    if os.path.islink(fp):
                        continue
                    total += os.path.getsize(fp)
                    count += 1
                except Exception:
                    pass
            if time.time() - t0 > max_seconds:
                return total, count
    return total, count


def scan_junk(progress=None, cancel=None):
    """
    返回垃圾项列表：
    {'key','name','desc','paths','size','files','selected','level'}
    """
    items = []
    total_n = len(JUNK_LOCATIONS)

    for i, (key, name, paths, desc, default_on, level) in enumerate(JUNK_LOCATIONS):
        if cancel and cancel():
            break
        if progress:
            progress("正在统计：%s" % name, int(i * 100 / total_n))

        real_paths = []
        size = 0
        files = 0

        if paths == ["__RECYCLE__"]:
            size = recyclebin_size()
            files = -1
            real_paths = ["__RECYCLE__"]
        elif paths == ["__HIBERFIL__"]:
            p = os.path.join(os.environ.get("SystemDrive", "C:") + "\\", "hiberfil.sys")
            if os.path.exists(p):
                try:
                    size = os.path.getsize(p)
                except Exception:
                    pass
            real_paths = ["__HIBERFIL__"]
        elif paths == ["__PAGEFILE__"]:
            p = os.path.join(os.environ.get("SystemDrive", "C:") + "\\", "pagefile.sys")
            if os.path.exists(p):
                try:
                    size = os.path.getsize(p)
                except Exception:
                    pass
            real_paths = ["__PAGEFILE__"]
        elif key == "firefox_cache":
            # 展开 profile 子目录
            base = _expand(paths[0])
            found = []
            if os.path.isdir(base):
                for prof in os.listdir(base):
                    for sub in ("cache2", "startupCache", "thumbnails"):
                        c = os.path.join(base, prof, sub)
                        if os.path.isdir(c):
                            found.append(c)
            real_paths = found
            size, files = _walk_size(found, max_seconds=5)
        elif key == "downloads_old":
            # 只统计 90 天前的文件
            base = _expand(paths[0])
            old_files = []
            cutoff = time.time() - 90 * 86400
            if os.path.isdir(base):
                for root, dirs, fs in os.walk(base, onerror=lambda e: None):
                    for f in fs:
                        fp = os.path.join(root, f)
                        try:
                            if os.path.getmtime(fp) < cutoff:
                                old_files.append(fp)
                        except Exception:
                            pass
            real_paths = old_files
            for fp in old_files:
                try:
                    size += os.path.getsize(fp)
                    files += 1
                except Exception:
                    pass
        else:
            for p in paths:
                ep = _expand(p)
                if os.path.exists(ep):
                    real_paths.append(ep)
            size, files = _walk_size(real_paths, max_seconds=6)

        # 空目录不展示，减少噪音
        if size <= 0:
            continue

        items.append({
            "key": key,
            "name": name,
            "desc": desc,
            "paths": real_paths,
            "size": size,
            "files": files,
            "selected": bool(default_on) and size > 0,
            "level": level,
        })

    if progress:
        progress("统计完成", 100)
    items.sort(key=lambda x: -x["size"])
    return items


def clean_junk(items, batch, progress=None):
    """
    清理垃圾。
    safe 类直接删除；careful/danger 类移到隔离区或删到回收站。
    返回 (释放字节数, 成功数, 失败数, 消息)
    """
    freed = 0
    ok = fail = 0
    msgs = []
    total = len(items) or 1

    for i, it in enumerate(items):
        if progress:
            progress("清理：%s" % it["name"], int(i * 100 / total))
        try:
            f, o, fl, m = _clean_one(it, batch)
            freed += f
            ok += o
            fail += fl
            msgs.append("✓ %s — 释放 %s" % (it["name"], human_size(f)))
        except Exception as e:
            fail += 1
            msgs.append("✗ %s — %s" % (it["name"], e))
            utils.log("清理垃圾失败 %s: %s" % (it["name"], e), "ERR")

    if progress:
        progress("完成", 100)
    return freed, ok, fail, msgs


def _clean_one(it, batch):
    key = it["key"]
    paths = it["paths"]
    level = it["level"]
    freed = 0
    ok = fail = 0

    if paths == ["__RECYCLE__"]:
        if empty_recyclebin():
            batch.note("清空回收站", "释放 %s" % human_size(it["size"]))
            return it["size"], 1, 0, ""
        return 0, 0, 1, ""

    if paths == ["__HIBERFIL__"]:
        code, out = utils.run_cmd(["powercfg", "/hibernate", "off"], timeout=30)
        if code == 0:
            batch.note("关闭休眠并删除 hiberfil.sys")
            return it["size"], 1, 0, ""
        return 0, 0, 1, out

    if paths == ["__PAGEFILE__"]:
        return 0, 0, 1, "虚拟内存文件不建议删除"

    for p in paths:
        if not p or not os.path.exists(p):
            continue
        if utils.is_protected(p):
            continue
        if level == "careful" or level == "danger":
            # 移到隔离区
            o, _ = batch.quarantine(p, it["name"])
            if o:
                freed += it["size"]
                ok += 1
            else:
                fail += 1
        else:
            # safe：直接删
            try:
                if os.path.isdir(p):
                    # 先算大小
                    sz = utils.dir_size(p, max_seconds=3)
                    shutil.rmtree(p, ignore_errors=True)
                    if os.path.exists(p):
                        # 部分删不掉（文件被占用），保守处理
                        fail += 1
                    else:
                        freed += sz
                        ok += 1
                        batch.note("删除缓存目录 %s" % p, human_size(sz))
                else:
                    sz = os.path.getsize(p)
                    os.remove(p)
                    freed += sz
                    ok += 1
            except Exception as e:
                utils.log("删除失败 %s: %s" % (p, e), "WARN")
                fail += 1
    return freed, ok, fail, ""


# ============================================================
# 大文件扫描
# ============================================================
def scan_large_files(roots=None, min_mb=LARGE_FILE_MB, progress=None,
                     cancel=None, limit=300):
    """
    扫描大文件。roots 为盘符列表，如 ['C:','D:']
    返回 [{'path','size','mtime','type'}]
    """
    if roots is None:
        roots = [d["letter"] for d in scan_drives()]
    min_bytes = min_mb * 1024 * 1024
    found = []
    skip_dirs = {"$recycle.bin", "system volume information", "windows", "winsxs",
                 "node_modules", ".git", "$windows.~bt", "$windows.~ws",
                 "recovery", "config.msi"}
    # Windows 目录单独跳，但用户可能想知道 windows 里的大文件 → 保留 subset
    t0 = time.time()

    for r in roots:
        root = r + "\\"
        if not os.path.isdir(root):
            continue
        for cur, dirs, files in os.walk(root, onerror=lambda e: None):
            if cancel and cancel():
                return found
            # 跳过顶层系统目录
            rel = os.path.relpath(cur, root).lower()
            depth = 0 if rel == "." else rel.count(os.sep) + 1
            if depth == 0:
                dirs[:] = [d for d in dirs if d.lower() not in skip_dirs]
            else:
                dirs[:] = [d for d in dirs
                           if d.lower() not in ("node_modules", "$recycle.bin",
                                                "system volume information",
                                                "config.msi")]
            for f in files:
                fp = os.path.join(cur, f)
                try:
                    st = os.stat(fp)
                except Exception:
                    continue
                if st.st_size >= min_bytes:
                    found.append({
                        "path": fp,
                        "size": st.st_size,
                        "mtime": st.st_mtime,
                        "type": os.path.splitext(f)[1].lower(),
                    })
            if progress and len(found) % 20 == 0:
                progress("已发现 %d 个大文件，当前：%s" % (len(found), cur),
                         None)
            if len(found) >= limit:
                break
        if len(found) >= limit:
            break

    found.sort(key=lambda x: -x["size"])
    if progress:
        progress("大文件扫描完成，共 %d 个" % len(found), 100)
    return found


# ============================================================
# 目录占用分析（懒加载树）
# ============================================================
def list_children(path, max_seconds=5):
    """
    列出某个目录下的一级子项及其大小，返回 [(name, full, size, is_dir)]
    按大小降序
    """
    out = []
    try:
        entries = list(os.scandir(path))
    except Exception:
        return out
    t0 = time.time()
    for e in entries:
        if time.time() - t0 > max_seconds:
            out.append((e.name, e.path, -1, e.is_dir(follow_symlinks=False)))
            continue
        try:
            if e.is_dir(follow_symlinks=False):
                sz = utils.dir_size(e.path, max_seconds=2)
                out.append((e.name, e.path, sz, True))
            else:
                sz = e.stat(follow_symlinks=False).st_size
                out.append((e.name, e.path, sz, False))
        except Exception:
            out.append((e.name, e.path, 0, False))
    out.sort(key=lambda x: -x[2])
    return out


def disk_usage_summary(letter, progress=None, cancel=None):
    """
    扫描某个盘的一级目录占用（用于"磁盘里有什么"总览）
    """
    root = letter.rstrip("\\") + "\\"
    kids = list_children(root, max_seconds=30)
    if progress:
        progress("分析完成", 100)
    return kids


# ============================================================
# v2: 分盘盘点 —— 每个盘装了什么软件、有什么大文件
# ============================================================
def _scan_drive_once(letter, min_mb=100, file_limit=80, dir_limit=25,
                     progress=None, cancel=None):
    """
    一次遍历把一个盘摸清楚：总大小、文件类型构成、大文件、一级目录占用。
    以前分三次扫，现在一次搞定，快得多。
    """
    from core.rules import EXT_TO_TYPE

    root = letter.rstrip("\\") + "\\"
    min_bytes = min_mb * 1024 * 1024
    skip_top = {"$recycle.bin", "system volume information", "config.msi",
                "$windows.~bt", "$windows.~ws", "$sysreset", "recovery"}
    skip_any = {"node_modules", "__pycache__", ".git", "$recycle.bin",
                "system volume information", "config.msi"}

    big = []
    types = {}
    dirs = {}
    total_size = 0
    file_count = 0
    t0 = time.time()
    last_report = t0

    for cur, dnames, fnames in os.walk(root, onerror=lambda e: None):
        if cancel and cancel():
            break
        rel = os.path.relpath(cur, root)
        if rel == ".":
            top = ""
            dnames[:] = [d for d in dnames if d.lower() not in skip_top]
        else:
            top = rel.split(os.sep)[0]
            dnames[:] = [d for d in dnames if d.lower() not in skip_any]

        for fn in fnames:
            fp = os.path.join(cur, fn)
            try:
                st = os.stat(fp)
            except Exception:
                continue
            size = st.st_size
            total_size += size
            file_count += 1
            if top:
                dirs[top] = dirs.get(top, 0) + size
            ext = os.path.splitext(fn)[1].lower()
            label = EXT_TO_TYPE.get(ext, "其他")
            rec = types.setdefault(label, [0, 0])
            rec[0] += size
            rec[1] += 1
            if size >= min_bytes:
                big.append({"path": fp, "size": size, "mtime": st.st_mtime})

        now = time.time()
        if progress and now - last_report > 1.2:
            last_report = now
            progress("正在扫描 %s 盘：已读 %d 个文件 / %s"
                     % (letter, file_count, utils.human_size(total_size)), None)

    big.sort(key=lambda x: -x["size"])
    type_list = [{"label": k, "size": v[0], "count": v[1]}
                 for k, v in types.items() if v[0] > 0]
    type_list.sort(key=lambda x: -x["size"])
    dir_list = sorted(((k, os.path.join(root, k), v, True)
                       for k, v in dirs.items()), key=lambda x: -x[2])

    return {
        "total_size": total_size,
        "file_count": file_count,
        "big_files": big[:file_limit],
        "big_count": len(big),
        "types": type_list,
        "top_dirs": dir_list[:dir_limit],
        "elapsed": time.time() - t0,
    }


def _soft_drive(s):
    """判断一个软件装在哪个盘"""
    for key in ("location", "icon", "uninstall", "quiet_uninstall"):
        v = (s.get(key) or "").strip().strip('"')
        m = re.search(r"([A-Za-z]):[\\/]", v)
        if m:
            return (m.group(1) + ":").upper()
    return ""


def drive_inventory(progress=None, cancel=None, file_limit=80, dir_limit=25,
                    letters=None):
    """
    对所有磁盘做一次盘点。

    返回 [{'letter','total','free','used','pct',
           'software':[{name,version,publisher,size,location,level,score},...],
           'big_files':[{path,size,mtime},...], 'big_count':N,
           'types':[{'label','size','count'},...],
           'top_dirs':[(name,path,size,is_dir),...],
           'file_count':N, 'scanned_size':N}]
    """
    from core import mod_software

    drives = [d for d in scan_drives() if d["total"] > 0]
    if letters:
        want = set(x.upper().rstrip(":") + ":" for x in letters)
        drives = [d for d in drives if d["letter"].upper() in want]

    if progress:
        progress("读取已安装软件列表…", 3)
    try:
        softs = mod_software.list_installed()
    except Exception as e:
        utils.log("盘点时读取软件列表失败: %s" % e, "WARN")
        softs = []

    out = []
    n = len(drives) or 1
    for i, d in enumerate(drives):
        if cancel and cancel():
            break
        letter = d["letter"].upper()
        base_pct = 5 + int(i * 90 / n)

        def sub_progress(msg, _p=None, _base=base_pct, _l=letter):
            if progress:
                progress(msg, _base)

        info = _scan_drive_once(letter, min_mb=100,
                                file_limit=file_limit,
                                dir_limit=dir_limit,
                                progress=sub_progress, cancel=cancel)

        sw = [s for s in softs if _soft_drive(s) == letter]
        sw.sort(key=lambda x: (-x.get("size", 0), -x.get("score", 0)))

        out.append({
            "letter": letter,
            "total": d["total"],
            "free": d["free"],
            "used": d["used"],
            "pct": d["pct"],
            "software": sw,
            "big_files": info["big_files"],
            "big_count": info["big_count"],
            "types": info["types"],
            "top_dirs": info["top_dirs"],
            "file_count": info["file_count"],
            "scanned_size": info["total_size"],
            "elapsed": info["elapsed"],
        })

    if progress:
        progress("盘点完成", 100)
    return out
