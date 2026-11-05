# -*- coding: utf-8 -*-
"""
360 / 奇虎 家族 检测与清理

扫描九个面：进程、服务/驱动、启动项、计划任务、安装目录、
注册表软件键、右键菜单、浏览器扩展、系统策略

每条结果都带"证据"，用户勾选后才处理。清理前自动备份。
"""
import os
import re
import glob
import winreg

from core import utils
from core.utils import (reg_key_exists, reg_list_subkeys, reg_list_values,
                        reg_read_value, reg_delete_tree, reg_delete_value,
                        reg_path_str, human_size)

HKLM = winreg.HKEY_LOCAL_MACHINE
HKCU = winreg.HKEY_CURRENT_USER
HKCR = winreg.HKEY_CLASSES_ROOT

# 判定关键词
KEYWORDS = ("360", "qihoo", "qhsafe", "zhudongfangyu", "360safe")


def _is_360(text):
    if not text:
        return False
    t = str(text).lower()
    return any(k in t for k in KEYWORDS)


def _mk(cat, name, detail, target, kind, level="high", data=None, extra=""):
    return {
        "id": "%s|%s|%s" % (kind, target, name),
        "category": cat,
        "name": name,
        "detail": detail,
        "target": target,
        "kind": kind,
        "level": level,
        "data": data or {},
        "extra": extra,
    }


# ============================================================
# 扫描
# ============================================================
def scan(progress=None):
    items = []
    steps = [
        ("正在检查运行中的 360 进程…", _scan_processes),
        ("正在检查 360 服务与驱动…", _scan_services),
        ("正在检查 360 开机启动项…", _scan_startup),
        ("正在检查 360 计划任务…", _scan_tasks),
        ("正在检查 360 安装目录…", _scan_dirs),
        ("正在检查 360 注册表残留…", _scan_registry),
        ("正在检查 360 右键菜单…", _scan_contextmenu),
        ("正在检查 360 浏览器扩展…", _scan_browser_ext),
        ("正在检查 360 系统策略…", _scan_policies),
    ]
    for i, (msg, fn) in enumerate(steps):
        if progress:
            progress(msg, int(i * 100 / len(steps)))
        try:
            items.extend(fn())
        except Exception as e:
            utils.log("扫描 %s 出错: %s" % (msg, e), "ERR")
    if progress:
        progress("扫描完成", 100)
    # 排序：高风险在前
    order = {"high": 0, "mid": 1, "low": 2}
    items.sort(key=lambda x: (order.get(x["level"], 3), x["category"]))
    return items


def _scan_processes():
    items = []
    for p in utils.list_processes():
        name = p["name"]
        if not name.endswith(".exe"):
            continue
        if name in _PROC_SET or _is_360(name):
            items.append(_mk(
                "进程", name,
                "正在运行的 360 组件：%s" % (p.get("exe") or "路径未知"),
                str(p["pid"]), "proc",
                data={"pid": p["pid"], "name": name, "exe": p.get("exe", "")},
                extra=p.get("exe", "")))
    return items


_PROC_SET = set()
try:
    from core.rules import PROC_360
    _PROC_SET = set(PROC_360.keys())
except Exception:
    pass


def _scan_services():
    items = []
    from core.rules import SERVICE_360_EXACT, SERVICE_360_FUZZY
    for s in utils.list_services():
        name = s["name"].lower()
        hit = name in SERVICE_360_EXACT
        if not hit:
            hit = any(f in name for f in SERVICE_360_FUZZY)
        if not hit and _is_360(s.get("image", "")):
            hit = True
        if not hit:
            continue
        label = SERVICE_360_EXACT.get(name) or "360 服务/驱动"
        state = s.get("state", "")
        items.append(_mk(
            "服务/驱动",
            s["name"],
            "%s  |  类型: %s  |  状态: %s" % (label, "驱动" if s["is_driver"] else "服务", state),
            s["name"], "service",
            data={"name": s["name"], "display": s["display"], "image": s["image"],
                  "state": state, "is_driver": s["is_driver"]},
            extra=s.get("image", "")))
    return items


_RUN_KEYS = [
    (HKCU, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKCU Run"),
    (HKCU, r"Software\Microsoft\Windows\CurrentVersion\RunOnce", "HKCU RunOnce"),
    (HKLM, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", "HKLM Run"),
    (HKLM, r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce", "HKLM RunOnce"),
    (HKLM, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run", "HKLM Run (32位)"),
    (HKLM, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\RunOnce", "HKLM RunOnce (32位)"),
]


def _scan_startup():
    items = []
    for hive, key, label in _RUN_KEYS:
        for name, val, typ in reg_list_values(hive, key):
            if _is_360(name) or _is_360(val):
                items.append(_mk(
                    "启动项", name,
                    "%s  →  %s" % (label, str(val)[:200]),
                    "%s\\%s" % (reg_path_str(hive, key), name), "run",
                    data={"hive": utils.HIVE_NAMES[hive], "key": key, "value": name},
                    extra=str(val)))

    # 启动文件夹
    startup_dirs = [
        os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup"),
        os.path.join(os.environ.get("PROGRAMDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup"),
    ]
    for d in startup_dirs:
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if _is_360(f):
                items.append(_mk(
                    "启动项", f, "启动文件夹中的 360 快捷方式",
                    os.path.join(d, f), "file",
                    data={"path": os.path.join(d, f)},
                    extra=os.path.join(d, f)))
    return items


def _scan_tasks():
    items = []
    from core.rules import TASK_360_FUZZY
    for t in utils.list_tasks():
        full = (t["path"] or "\\") + t["name"]
        if not _is_360(full):
            continue
        items.append(_mk(
            "计划任务", t["name"],
            "计划任务 %s  |  状态: %s" % (full, t["state"]),
            full, "task",
            data={"path": t["path"], "name": t["name"]},
            extra=full))
    return items


def _sys_drive_fix(p):
    """把规则里写死的 C: 换成真实系统盘"""
    sd = os.environ.get("SystemDrive", "C:")
    if sd.upper() != "C:" and p.upper().startswith("C:\\"):
        return sd + p[2:]
    return p


def _scan_dirs():
    items = []
    from core.rules import DIR_360, DIR_360_USER
    candidates = []
    for d in DIR_360:
        candidates.append(_sys_drive_fix(d))
    la = os.environ.get("LOCALAPPDATA", "")
    ad = os.environ.get("APPDATA", "")
    for n in DIR_360_USER:
        if la:
            candidates.append(os.path.join(la, n))
        if ad:
            candidates.append(os.path.join(ad, n))

    seen = set()
    for d in candidates:
        p = os.path.abspath(d)
        if p.lower() in seen:
            continue
        seen.add(p.lower())
        if not os.path.exists(p):
            continue
        size = utils.dir_size(p, max_seconds=4)
        # 找卸载程序
        uninst = _find_uninstaller(p)
        items.append(_mk(
            "安装目录", os.path.basename(p) or p,
            "占用 %s  |  %s%s" % (human_size(size), p,
                                 ("  |  发现官方卸载器: " + os.path.basename(uninst)) if uninst else ""),
            p, "dir",
            data={"path": p, "size": size, "uninstaller": uninst},
            extra=p))
    return items


def _find_uninstaller(root):
    names = ["uninst.exe", "uninstall.exe", "360uninst.exe", "uninst360.exe",
             "uninst.exe", "卸载.exe", "uninstall360.exe"]
    for n in names:
        p = os.path.join(root, n)
        if os.path.exists(p):
            return p
    # 深一层找
    for pat in ("*/uninst*.exe", "*/uninstall*.exe", "*/卸载*.exe"):
        for p in glob.glob(os.path.join(root, pat))[:5]:
            return p
    return ""


def _scan_registry():
    items = []
    roots = [
        (HKLM, r"SOFTWARE"),
        (HKLM, r"SOFTWARE\WOW6432Node"),
        (HKCU, r"SOFTWARE"),
    ]
    checked = set()
    for hive, base in roots:
        for sub in reg_list_subkeys(hive, base):
            sl = sub.lower()
            if not _is_360(sl):
                continue
            path = base + "\\" + sub
            key = (utils.HIVE_NAMES[hive], path.lower())
            if key in checked:
                continue
            checked.add(key)
            # 跳过含 Uninstall 的（那是软件列表，单独处理）
            items.append(_mk(
                "注册表残留", sub,
                "软件配置残留：%s" % reg_path_str(hive, path),
                reg_path_str(hive, path), "reg",
                data={"hive": utils.HIVE_NAMES[hive], "path": path},
                extra=reg_path_str(hive, path)))
    return items


_CTX_ROOTS = [
    r"*\shellex\ContextMenuHandlers",
    r"Directory\shellex\ContextMenuHandlers",
    r"Directory\Background\shellex\ContextMenuHandlers",
    r"Folder\shellex\ContextMenuHandlers",
    r"Drive\shellex\ContextMenuHandlers",
    r"AllFilesystemObjects\shellex\ContextMenuHandlers",
    r"DesktopBackground\Shell",
    r"Directory\Background\shell",
    r"Directory\shell",
    r"*\shell",
    r"Folder\shell",
]


def _scan_contextmenu():
    items = []
    for base in _CTX_ROOTS:
        for sub in reg_list_subkeys(HKCR, base):
            full = base + "\\" + sub
            # 读默认值（通常是 CLSID 或描述）
            dv = reg_read_value(HKCR, full, "")
            text = "%s %s" % (sub, dv)
            if not _is_360(text):
                # 再看 command
                cmd = reg_read_value(HKCR, full + r"\command", "")
                if not _is_360(cmd):
                    continue
                text = cmd
            items.append(_mk(
                "右键菜单", sub,
                "注册表位置：HKEY_CLASSES_ROOT\\%s" % full,
                "HKCR\\" + full, "ctxtreg",
                level="mid",
                data={"key": full},
                extra=str(text)[:200]))
    return items


def _scan_browser_ext():
    items = []
    bases = [
        ("Edge", os.path.join(os.environ.get("LOCALAPPDATA", ""),
                              r"Microsoft\Edge\User Data")),
        ("Chrome", os.path.join(os.environ.get("LOCALAPPDATA", ""),
                                r"Google\Chrome\User Data")),
        ("360浏览器", os.path.join(os.environ.get("LOCALAPPDATA", ""),
                                r"360Chrome\Chrome\User Data")),
    ]
    for browser, base in bases:
        if not os.path.isdir(base):
            continue
        for prof in os.listdir(base):
            ext_root = os.path.join(base, prof, "Extensions")
            if not os.path.isdir(ext_root):
                continue
            for eid in os.listdir(ext_root):
                epath = os.path.join(ext_root, eid)
                # 找版本目录下的 manifest
                manifests = glob.glob(os.path.join(epath, "*", "manifest.json"))
                if not manifests:
                    continue
                mf = manifests[0]
                name = eid
                try:
                    import json
                    with open(mf, encoding="utf-8", errors="ignore") as f:
                        m = json.load(f)
                    name = m.get("name", eid)
                    # 处理 __MSG_xxx__ 形式的本地化名
                    if name.startswith("__MSG_"):
                        name = _read_locale_name(mf, name)
                except Exception:
                    pass
                if not _is_360(name) and not _is_360(eid) and not _is_360(epath):
                    continue
                items.append(_mk(
                    "浏览器扩展", name,
                    "%s 配置 %s 中的扩展：%s" % (browser, prof, eid),
                    epath, "extdir",
                    level="mid",
                    data={"path": epath, "browser": browser, "ext_id": eid},
                    extra=epath))
    return items


def _read_locale_name(manifest_path, msg_key):
    try:
        import json
        with open(manifest_path, encoding="utf-8", errors="ignore") as f:
            m = json.load(f)
        default = m.get("default_locale", "zh_CN")
        loc = os.path.join(os.path.dirname(manifest_path), "_locales", default, "messages.json")
        if os.path.exists(loc):
            with open(loc, encoding="utf-8", errors="ignore") as f:
                msgs = json.load(f)
            key = msg_key[6:-2] if msg_key.endswith("__") else msg_key[6:]
            key = msg_key.replace("__MSG_", "").replace("__", "")
            for k, v in msgs.items():
                if k.lower() == key.lower():
                    return v.get("message", msg_key)
    except Exception:
        pass
    return msg_key


def _scan_policies():
    """360 常写浏览器策略来实现主页/搜索劫持"""
    items = []
    targets = [
        (HKLM, r"SOFTWARE\Policies\Microsoft\Edge"),
        (HKCU, r"SOFTWARE\Policies\Microsoft\Edge"),
        (HKLM, r"SOFTWARE\Policies\Google\Chrome"),
        (HKCU, r"SOFTWARE\Policies\Google\Chrome"),
    ]
    hijack_keys = ["HomepageLocation", "RestoreOnStartup", "RestoreOnStartupURLs",
                   "NewTabPageLocation", "DefaultSearchProviderName",
                   "DefaultSearchProviderSearchURL", "DefaultSearchProviderKeyword",
                   "DefaultSearchProviderEnabled", "URLWhitelist", "URLBlacklist"]
    for hive, path in targets:
        for k in hijack_keys:
            v = reg_read_value(hive, path, k)
            if v is None:
                continue
            sv = str(v)
            if "360" in sv.lower() or k in ("HomepageLocation", "RestoreOnStartup",
                                            "NewTabPageLocation",
                                            "DefaultSearchProviderSearchURL"):
                items.append(_mk(
                    "系统策略", k,
                    "浏览器策略被写入：%s = %s" % (k, sv[:180]),
                    "%s\\%s" % (reg_path_str(hive, path), k), "policyvalue",
                    data={"hive": utils.HIVE_NAMES[hive], "path": path,
                          "name": k, "value": v},
                    extra=sv))
        # 整个策略键存不存在
    return items


# ============================================================
# 清理
# ============================================================
def clean(items, batch, progress=None):
    """
    执行清理。返回 (成功数, 失败数, 消息列表)
    顺序很关键：先杀进程 → 停服务 → 删任务 → 删启动项 → 删注册表 → 删目录
    """
    order = {"proc": 0, "service": 1, "task": 2, "run": 3, "policyvalue": 4,
             "ctxtreg": 5, "reg": 6, "file": 7, "extdir": 8, "dir": 9}
    items = sorted(items, key=lambda x: order.get(x["kind"], 99))

    ok = fail = 0
    msgs = []
    total = len(items) or 1

    for idx, it in enumerate(items):
        if progress:
            progress("清理中：%s" % it["name"], int(idx * 100 / total))
        try:
            r_ok, msg = _do_clean(it, batch)
        except Exception as e:
            r_ok, msg = False, str(e)
        if r_ok:
            ok += 1
        else:
            fail += 1
        msgs.append("%s %s — %s" % ("✓" if r_ok else "✗", it["name"], msg))
        utils.log("清理 %s: %s (%s)" % (it["name"], msg, "OK" if r_ok else "FAIL"))

    if progress:
        progress("清理完成", 100)
    return ok, fail, msgs


def _do_clean(it, batch):
    kind = it["kind"]
    d = it["data"]

    # ---------- 进程 ----------
    if kind == "proc":
        pid, name = d.get("pid"), d.get("name")
        code, out = utils.kill_process(pid=pid)
        if code != 0:
            code2, out2 = utils.kill_process(name=name)
            if code2 != 0:
                return False, ("被 360 自我保护拦截，需先关闭 360 自保护或进安全模式"
                               if "拒绝" in out or "Access" in out or code == 0
                               else "结束失败: %s" % out.strip()[:80])
        batch.note("结束进程 %s (PID %s)" % (name, pid))
        return True, "已结束"

    # ---------- 服务 ----------
    if kind == "service":
        name = d["name"]
        utils.stop_service(name)
        code, out = utils.delete_service(name)
        if code != 0:
            # 退一步试注册表删除
            p = r"SYSTEM\CurrentControlSet\Services\%s" % name
            if reg_key_exists(HKLM, p):
                if not batch.backup_reg(HKLM, p, "服务 " + name):
                    return False, "备份失败，已取消删除"
                if reg_delete_tree(HKLM, p):
                    return True, "服务已删除（注册表方式）"
            return False, "删除失败: %s" % out.strip()[:80]
        batch.note("删除服务 %s" % name)
        return True, "服务已删除"

    # ---------- 计划任务 ----------
    if kind == "task":
        code, out = utils.delete_task(d.get("path"), d["name"])
        if code != 0:
            return False, "删除失败: %s" % out.strip()[:80]
        batch.note("删除计划任务 %s" % it["target"])
        return True, "已删除"

    # ---------- 启动项 ----------
    if kind == "run":
        hive = utils.hive_from_name(d["hive"])
        key, val = d["key"], d["value"]
        batch.backup_reg_value(hive, key, val, "启动项 " + val)
        if reg_delete_value(hive, key, val):
            return True, "启动项已移除"
        return False, "删除失败（可能需要管理员权限）"

    # ---------- 策略值 ----------
    if kind == "policyvalue":
        hive = utils.hive_from_name(d["hive"])
        batch.backup_reg_value(hive, d["path"], d["name"], "策略 " + d["name"])
        if reg_delete_value(hive, d["path"], d["name"]):
            return True, "策略已清除"
        return False, "清除失败"

    # ---------- 右键菜单 ----------
    if kind == "ctxtreg":
        key = d["key"]
        if not batch.backup_reg(HKCR, key, "右键菜单 " + it["name"]):
            return False, "备份失败，已取消删除"
        if reg_delete_tree(HKCR, key):
            return True, "右键菜单已删除"
        return False, "删除失败"

    # ---------- 注册表残留 ----------
    if kind == "reg":
        hive = utils.hive_from_name(d["hive"])
        path = d["path"]
        if not batch.backup_reg(hive, path, "注册表 " + it["name"]):
            return False, "备份失败，已取消删除"
        if reg_delete_tree(hive, path):
            return True, "注册表项已删除（可恢复）"
        return False, "删除失败"

    # ---------- 文件 / 目录 / 扩展 ----------
    if kind in ("file", "dir", "extdir"):
        p = d["path"]
        if not os.path.exists(p):
            return True, "已不存在"
        if utils.is_protected(p):
            return False, "属于系统保护路径，已跳过"
        ok, msg = batch.quarantine(p, it["name"])
        if ok:
            return True, "已移入隔离区（可还原）"
        return False, "移动失败: %s（程序可能正在运行）" % msg

    return False, "未知类型"


# ============================================================
# 官方卸载器
# ============================================================
def find_all_uninstallers():
    """找到所有 360 官方卸载程序"""
    out = []
    from core.rules import DIR_360, DIR_360_USER
    cands = [_sys_drive_fix(d) for d in DIR_360]
    la = os.environ.get("LOCALAPPDATA", "")
    ad = os.environ.get("APPDATA", "")
    for n in DIR_360_USER:
        if la:
            cands.append(os.path.join(la, n))
        if ad:
            cands.append(os.path.join(ad, n))
    seen = set()
    for d in cands:
        if not os.path.isdir(d):
            continue
        u = _find_uninstaller(d)
        if u and u.lower() not in seen:
            seen.add(u.lower())
            out.append({"dir": d, "uninstaller": u})
    # 从卸载列表里找（更靠谱）
    try:
        from core.mod_software import list_installed
        for s in list_installed():
            if "360" in (s.get("name", "") + s.get("publisher", "")).lower() or \
               "qihoo" in (s.get("name", "") + s.get("publisher", "")).lower():
                if s.get("uninstall") and s["uninstall"].lower() not in seen:
                    seen.add(s["uninstall"].lower())
                    out.append({"dir": s.get("location", ""), "uninstaller": s["uninstall"],
                                "name": s.get("name")})
    except Exception:
        pass
    return out
