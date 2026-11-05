# -*- coding: utf-8 -*-
r"""
Edge / 浏览器 被劫持检测与修复

360 等软件劫持浏览器通常只用三招：
  1. 改快捷方式参数（msedge.exe 后面挂一个网址）
  2. 写组策略（Policies\Microsoft\Edge），优先级最高，界面里改不掉
  3. 改用户配置 Preferences（主页、启动页、默认搜索）

本模块三招全查，逐项修复，每步都先备份。
"""
import os
import re
import json
import glob
import shutil
import winreg

from core import utils
from core.utils import (reg_read_value, reg_delete_value, reg_list_subkeys,
                        reg_path_str)

HKLM = winreg.HKEY_LOCAL_MACHINE
HKCU = winreg.HKEY_CURRENT_USER
HKCR = winreg.HKEY_CLASSES_ROOT

EDGE_EXE_HINTS = ("msedge.exe", "microsoft\\edge")

# 已知劫持域名特征
HIJACK_DOMAINS = [
    "360.cn", "360.com", "hao.360", "so.com", "hao123", "2345.com",
    "duba.com", "liebao", "sogou", "baidu.com/s?wd", "114so", "wps.cn",
    "rising.com.cn", "kouzip", "hao.qq.com",
]


def _is_hijack_url(u):
    if not u:
        return False
    ul = str(u).lower()
    if not (ul.startswith("http") or ".com" in ul or ".cn" in ul):
        return False
    return any(d in ul for d in HIJACK_DOMAINS)


def _mk(cat, name, detail, target, kind, level="high", data=None, extra="",
        default=None):
    return {
        "id": "%s|%s" % (kind, target),
        "category": cat,
        "name": name,
        "detail": detail,
        "target": target,
        "kind": kind,
        "level": level,
        "data": data or {},
        "extra": extra,
        "default_checked": (level == "high") if default is None else bool(default),
    }


# ============================================================
# 扫描
# ============================================================
def scan(progress=None):
    items = []
    steps = [
        ("检查浏览器组策略…", _scan_policies),
        ("检查用户配置文件…", _scan_preferences),
        ("检查快捷方式参数…", _scan_shortcuts),
        ("检查文件关联…", _scan_associations),
        ("检查强制安装的扩展…", _scan_force_ext),
        ("检查已装扩展…", _scan_extensions),
        ("检查默认浏览器…", _scan_default_browser),
    ]
    for i, (msg, fn) in enumerate(steps):
        if progress:
            progress(msg, int(i * 100 / len(steps)))
        try:
            items.extend(fn())
        except Exception as e:
            utils.log("浏览器扫描 %s 出错: %s" % (msg, e), "ERR")
    if progress:
        progress("检查完成", 100)
    order = {"high": 0, "mid": 1, "low": 2}
    items.sort(key=lambda x: (order.get(x["level"], 3), x["category"]))
    return items


# ---------- 1. 组策略 ----------
POLICY_TARGETS = [
    (HKLM, r"SOFTWARE\Policies\Microsoft\Edge", "Edge 组策略(本机)"),
    (HKCU, r"SOFTWARE\Policies\Microsoft\Edge", "Edge 组策略(用户)"),
    (HKLM, r"SOFTWARE\Policies\Google\Chrome", "Chrome 组策略(本机)"),
    (HKCU, r"SOFTWARE\Policies\Google\Chrome", "Chrome 组策略(用户)"),
    (HKLM, r"SOFTWARE\Policies\Microsoft\Edge\Recommended", "Edge 推荐策略"),
]

WATCH_VALUES = [
    "HomepageLocation", "HomepageIsNewTabPage",
    "RestoreOnStartup", "NewTabPageLocation",
    "DefaultSearchProviderEnabled", "DefaultSearchProviderName",
    "DefaultSearchProviderKeyword", "DefaultSearchProviderSearchURL",
    "DefaultSearchProviderSuggestURL", "DefaultSearchProviderIconURL",
    "BrowserSignin", "SmartScreenEnabled", "ExtensionInstallForcelist",
    "URLBlocklist", "URLAllowlist",
]


def _scan_policies():
    items = []
    for hive, path, label in POLICY_TARGETS:
        for v in WATCH_VALUES:
            val = reg_read_value(hive, path, v)
            if val is None:
                continue
            sv = str(val)
            if v == "RestoreOnStartup":
                risky = True
            elif v == "HomepageIsNewTabPage":
                risky = False
            elif _is_hijack_url(sv):
                risky = True
            elif v.startswith("DefaultSearchProvider") and v not in ("DefaultSearchProviderEnabled",):
                risky = True
            elif v == "ExtensionInstallForcelist":
                risky = True
            else:
                risky = False
            if not risky:
                continue
            items.append(_mk(
                "组策略", "%s - %s" % (label, v),
                "值 = %s   ← 策略优先级最高，在浏览器设置里改不掉" % sv[:150],
                "%s\\%s" % (reg_path_str(hive, path), v), "policy",
                data={"hive": utils.HIVE_NAMES[hive], "path": path, "name": v},
                extra=sv))

        # RestoreOnStartupURLs 子键
        sub = path + r"\RestoreOnStartupURLs"
        for k in reg_list_subkeys(hive, sub):
            v = reg_read_value(hive, sub, k)
            if v:
                items.append(_mk(
                    "组策略", "%s - 启动页 %s" % (label, k),
                    "浏览器启动时会打开：%s" % v,
                    "%s\\RestoreOnStartupURLs\\%s" % (reg_path_str(hive, path), k),
                    "policy",
                    data={"hive": utils.HIVE_NAMES[hive],
                          "path": path + r"\RestoreOnStartupURLs", "name": k},
                    extra=str(v)))
    return items


# ---------- 2. 用户配置 ----------
def edge_user_data_dirs():
    la = os.environ.get("LOCALAPPDATA", "")
    out = []
    for b in ("Microsoft\\Edge\\User Data", "Google\\Chrome\\User Data"):
        p = os.path.join(la, b)
        if os.path.isdir(p):
            out.append(p)
    return out


def _scan_preferences():
    items = []
    for ud in edge_user_data_dirs():
        browser = "Edge" if "Edge" in ud else "Chrome"
        for prof_dir in glob.glob(os.path.join(ud, "*")):
            if not os.path.isdir(prof_dir):
                continue
            base = os.path.basename(prof_dir)
            if base in ("User Data",):
                continue
            pref = os.path.join(prof_dir, "Preferences")
            if not os.path.exists(pref):
                continue
            try:
                with open(pref, encoding="utf-8", errors="ignore") as f:
                    d = json.load(f)
            except Exception as e:
                utils.log("读取 %s 失败: %s" % (pref, e), "WARN")
                continue

            # 启动页
            sess = d.get("session") or {}
            urls = sess.get("startup_urls") or []
            bad = [u for u in urls if _is_hijack_url(u)]
            if bad or (sess.get("restore_on_startup") == 4 and urls):
                items.append(_mk(
                    "启动页", "%s - %s 启动页被改" % (browser, base),
                    "打开浏览器会自动跳到：%s" % (", ".join(urls)[:160] or "(空)"),
                    pref, "pref",
                    data={"file": pref, "field": "session.startup_urls",
                          "browser": browser, "profile": base},
                    extra=",".join(urls)))

            # 主页
            home = d.get("homepage") or ""
            if _is_hijack_url(home):
                items.append(_mk(
                    "主页", "%s - %s 主页被改" % (browser, base),
                    "主页 = %s" % home,
                    pref + "#homepage", "pref",
                    data={"file": pref, "field": "homepage",
                          "browser": browser, "profile": base},
                    extra=home))

            # 新标签页
            ntp = ""
            br = d.get("browser") or {}
            if isinstance(br, dict):
                ntp = br.get("new_tab_page_location") or ""
            if _is_hijack_url(ntp):
                items.append(_mk(
                    "新标签页", "%s - %s 新标签页被改" % (browser, base),
                    "新标签页 = %s" % ntp,
                    pref + "#ntp", "pref",
                    data={"file": pref, "field": "browser.new_tab_page_location",
                          "browser": browser, "profile": base},
                    extra=ntp))

            # 默认搜索
            dsp = d.get("default_search_provider_data") or {}
            if isinstance(dsp, dict):
                tmpl = json.dumps(dsp, ensure_ascii=False)
                if _is_hijack_url(tmpl) or "360" in tmpl.lower():
                    items.append(_mk(
                        "默认搜索", "%s - %s 默认搜索引擎被改" % (browser, base),
                        "搜索被劫持到第三方：%s" % tmpl[:180],
                        pref + "#search", "pref",
                        data={"file": pref, "field": "default_search_provider_data",
                              "browser": browser, "profile": base},
                        extra=tmpl[:200]))
    return items


# ---------- 3. 快捷方式 ----------
def edge_shortcut_paths():
    paths = []
    la = os.environ.get("LOCALAPPDATA", "")
    pd = os.environ.get("PROGRAMDATA", "")
    up = os.environ.get("USERPROFILE", "")
    pub = os.environ.get("PUBLIC", r"C:\Users\Public")

    dirs = [
        os.path.join(up, "Desktop"),
        os.path.join(pub, "Desktop"),
        os.path.join(la, r"Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar"),
        os.path.join(la, r"Microsoft\Windows\Start Menu\Programs"),
        os.path.join(pd, r"Microsoft\Windows\Start Menu\Programs"),
    ]
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for pat in ("*.lnk", "*.url"):
            for p in glob.glob(os.path.join(d, pat)):
                paths.append(p)
        # 一级子目录
        try:
            for sub in os.listdir(d):
                sp = os.path.join(d, sub)
                if os.path.isdir(sp):
                    for p in glob.glob(os.path.join(sp, "*.lnk")):
                        paths.append(p)
        except Exception:
            pass
    return list(dict.fromkeys(paths))


def read_lnk(path):
    """用 PowerShell COM 读取 .lnk 的目标和参数（单个）"""
    if not path.lower().endswith(".lnk"):
        return None
    script = (
        "$s=New-Object -ComObject WScript.Shell;"
        "$l=$s.CreateShortcut('%s');"
        "Write-Output ($l.TargetPath + '|||' + $l.Arguments)"
        % path.replace("'", "''")
    )
    code, out = utils.run_ps(script, timeout=20)
    if code != 0 or "|||" not in out:
        return None
    t, a = out.strip().split("|||", 1)
    return {"target": t.strip(), "args": a.strip()}


def read_lnks_batch(paths):
    """
    批量读取多个 .lnk，一次 PowerShell 调用搞定。
    返回 {path: {'target':..., 'args':...}}
    """
    targets = [p for p in paths if p.lower().endswith(".lnk")]
    if not targets:
        return {}
    out_map = {}
    CHUNK = 60
    for i in range(0, len(targets), CHUNK):
        chunk = targets[i:i + CHUNK]
        arr = ",".join("'%s'" % p.replace("'", "''") for p in chunk)
        script = (
            "$s=New-Object -ComObject WScript.Shell;"
            "$fs=@(%s);"
            "foreach($f in $fs){try{"
            "$l=$s.CreateShortcut($f);"
            "Write-Output ($f+'|||'+$l.TargetPath+'|||'+$l.Arguments)"
            "}catch{}}"
            % arr)
        code, out = utils.run_ps(script, timeout=60)
        if code != 0:
            continue
        for line in out.splitlines():
            line = line.strip()
            if "|||" not in line:
                continue
            parts = line.split("|||")
            if len(parts) < 3:
                continue
            f = parts[0]
            out_map[f] = {"target": parts[1].strip(),
                          "args": "|||".join(parts[2:]).strip()}
    return out_map


def _scan_shortcuts():
    items = []
    all_paths = edge_shortcut_paths()

    # 先处理 .url（纯文本，不用调 PowerShell）
    lnk_paths = []
    for p in all_paths:
        if p.lower().endswith(".url"):
            try:
                with open(p, encoding="utf-8", errors="ignore") as f:
                    txt = f.read()
                m = re.search(r"URL=(.+)", txt, re.I)
                if m and _is_hijack_url(m.group(1).strip()):
                    items.append(_mk(
                        "快捷方式", os.path.basename(p),
                        "网址快捷方式指向：%s" % m.group(1).strip()[:150],
                        p, "shortcut_url", level="mid",
                        data={"path": p}, extra=m.group(1).strip()))
            except Exception:
                pass
        else:
            lnk_paths.append(p)

    # 批量读 lnk
    infos = read_lnks_batch(lnk_paths)

    for p in lnk_paths:
        info = infos.get(p)
        if not info:
            continue
        target = (info["target"] or "").lower()
        args = info["args"] or ""
        name = os.path.basename(p)

        is_edge = "msedge.exe" in target or "\\edge\\" in target
        if not is_edge and not any(k in name.lower() for k in ("edge", "浏览器", "browser")):
            continue

        bad_args = []
        if args:
            for tok in re.findall(r"(https?://\S+|www\.\S+)", args):
                bad_args.append(tok)
            if re.search(r"--(app|startup-url|homepage)=.+(http|\w+\.(com|cn))", args, re.I):
                bad_args.append(args)

        if bad_args:
            suffer = "360" if "360" in args.lower() else ""
            items.append(_mk(
                "快捷方式", name,
                "目标：%s\n参数：%s%s" % (info["target"], args[:200],
                                      "\n→ 被%s 附加了跳转地址" % suffer if suffer else ""),
                p, "shortcut",
                data={"path": p, "target": info["target"], "args": args},
                extra=args[:300]))
    return items


# ---------- 4. 文件关联 ----------
def _scan_associations():
    items = []
    # http/https 的 open 命令
    for proto in ("http", "https"):
        p = proto + r"\shell\open\command"
        v = reg_read_value(HKCR, p, "")
        if v and ("360" in str(v).lower() or "qihoo" in str(v).lower()):
            items.append(_mk(
                "文件关联", "%s 协议被接管" % proto,
                "打开网页会调用：%s" % str(v)[:200],
                "%s\\%s" % (reg_path_str(HKCR, p), "(默认)"), "assoc",
                data={"path": p, "name": ""}, extra=str(v)))

    # .html / .htm
    for ext in (".html", ".htm", ".mht", ".mhtml"):
        try:
            with winreg.OpenKey(HKCR, ext) as k:
                v, _ = winreg.QueryValueEx(k, "")
            if v and "360" in str(v).lower():
                items.append(_mk(
                    "文件关联", "%s 打开方式被改" % ext,
                    "关联到：%s" % v, "%s\\%s" % (reg_path_str(HKCR, ext), "(默认)"),
                    "assoc_value",
                    data={"path": ext, "name": ""}, extra=str(v)))
        except Exception:
            pass
    return items


# ---------- 5. 强制扩展（策略层） ----------
def _scan_force_ext():
    items = []
    # 策略里 Forcelist
    for hive, path, label in [(HKLM, r"SOFTWARE\Policies\Microsoft\Edge\ExtensionInstallForcelist", "Edge"),
                              (HKCU, r"SOFTWARE\Policies\Microsoft\Edge\ExtensionInstallForcelist", "Edge"),
                              (HKLM, r"SOFTWARE\Policies\Google\Chrome\ExtensionInstallForcelist", "Chrome")]:
        for k in reg_list_subkeys(hive, path):
            v = reg_read_value(hive, path, k)
            if v:
                items.append(_mk(
                    "强制扩展", "%s 被策略强制安装扩展" % label,
                    "扩展 ID：%s  ← 无法在扩展管理里删除" % str(v)[:120],
                    "%s\\%s" % (reg_path_str(hive, path), k), "policy",
                    data={"hive": utils.HIVE_NAMES[hive], "path": path, "name": k},
                    extra=str(v)))
    return items


# ---------- 6. 实际安装的扩展 ----------
EXT_AD_HINTS = (
    "广告", "推广", "导航", "购物", "特价", "红包", "资讯", "热点",
    "toolbar", "advert", "popup", "360", "2345", "助手", "加速",
)

# 官方商店的更新地址，不在里面的基本是侧载进来的
OFFICIAL_UPDATE_HOSTS = (
    "clients2.google.com", "chrome.google.com", "google.com",
    "edge.microsoft.com", "microsoft.com",
)


def _scan_extensions():
    items = []
    for ud in edge_user_data_dirs():
        browser = "Edge" if "Edge" in ud else "Chrome"
        for prof_dir in glob.glob(os.path.join(ud, "*")):
            ext_root = os.path.join(prof_dir, "Extensions")
            if not os.path.isdir(ext_root):
                continue
            prof = os.path.basename(prof_dir)
            try:
                eids = os.listdir(ext_root)
            except Exception:
                continue
            for eid in eids:
                epath = os.path.join(ext_root, eid)
                if not os.path.isdir(epath):
                    continue
                manifests = glob.glob(os.path.join(epath, "*", "manifest.json"))
                if not manifests:
                    continue
                mf = manifests[0]
                name, perms, update_url = eid, [], ""
                try:
                    with open(mf, encoding="utf-8", errors="ignore") as f:
                        m = json.load(f)
                    name = m.get("name") or eid
                    if name.startswith("__MSG_"):
                        name = _ext_localized(mf, name) or eid
                    raw = (m.get("permissions") or []) + \
                          (m.get("host_permissions") or [])
                    perms = [str(p).lower() for p in raw]
                    update_url = m.get("update_url") or ""
                except Exception:
                    pass

                low = (name + " " + update_url).lower()
                ad_hit = [k for k in EXT_AD_HINTS if k in low]
                side = bool(update_url) and not any(
                    h in update_url.lower() for h in OFFICIAL_UPDATE_HOSTS)
                notify = "notifications" in perms
                all_urls = "<all_urls>" in perms

                # 只有"来路不明 + 要高权限"才值得报，正常商店扩展不打扰
                if not ad_hit and not (side and (notify or all_urls)):
                    continue

                level = "high" if ad_hit else "mid"
                why = []
                if ad_hit:
                    why.append("名称/来源含可疑关键词「%s」" % ad_hit[0])
                if side:
                    why.append("不是从官方商店装的（更新源 %s）" % update_url[:50])
                if notify:
                    why.append("能给你弹网页通知")
                if all_urls:
                    why.append("能读取你访问的所有网页")

                items.append(_mk(
                    "已装扩展", name,
                    "%s · 配置 %s\n扩展 ID：%s\n→ %s"
                    % (browser, prof, eid, "；".join(why)),
                    epath, "extdir", level=level,
                    default=(level == "high"),
                    data={"path": epath, "browser": browser,
                          "ext_id": eid, "profile": prof},
                    extra=name))
    return items


def _ext_localized(manifest_path, msg_key):
    try:
        with open(manifest_path, encoding="utf-8", errors="ignore") as f:
            m = json.load(f)
        loc = m.get("default_locale", "zh_CN")
        lf = os.path.join(os.path.dirname(manifest_path), "_locales", loc,
                          "messages.json")
        if os.path.exists(lf):
            with open(lf, encoding="utf-8", errors="ignore") as f:
                msgs = json.load(f)
            key = msg_key.replace("__MSG_", "").replace("__", "")
            for k, v in msgs.items():
                if k.lower() == key.lower():
                    return v.get("message")
    except Exception:
        pass
    return None


# ---------- 7. 默认浏览器 ----------
DEFAULT_PROG_MAP = [
    ("MSEdgeHTM", "Microsoft Edge", False),
    ("ChromeHTML", "Google Chrome", False),
    ("FirefoxURL", "Mozilla Firefox", False),
    ("360seHTML", "360 安全浏览器", True),
    ("360chrome", "360 极速浏览器", True),
    ("360SE", "360 安全浏览器", True),
    ("liebaoHTML", "猎豹浏览器", True),
    ("SogouExplorer", "搜狗浏览器", True),
    ("QQBrowser", "QQ 浏览器", False),
    ("BaiduBrowser", "百度浏览器", True),
]


def current_default_browser():
    """返回 (显示名, 是否被流氓浏览器占用, ProgId)"""
    p = (r"Software\Microsoft\Windows\Shell\Associations"
         r"\UrlAssociations\http\UserChoice")
    prog = str(reg_read_value(HKCU, p, "ProgId") or "")
    pl = prog.lower()
    for key, label, bad in DEFAULT_PROG_MAP:
        if key.lower() in pl:
            return label, bad, prog
    return (prog or "未知", False, prog)


def _scan_default_browser():
    items = []
    label, bad, prog = current_default_browser()
    if not bad:
        return items
    items.append(_mk(
        "默认浏览器", "默认浏览器是 %s" % label,
        "现在点开任何网页都会用 %s 打开。\n\n"
        "Windows 对这个设置有哈希校验，工具不会硬改——"
        "硬改会被系统判定为「应用默认设置已被重置」并弹提示。\n"
        "→ 其它项修好后，点「打开默认应用设置」手动改回 Edge 就行。" % label,
        "default_browser", "default_browser",
        level="high", default=False,
        data={"name": label, "prog": prog}, extra=label))
    return items


def open_default_apps_settings():
    try:
        os.startfile("ms-settings:defaultapps")
        return True
    except Exception:
        return False


# ============================================================
# 修复
# ============================================================
def fix(items, batch, progress=None):
    """返回 (成功数, 失败数, 消息列表)"""
    ok = fail = 0
    msgs = []
    total = len(items) or 1
    edge_running = _browser_running()

    for i, it in enumerate(items):
        if progress:
            progress("修复：%s" % it["name"], int(i * 100 / total))
        try:
            r, msg = _do_fix(it, batch)
        except Exception as e:
            r, msg = False, str(e)
        if r:
            ok += 1
        else:
            fail += 1
        msgs.append("%s %s — %s" % ("✓" if r else "✗", it["name"], msg))

    if edge_running and any(it["kind"] in ("pref", "shortcut") for it in items):
        msgs.append("⚠ 检测到浏览器正在运行，部分改动可能在重启后被覆盖。建议关闭浏览器后重新检查。")

    if progress:
        progress("修复完成", 100)
    return ok, fail, msgs


def _browser_running():
    for p in utils.list_processes():
        if p["name"] in ("msedge.exe", "chrome.exe", "360se.exe", "360chromex.exe"):
            return True
    return False


def _do_fix(it, batch):
    kind = it["kind"]
    d = it["data"]

    # ---------- 策略 ----------
    if kind == "policy":
        hive = utils.hive_from_name(d["hive"])
        batch.backup_reg_value(hive, d["path"], d["name"], "策略 " + d["name"])
        if reg_delete_value(hive, d["path"], d["name"]):
            return True, "策略已移除"
        return False, "移除失败（需要管理员权限）"

    # ---------- 快捷方式网址 ----------
    if kind == "shortcut_url":
        # .url 文件：备份后改成 about:blank 或删除
        p = d["path"]
        try:
            utils.backup_batch_file_copy(batch, p, "网址快捷方式")
            os.remove(p)
            return True, "已删除劫持用的网址快捷方式（已备份）"
        except Exception as e:
            return False, str(e)

    # ---------- 快捷方式参数 ----------
    if kind == "shortcut":
        p = d["path"]
        target = d["target"]
        args = d["args"]
        try:
            utils.backup_batch_file_copy(batch, p, "快捷方式 " + os.path.basename(p))
        except Exception as e:
            return False, "备份失败: %s" % e

        # 清掉网址和应用参数，保留合法参数
        keep = []
        for tok in args.split():
            tl = tok.lower()
            if re.match(r"^(https?://|www\.)", tl):
                continue
            if re.match(r"^--(app|startup-url|homepage)=", tl):
                continue
            if tl.startswith("--") or tl.startswith("-"):
                keep.append(tok)
        new_args = " ".join(keep)

        script = (
            "$s=New-Object -ComObject WScript.Shell;"
            "$l=$s.CreateShortcut('%s');"
            "$l.TargetPath='%s';"
            "$l.Arguments='%s';"
            "$l.Save()"
            % (p.replace("'", "''"), target.replace("'", "''"),
               new_args.replace("'", "''"))
        )
        code, out = utils.run_ps(script, timeout=25)
        if code == 0:
            return True, ("参数已清空" if not new_args else "已清理劫持参数，保留：%s" % new_args)
        return False, "修改快捷方式失败: %s" % out.strip()[:100]

    # ---------- 配置文件 ----------
    if kind == "pref":
        f = d["file"]
        field = d["field"]
        try:
            utils.backup_batch_file_copy(batch, f, "浏览器配置")
        except Exception as e:
            return False, "备份失败: %s" % e
        try:
            with open(f, encoding="utf-8", errors="ignore") as fp:
                data = json.load(fp)
        except Exception as e:
            return False, "读取配置失败: %s" % e

        if field == "session.startup_urls":
            sess = data.setdefault("session", {})
            sess["startup_urls"] = []
            sess["restore_on_startup"] = 5   # 5 = 打开新标签页
            msg = "启动页已重置为新标签页"
        elif field == "homepage":
            data["homepage"] = "https://www.bing.com/"
            data["homepage_is_newtabpage"] = True
            msg = "主页已重置"
        elif field == "browser.new_tab_page_location":
            br = data.get("browser") or {}
            br.pop("new_tab_page_location", None)
            data["browser"] = br
            msg = "新标签页设置已清除"
        elif field == "default_search_provider_data":
            data.pop("default_search_provider_data", None)
            data.pop("default_search_provider", None)
            msg = "默认搜索已重置（重启浏览器后生效）"
        else:
            msg = "已处理"

        try:
            tmp = f + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=False)
            shutil.move(tmp, f)
        except Exception as e:
            return False, "写入配置失败（浏览器可能正在运行）: %s" % e
        return True, msg

    # ---------- 文件关联 ----------
    if kind == "assoc":
        key = d["path"]
        batch.backup_reg(HKCR, key, "文件关联 " + key)
        # 恢复为系统默认
        default = '"%s"' % os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe")
        if not os.path.exists(default.strip('"')):
            default = '"%s"' % os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe")
        if not os.path.exists(default.strip('"')):
            default = '"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"'
        try:
            with winreg.OpenKey(HKCR, key, 0, winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, default + " %1")
            return True, "已恢复为 Edge 默认打开"
        except Exception as e:
            return False, str(e)

    if kind == "assoc_value":
        path = d["path"]
        batch.backup_reg_value(HKCR, path, "", "关联 " + path)
        try:
            with winreg.OpenKey(HKCR, path, 0, winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "MSEdgeHTM")
            return True, "已恢复为 Edge 打开"
        except Exception as e:
            return False, str(e)

    # ---------- 扩展目录 ----------
    if kind == "extdir":
        p = d["path"]
        if not os.path.exists(p):
            return True, "扩展已不存在"
        if utils.is_protected(p):
            return False, "属于保护路径，已跳过"
        ok, msg = batch.quarantine(p, it["name"])
        return (True, "扩展已移入隔离区（可还原）") if ok else (False, msg)

    # ---------- 默认浏览器 ----------
    if kind == "default_browser":
        if open_default_apps_settings():
            return True, "已打开系统设置，请在列表里选择 Edge"
        return False, "打开设置失败，请手动进 设置 → 应用 → 默认应用 修改"

    return False, "未知类型"


# ============================================================
# v2: 彻底恢复原始浏览器
# ============================================================
def full_reset(batch, progress=None):
    """
    把 Edge / Chrome 恢复到出厂状态：
      1. 组策略键整个删掉（含 Recommended / Forcelist）
      2. 所有快捷方式的劫持参数清空、.url 劫持文件删除
      3. 所有 profile 的 Preferences 重置：启动页/主页/新标签页/默认搜索
      4. http/https/html 文件关联恢复为 Edge
    全程先备份。返回 (成功数, 失败数, 消息列表)
    """
    ok = fail = 0
    msgs = []

    def step(msg, pct):
        if progress:
            progress(msg, pct)

    # ---- 1. 组策略 ----
    step("清除浏览器组策略…", 5)
    for hive, path, label in POLICY_TARGETS:
        if not utils.reg_key_exists(hive, path):
            continue
        if batch.backup_reg(hive, path, label):
            if utils.reg_delete_tree(hive, path):
                ok += 1
                msgs.append("✓ %s — 组策略已整体删除" % label)
            else:
                fail += 1
                msgs.append("✗ %s — 删除失败（需要管理员权限）" % label)
        else:
            fail += 1
            msgs.append("✗ %s — 备份失败，已跳过（安全保护）" % label)
    # Forcelist 单独也删一遍（父键删了子键自然没了，但单独列一遍更直观）
    step("清除强制安装的扩展策略…", 25)
    for hive, path, label in [(HKLM, r"SOFTWARE\Policies\Microsoft\Edge\ExtensionInstallForcelist", "Edge 强制扩展"),
                              (HKCU, r"SOFTWARE\Policies\Microsoft\Edge\ExtensionInstallForcelist", "Edge 强制扩展(用户)"),
                              (HKLM, r"SOFTWARE\Policies\Google\Chrome\ExtensionInstallForcelist", "Chrome 强制扩展"),
                              (HKCU, r"SOFTWARE\Policies\Google\Chrome\ExtensionInstallForcelist", "Chrome 强制扩展(用户)")]:
        if utils.reg_key_exists(hive, path):
            if batch.backup_reg(hive, path, label) and utils.reg_delete_tree(hive, path):
                ok += 1
                msgs.append("✓ %s — 已删除" % label)

    # ---- 2. 快捷方式 ----
    step("清理快捷方式劫持参数…", 40)
    sc_items = _scan_shortcuts()
    for it in sc_items:
        try:
            r, m = _do_fix(it, batch)
        except Exception as e:
            r, m = False, str(e)
        if r:
            ok += 1
            msgs.append("✓ 快捷方式 %s — 已清理" % os.path.basename(it["target"]))
        else:
            fail += 1
            msgs.append("✗ 快捷方式 %s — %s" % (os.path.basename(it["target"]), m))
    if not sc_items:
        msgs.append("✓ 快捷方式检查完毕，没有劫持")

    # ---- 3. Preferences 全量重置 ----
    step("重置浏览器配置（主页/启动页/搜索）…", 60)
    for ud in edge_user_data_dirs():
        browser = "Edge" if "Edge" in ud else "Chrome"
        for prof_dir in glob.glob(os.path.join(ud, "*")):
            pref = os.path.join(prof_dir, "Preferences")
            if not os.path.exists(pref):
                continue
            base = os.path.basename(prof_dir)
            try:
                utils.backup_batch_file_copy(batch, pref, "%s 配置 %s" % (browser, base))
                with open(pref, encoding="utf-8", errors="ignore") as fp:
                    data = json.load(fp)
                changed = []
                sess = data.setdefault("session", {})
                if sess.get("startup_urls") or sess.get("restore_on_startup") not in (1, 5, None):
                    sess["startup_urls"] = []
                    sess["restore_on_startup"] = 5
                    changed.append("启动页")
                if data.get("homepage") or data.get("homepage_is_newtabpage") is False:
                    data.pop("homepage", None)
                    data["homepage_is_newtabpage"] = True
                    changed.append("主页")
                br = data.get("browser") or {}
                if br.pop("new_tab_page_location", None):
                    data["browser"] = br
                    changed.append("新标签页")
                if data.pop("default_search_provider_data", None) is not None or \
                   data.pop("default_search_provider", None) is not None:
                    changed.append("默认搜索")
                if not changed:
                    msgs.append("✓ %s[%s] — 配置本来就是干净的" % (browser, base))
                    continue
                tmp = pref + ".tmp"
                with open(tmp, "w", encoding="utf-8") as fp:
                    json.dump(data, fp, ensure_ascii=False)
                shutil.move(tmp, pref)
                ok += 1
                msgs.append("✓ %s[%s] — 已重置：%s" % (browser, base, "、".join(changed)))
            except Exception as e:
                fail += 1
                msgs.append("✗ %s[%s] — %s（浏览器可能在运行）" % (browser, base, e))

    # ---- 4. 文件关联 ----
    step("恢复文件关联…", 85)
    for it in _scan_associations():
        try:
            r, m = _do_fix(it, batch)
        except Exception as e:
            r, m = False, str(e)
        if r:
            ok += 1
            msgs.append("✓ %s — %s" % (it["name"], m))
        else:
            fail += 1
            msgs.append("✗ %s — %s" % (it["name"], m))
    if not _scan_associations():
        msgs.append("✓ 文件关联检查完毕，没有被接管")

    # ---- 5. 高风险扩展 ----
    step("清理可疑扩展…", 92)
    try:
        exts = [i for i in _scan_extensions() if i["level"] == "high"]
    except Exception:
        exts = []
    for it in exts:
        try:
            r, m = _do_fix(it, batch)
        except Exception as e:
            r, m = False, str(e)
        if r:
            ok += 1
            msgs.append("✓ 扩展 %s — 已隔离（可还原）" % it["name"])
        else:
            fail += 1
            msgs.append("✗ 扩展 %s — %s" % (it["name"], m))
    if not exts:
        msgs.append("✓ 没有发现可疑扩展")

    # ---- 6. 默认浏览器（只能引导，不能硬改） ----
    label, bad, prog = current_default_browser()
    if bad:
        msgs.append("⚠ 默认浏览器仍然是「%s」。这个设置有系统哈希保护，工具改不了，"
                    "请点「打开默认应用设置」手动改回 Edge。" % label)

    step("完成", 100)
    return ok, fail, msgs
