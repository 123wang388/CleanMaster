# -*- coding: utf-8 -*-
"""
已安装软件盘点 + 流氓/捆绑软件识别

数据源：注册表 Uninstall 三处 + UWP 应用
识别：关键词打分模型，每条命中都给理由，不黑盒
"""
import os
import re
import json
import winreg

from core import utils
from core.rules import (VENDOR_RULES, NAME_RULES, WHITELIST_VENDORS,
                        WHITELIST_NAMES, SUSPICIOUS_INSTALL_PATHS)
from core.utils import reg_list_subkeys, reg_read_value

HKLM = winreg.HKEY_LOCAL_MACHINE
HKCU = winreg.HKEY_CURRENT_USER

UNINSTALL_KEYS = [
    (HKLM, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", "系统(64位)"),
    (HKLM, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall", "系统(32位)"),
    (HKCU, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", "当前用户"),
]


# ============================================================
# 枚举
# ============================================================
def list_installed(progress=None):
    """返回所有已安装软件（已去重）"""
    out = []
    seen = set()

    for hive, base, scope in UNINSTALL_KEYS:
        subs = reg_list_subkeys(hive, base)
        for i, sub in enumerate(subs):
            if progress and i % 20 == 0:
                progress("读取软件列表 %d/%d" % (i + 1, len(subs)), None)
            p = base + "\\" + sub
            name = reg_read_value(hive, p, "DisplayName")
            if not name:
                continue
            name = str(name).strip()
            if not name:
                continue

            # 跳过系统补丁/组件
            try:
                syscomp = reg_read_value(hive, p, "SystemComponent")
                if syscomp == 1:
                    continue
            except Exception:
                pass
            release = str(reg_read_value(hive, p, "ReleaseType") or "")
            parent = reg_read_value(hive, p, "ParentKeyName")
            if parent:
                continue
            if release.upper() in ("SECURITY UPDATE", "UPDATE", "HOTFIX"):
                continue
            if name.startswith("KB") and re.match(r"^KB\d{6,}", name):
                continue
            if name.startswith("{") and name.endswith("}"):
                continue

            uninst = str(reg_read_value(hive, p, "UninstallString") or "")
            quiet = str(reg_read_value(hive, p, "QuietUninstallString") or "")
            version = str(reg_read_value(hive, p, "DisplayVersion") or "")
            publisher = str(reg_read_value(hive, p, "Publisher") or "")
            location = str(reg_read_value(hive, p, "InstallLocation") or "")
            icon = str(reg_read_value(hive, p, "DisplayIcon") or "")
            date = str(reg_read_value(hive, p, "InstallDate") or "")
            size_kb = reg_read_value(hive, p, "EstimatedSize") or 0

            key = name.lower() + "|" + version.lower()
            if key in seen:
                continue
            seen.add(key)

            s = {
                "name": name,
                "version": version,
                "publisher": publisher,
                "location": location,
                "uninstall": uninst,
                "quiet_uninstall": quiet,
                "icon": icon,
                "date": date,
                "size": int(size_kb) * 1024 if isinstance(size_kb, int) else 0,
                "scope": scope,
                "reg_path": "%s\\%s" % (utils.reg_path_str(hive, base), sub),
                "hive": utils.HIVE_NAMES[hive],
                "key": sub,
                "type": "win32",
            }
            s.update(evaluate(s))
            out.append(s)

    # UWP
    try:
        out.extend(_list_uwp())
    except Exception as e:
        utils.log("UWP 枚举失败: %s" % e, "WARN")

    out.sort(key=lambda x: (-x["score"], x["name"].lower()))
    return out


def _list_uwp():
    out = []
    code, txt = utils.run_ps(
        "Get-AppxPackage | Where-Object {$_.IsFramework -eq $false} | "
        "Select-Object Name,PackageFullName,PublisherDisplayName,Version,InstallLocation | "
        "ConvertTo-Json -Compress", timeout=60)
    if code != 0 or not txt.strip().startswith("["):
        return out
    try:
        data = json.loads(txt)
    except Exception:
        return out
    for a in data:
        name = a.get("Name") or ""
        pub = a.get("PublisherDisplayName") or ""
        s = {
            "name": name,
            "version": str(a.get("Version") or ""),
            "publisher": pub,
            "location": a.get("InstallLocation") or "",
            "uninstall": "",
            "quiet_uninstall": "",
            "icon": "",
            "date": "",
            "size": 0,
            "scope": "应用商店",
            "reg_path": a.get("PackageFullName") or "",
            "hive": "UWP",
            "key": a.get("PackageFullName") or "",
            "type": "uwp",
        }
        s.update(evaluate(s))
        out.append(s)
    return out


# ============================================================
# 打分
# ============================================================
def evaluate(s):
    """
    返回 {'score': 0-100, 'level': high/mid/low/trusted, 'reasons': [...]}
    原则：宁可漏判也不误伤——把正常软件标成流氓，比漏掉一个更让人不信任工具。
    """
    name = s.get("name", "") or ""
    pub = s.get("publisher", "") or ""
    loc = s.get("location", "") or ""
    uninst = s.get("uninstall", "") or ""
    is_uwp = s.get("type") == "uwp"
    name_low = name.lower()
    pub_low = pub.lower()

    # --- 0. 无意义的名字（纯 GUID / 纯数字ID），不参与评分 ---
    if re.match(r"^\{?[0-9A-Fa-f]{8}[-0-9A-Fa-f]{4,}[-0-9A-Fa-f]*\}?$", name) or \
       re.match(r"^[0-9A-Fa-f\-]{24,}$", name):
        return {"score": 0, "level": "low",
                "reasons": ["名称是系统标识符，无参考意义"], "tags": []}

    # --- 1. 微软自家应用 ---
    if is_uwp and name_low.startswith("microsoft."):
        return {"score": 0, "level": "trusted",
                "reasons": ["Microsoft 官方应用"], "tags": ["可信"]}
    if name_low.startswith("microsoft ") or name_low.startswith("windows "):
        return {"score": 0, "level": "trusted",
                "reasons": ["Microsoft 官方组件"], "tags": ["可信"]}

    # --- 2. 厂商白名单 ---
    for w in WHITELIST_VENDORS:
        if w in pub_low:
            return {"score": 0, "level": "trusted",
                    "reasons": ["正规厂商：%s" % pub], "tags": ["可信"]}
    for w in WHITELIST_NAMES:
        if w in name_low:
            return {"score": 0, "level": "trusted",
                    "reasons": ["已知正规软件"], "tags": ["可信"]}

    score = 0
    reasons = []
    tag_set = set()

    # --- 3. 厂商规则（看名称 + 发布者 + 安装路径）---
    vendor_text = ("%s %s" % (name, pub)).lower()
    for kws, pts, vendor in VENDOR_RULES:
        if any(k in vendor_text for k in kws):
            score += pts
            reasons.append("厂商特征：%s (+%d)" % (vendor, pts))
            tag_set.add(vendor)
            break

    # --- 4. 名称规则 ---
    for kws, pts, label in NAME_RULES:
        if any(k in name_low for k in kws):
            score += pts
            reasons.append("%s (+%d)" % (label, pts))
            tag_set.add(label)

    # --- 5. 风险特征 ---
    if not uninst and not is_uwp:
        score += 18
        reasons.append("没有注册卸载程序 (+18)")
        tag_set.add("无卸载入口")

    if loc:
        ll = loc.lower().replace("/", "\\")
        for sp in SUSPICIOUS_INSTALL_PATHS:
            if sp in ll:
                score += 16
                reasons.append("装在临时/隐蔽目录 (+16)")
                tag_set.add("隐蔽安装")
                break

    if not pub.strip() and not is_uwp:
        score += 6
        reasons.append("没有发布者信息 (+6)")

    if len(name) > 48 and not is_uwp:
        score += 6
        reasons.append("名称异常冗长 (+6)")

    score = max(0, min(100, score))

    if score >= 58:
        level = "high"
        tag_set.add("建议卸载")
    elif score >= 36:
        level = "mid"
        tag_set.add("建议检查")
    else:
        level = "low"

    return {"score": score, "level": level,
            "reasons": reasons or ["未命中风险特征"],
            "tags": sorted(tag_set)}


# ============================================================
# 附加信息：签名 / 是否运行中
# ============================================================
def check_signatures(softs, limit=120):
    """
    批量检查数字签名。只对 score>=25 的做，避免太慢。
    返回 {name: 'signed'|'unsigned'|'unknown'}
    """
    targets = [s for s in softs if s["score"] >= 25 and s.get("icon")][:limit]
    paths = []
    for s in targets:
        p = _exe_from_icon(s.get("icon", ""))
        if p and os.path.exists(p):
            paths.append((s["name"], p))
    if not paths:
        return {}
    result = {}
    # 分批，每批 25 个
    for i in range(0, len(paths), 25):
        chunk = paths[i:i + 25]
        script = "& {" + ";".join(
            "$r=Get-AuthenticodeSignature -LiteralPath '%s' -ErrorAction SilentlyContinue;"
            "if($r -and $r.Status -eq 'Valid'){'%s|OK'}else{'%s|NO'}"
            % (p.replace("'", "''"), n.replace("'", "''"), n.replace("'", "''"))
            for n, p in chunk) + "}"
        code, out = utils.run_ps(script, timeout=90)
        for line in out.splitlines():
            line = line.strip()
            if "|" in line:
                n, v = line.rsplit("|", 1)
                result[n] = "signed" if v == "OK" else "unsigned"
    return result


def _exe_from_icon(icon):
    if not icon:
        return ""
    p = icon.strip().strip('"')
    if "," in p and p.lower().endswith(".exe"): 
        p = p.split(",")[0]
    m = re.match(r"^(.+?\.exe)", p, re.I)
    if m:
        p = m.group(1)
    p = os.path.expandvars(p)
    return p


# ============================================================
# 卸载
# ============================================================
def build_uninstall_cmd(s):
    """把注册表里的卸载串转成可执行命令"""
    q = (s.get("quiet_uninstall") or "").strip()
    u = (s.get("uninstall") or "").strip()
    cmd = q or u
    if not cmd:
        return ""

    low = cmd.lower()
    # MsiExec /I{GUID} → /X{GUID}
    if "msiexec" in low:
        cmd = re.sub(r"/I(\{)", r"/X\1", cmd, flags=re.I)
        if " /x" not in cmd.lower():
            m = re.search(r"\{[0-9A-Fa-f\-]{36}\}", cmd)
            if m:
                cmd = "msiexec.exe /x %s /qn" % m.group(0)
        return cmd
    return cmd


def run_uninstall(s, wait=False):
    """执行卸载，返回 (成功, 信息)"""
    if s.get("type") == "uwp":
        pkg = s.get("key", "")
        code, out = utils.run_ps(
            "Remove-AppxPackage -Package '%s' -ErrorAction Stop" % pkg.replace("'", "''"),
            timeout=180)
        return code == 0, out.strip()[:200]

    cmd = build_uninstall_cmd(s)
    if not cmd:
        return False, "该软件没有提供卸载命令，需要手动处理"

    utils.log("执行卸载: %s -> %s" % (s["name"], cmd))
    try:
        if wait:
            import subprocess
            p = subprocess.run(cmd, shell=True, timeout=600,
                               creationflags=0x08000000,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            return p.returncode == 0, (p.stdout or b"").decode("gbk", "ignore")[:300]
        # 交互式：直接拉起让用户自己点
        import subprocess
        subprocess.Popen(cmd, shell=True, creationflags=0x00000010)
        return True, "已启动卸载程序，请在弹出的窗口中完成卸载"
    except Exception as e:
        return False, str(e)


# ============================================================
# 关联：谁在开机自启
# ============================================================
def startup_map():
    """返回 {小写关键词: [启动项名]}，用于给软件标注是否自启"""
    m = {}
    keys = [
        (HKCU, r"Software\Microsoft\Windows\CurrentVersion\Run"),
        (HKLM, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
        (HKLM, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"),
    ]
    from core.utils import reg_list_values
    for hive, key in keys:
        for name, val, _ in reg_list_values(hive, key):
            m.setdefault(str(name).lower(), []).append(str(val))
    return m


# ============================================================
# v2: 卸载后残留追踪 —— 目录 / 注册表 / 启动项 / 服务 / 计划任务 / 快捷方式
# ============================================================

STOP_TOKENS = {
    "the", "for", "and", "soft", "software", "setup", "install", "installer",
    "manager", "player", "free", "pro", "plus", "bin", "x64", "x86", "windows",
    "microsoft", "update", "version", "edition", "client", "service", "tool",
    "app", "desktop", "system", "center", "studio", "suite", "premium",
    "lite", "express", "basic", "home", "enterprise", "driver", "runtime",
    "library", "package", "common", "shared", "helper", "agent", "core",
    # 下面这些太通用，一匹配就是一堆误报
    "build", "builder", "visual", "live", "mate", "shell", "game", "gaming",
    "editor", "view", "viewer", "control", "audio", "video", "photo", "music",
    "cloud", "drive", "box", "hub", "link", "pass", "safe", "guard", "care",
    "clean", "fast", "quick", "smart", "easy", "super", "micro", "macro",
    "data", "file", "folder", "note", "word", "excel", "power", "point",
    "browser", "reader", "writer", "maker", "creator", "master", "protable",
    "series", "family", "group", "team", "work", "works", "workspace",
}

ZH_GENERIC = ("官方版", "免费版", "专业版", "中文版", "最新版", "增强版",
              "精简版", "旗舰版", "企业版", "个人版", "正式版")

# 这些目录名没有辨识度，不能当作软件特征
ZH_DIR_GENERIC = {"新建文件夹", "程序", "软件", "工具", "文件", "桌面", "下载",
                  "文档", "应用", "程序文件", "应用程序", "临时文件", "未命名",
                  "我的文档", "本地磁盘", "用户"}

# 游戏/平台目录：里面的东西删了会影响游戏
GAME_PLATFORM_HINTS = (
    "\\steam\\", "\\steamapps\\", "\\epic games\\", "\\tencent games\\",
    "\\wegame\\", "\\battle.net\\", "\\riot games\\", "\\ubisoft\\",
    "\\origin games\\", "\\ea games\\", "\\gog galaxy\\", "\\xboxgames\\",
    "\\microsoft games\\", "\\blizzard\\",
)


def _in_game_dir(p):
    pl = (p or "").lower()
    return any(h in pl for h in GAME_PLATFORM_HINTS)

# 注册表一级键里这些是系统区，不往里深挖
REG_SAFE_ROOTS = {
    "microsoft", "windows", "policies", "classes", "clients", "registeredapplications",
    "wow6432node", "system", "scheme", "internet explorer", "google", "mozilla",
}


def _name_tokens(s):
    """从软件名/发布者/安装目录里提取可匹配的关键词（中英文都支持）"""
    name = s.get("name", "") or ""
    name = re.sub(r"[（(\[].*?[)）\]]", " ", name)
    name = re.sub(r"\bv?\d+(\.\d+)+\b", " ", name)

    toks = set()

    for t in re.findall(r"[A-Za-z][A-Za-z0-9_\-]{2,}", name):
        if t.lower() not in STOP_TOKENS:
            toks.add(t)

    for z in re.findall(r"[\u4e00-\u9fa5]{2,10}", name):
        for g in ZH_GENERIC:
            z = z.replace(g, "")
        z = z.strip()
        if len(z) >= 2 and z not in ZH_GENERIC:
            toks.add(z)

    pub = s.get("publisher", "") or ""
    for t in re.findall(r"[A-Za-z][A-Za-z0-9_\-]{2,}", pub):
        if t.lower() not in STOP_TOKENS and t.lower() not in ("corp", "ltd", "inc",
                                                             "co", "limited", "gmbh"):
            toks.add(t)

    loc = (s.get("location") or "").strip().rstrip("\\/")
    if loc:
        b = os.path.basename(loc)
        if (len(b) >= 3 and b.lower() not in STOP_TOKENS
                and b not in ZH_DIR_GENERIC
                and not re.match(r"^(新建|未命名|副本|copy)", b, re.I)):
            toks.add(b)

    return sorted(toks)


def _match(text, toks):
    """命中返回对应 token，否则 None。英文要求 >=4 字符，避免 build/builder 这类误伤"""
    if not text:
        return None
    for t in toks:
        if t.isascii():
            if len(t) >= 4 and t.lower() in text.lower():
                return t
        else:
            if len(t) >= 2 and t in text:
                return t
    return None


def _match_strict(text, toks):
    """
    严格匹配，用于服务和注册表 —— 必须整词边界或从头开始。
    AudioEndpointBuilder 不会被 Token "Build" 命中。
    """
    if not text:
        return None
    tl = text.lower()
    for t in toks:
        if t.isascii():
            tl2 = t.lower()
            if len(tl2) < 4:
                continue
            if tl.startswith(tl2):
                return t
            if re.search(r"(^|[^a-z0-9])" + re.escape(tl2) + r"([^a-z0-9]|$)", tl):
                return t
    return None


def _dir_roots():
    roots = []
    for key in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA",
                "APPDATA", "PROGRAMDATA"):
        v = os.environ.get(key)
        if v and os.path.isdir(v):
            roots.append(v)
    la = os.environ.get("LOCALAPPDATA", "")
    if la:
        p = os.path.join(la, "Programs")
        if os.path.isdir(p):
            roots.append(p)
    # 其它盘上的 Program Files
    for d in utils.get_drives():
        for sub in ("Program Files", "Program Files (x86)", "Programs", "软件"):
            p = os.path.join(d[0] + "\\", sub)
            if os.path.isdir(p) and p not in roots:
                roots.append(p)
    return list(dict.fromkeys(roots))


RUN_KEYS = [
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"),
]

# 系统核心服务，除非 exe 明确在目标软件目录下，否则绝不列为残留
SYSTEM_SERVICE_PREFIX = (
    "audio", "rpc", "dcom", "plugplay", "power", "themes", "eventlog",
    "dhcp", "dnscache", "lanman", "wsearch", "appshell", "wpn", "storsvc",
    "wuauserv", "bits", "cryptsvc", "trustedinstaller", "winmgmt",
    "schedule", "seclogon", "spooler", "windefend", "mpssvc", "bfe",
    "nsi", "netprofm", "nlasvc", "iphlpsvc", "dhcpc", "wscsvc", "sysmain",
    "sppsvc", "usosvc", "wlan", "wlansvc", "dot3", "tapisrv", "rasman",
    "termservice", "sessionenv", "umrdp", "wecsvc", "vss", "swprv",
    "deviceinstall", "devicesetup", "dps", "diagtrack", "gpsvc",
    "broker", "cbdhsvc", "cdpusersvc", "wpnuserservice", "shellhwdetection",
)


def _is_system_service(name):
    nl = (name or "").lower()
    return any(nl.startswith(p) for p in SYSTEM_SERVICE_PREFIX)


def find_traces(s, progress=None):
    """
    扫描某个软件在系统里留下的所有痕迹（卸载前后都能用）。
    返回 [{'kind','label','detail','target','data','default'}]
    kind: dir / reg / run / service / task / shortcut
    """
    items = []
    toks = _name_tokens(s)
    if not toks:
        return items

    loc = (s.get("location") or "").strip().rstrip("\\/")
    loc_low = loc.lower()

    def step(msg):
        if progress:
            progress(msg, None)

    # ---------- 1. 目录 ----------
    step("扫描安装目录与数据目录…")
    cand = set()
    for p in (loc, os.path.dirname(_exe_from_icon(s.get("icon", "")) or "")):
        if p and os.path.isdir(p):
            cand.add(os.path.normpath(p))

    for root in _dir_roots():
        try:
            entries = os.listdir(root)
        except Exception:
            continue
        for d in entries:
            full = os.path.join(root, d)
            if not os.path.isdir(full):
                continue
            if _match(d, toks):
                cand.add(os.path.normpath(full))

    for d in sorted(cand):
        if not os.path.exists(d) or utils.is_protected(d):
            continue
        sz = utils.dir_size(d, max_seconds=4)
        # 在游戏/平台目录里、又不是它自己的安装目录 → 不默认勾选
        game = _in_game_dir(d) and not (loc and d.lower().startswith(loc.lower()))
        items.append({
            "kind": "dir",
            "label": "目录 " + d,
            "detail": "占用 %s%s" % (
                utils.human_size(sz),
                "；位于游戏/平台目录内，删除可能影响游戏" if game else ""),
            "target": d,
            "data": {"path": d, "size": sz},
            "default": not game,
        })

    # ---------- 2. 注册表 ----------
    step("扫描注册表…")
    reg_targets = []

    for hive, base in [(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE"),
                       (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node"),
                       (winreg.HKEY_CURRENT_USER, r"SOFTWARE")]:
        for sub in utils.reg_list_subkeys(hive, base):
            if _match(sub, toks):
                reg_targets.append((hive, base + "\\" + sub, sub))
                continue
            # 再深一层：厂商\产品
            if sub.lower() in REG_SAFE_ROOTS:
                continue
            vend = base + "\\" + sub
            for sub2 in utils.reg_list_subkeys(hive, vend):
                if _match(sub2, toks):
                    reg_targets.append((hive, vend + "\\" + sub2, sub2))

    # 卸载登记项本身
    up = s.get("reg_path", "")
    if up:
        hive_str, _, sub = up.partition("\\")
        if hive_str in ("HKLM", "HKCU") and sub and \
           utils.reg_key_exists(utils.hive_from_name(hive_str), sub):
            reg_targets.append((utils.hive_from_name(hive_str), sub,
                                "卸载登记项"))

    seen_reg = set()
    for hive, path, label in reg_targets:
        key = (utils.HIVE_NAMES.get(hive, "HKLM"), path.lower())
        if key in seen_reg:
            continue
        seen_reg.add(key)
        up_ = path.upper()
        if "\\MICROSOFT\\WINDOWS\\CURRENTVERSION" in up_:
            continue
        items.append({
            "kind": "reg",
            "label": "注册表 %s\\%s" % (utils.HIVE_NAMES.get(hive, "HKLM"), path),
            "detail": "配置项：%s" % label,
            "target": path,
            "data": {"hive": utils.HIVE_NAMES.get(hive, "HKLM"), "path": path},
            "default": True,
        })

    # ---------- 3. 开机自启 ----------
    step("扫描开机自启项…")
    for hive, key in RUN_KEYS:
        for name, val, _ in utils.reg_list_values(hive, key):
            sv = str(val)
            hit = _match(name, toks)
            if not hit and loc_low and loc_low in sv.lower():
                hit = "安装路径"
            if not hit:
                continue
            items.append({
                "kind": "run",
                "label": "自启项 " + str(name),
                "detail": "命令：%s" % sv[:150],
                "target": "%s\\%s" % (utils.reg_path_str(hive, key), name),
                "data": {"hive": utils.HIVE_NAMES[hive], "path": key,
                         "name": str(name)},
                "default": True,
            })

    # ---------- 4. 服务 ----------
    step("扫描关联服务…")
    try:
        for svc in utils.list_services():
            img = (svc.get("image") or "").lower()
            path_hit = bool(loc_low) and loc_low in img
            hit = _match_strict(svc["name"], toks) or \
                _match_strict(svc["display"], toks)
            # 系统核心服务一律不碰，除非它的 exe 确实在该软件目录下
            if not path_hit and _is_system_service(svc["name"]):
                continue
            if not hit and not path_hit:
                continue
            items.append({
                "kind": "service",
                "label": "服务 " + svc["name"],
                "detail": "%s\n路径：%s" % (svc.get("display", ""), img[:140]),
                "target": svc["name"],
                "data": {"service": svc["name"], "image": img},
                "default": True,
            })
    except Exception as e:
        utils.log("扫描服务失败: %s" % e, "WARN")

    # ---------- 5. 计划任务 ----------
    step("扫描计划任务…")
    try:
        for t in utils.list_tasks():
            if not _match(t["name"], toks):
                continue
            items.append({
                "kind": "task",
                "label": "计划任务 " + t["name"],
                "detail": "%s%s" % (t["path"], t["name"]),
                "target": (t["path"] or "\\") + t["name"],
                "data": {"path": t["path"], "name": t["name"]},
                "default": True,
            })
    except Exception as e:
        utils.log("扫描计划任务失败: %s" % e, "WARN")

    # ---------- 6. 快捷方式 ----------
    step("扫描快捷方式…")
    la = os.environ.get("APPDATA", "")
    pd = os.environ.get("PROGRAMDATA", "")
    uprof = os.environ.get("USERPROFILE", "")
    pub = os.environ.get("PUBLIC", r"C://Users//Public")
    sm_dirs = [
        os.path.join(la, r"Microsoft\Windows\Start Menu\Programs"),
        os.path.join(pd, r"Microsoft\Windows\Start Menu\Programs"),
        os.path.join(uprof, "Desktop"),
        os.path.join(pub, "Desktop"),
    ]
    name_full = (s.get("name") or "").lower()
    for d in sm_dirs:
        if not os.path.isdir(d):
            continue
        for root, _dirs, files in os.walk(d):
            for f in files:
                if not f.lower().endswith((".lnk", ".url")):
                    continue
                stem = os.path.splitext(f)[0]
                sl = stem.lower()
                ok = bool(_match(stem, toks))
                if not ok and name_full and (name_full in sl or sl in name_full):
                    ok = True
                if not ok:
                    continue
                fp = os.path.join(root, f)
                items.append({
                    "kind": "shortcut",
                    "label": "快捷方式 " + f,
                    "detail": os.path.dirname(fp),
                    "target": fp,
                    "data": {"path": fp},
                    "default": True,
                })

    return items


def remove_traces(items, batch, progress=None):
    """清除痕迹：文件进隔离区，注册表/服务/任务先备份再删"""
    ok = fail = 0
    msgs = []
    total = len(items) or 1

    order = {"service": 0, "task": 1, "run": 2, "reg": 3,
             "shortcut": 4, "dir": 5}
    items = sorted(items, key=lambda x: order.get(x["kind"], 9))

    for i, it in enumerate(items):
        if progress:
            progress("清除：%s" % it["label"], int(i * 100 / total))
        try:
            o, m = _remove_one(it, batch)
        except Exception as e:
            o, m = False, str(e)
        if o:
            ok += 1
        else:
            fail += 1
        msgs.append("%s %s — %s" % ("✓" if o else "✗", it["label"], m))
        utils.log("清除痕迹 %s: %s (%s)" % (it["label"], m, "OK" if o else "FAIL"))

    if progress:
        progress("完成", 100)
    return ok, fail, msgs


def _remove_one(it, batch):
    kind = it["kind"]
    d = it.get("data") or {}

    if kind == "dir":
        p = d.get("path")
        if not os.path.exists(p):
            return True, "目录已不存在（卸载程序自己删掉了）"
        if utils.is_protected(p):
            return False, "系统保护路径，已跳过"
        o, m = batch.quarantine(p, it["label"])
        return (True, "已移入隔离区（可还原）") if o else (False, m)

    if kind in ("shortcut",):
        p = d.get("path")
        if not os.path.exists(p):
            return True, "已不存在"
        o, m = batch.quarantine(p, it["label"])
        return (True, "已移入隔离区") if o else (False, m)

    if kind == "reg":
        hive = utils.hive_from_name(d.get("hive", "HKLM"))
        path = d.get("path")
        if not utils.reg_key_exists(hive, path):
            return True, "注册表项已不存在"
        if not batch.backup_reg(hive, path, it["label"]):
            return False, "备份失败，已取消删除（安全保护）"
        o = utils.reg_delete_tree(hive, path)
        return (True, "注册表项已删除（可还原）") if o else (False, "删除失败，需要管理员权限")

    if kind == "run":
        hive = utils.hive_from_name(d.get("hive", "HKCU"))
        batch.backup_reg_value(hive, d["path"], d["name"], it["label"])
        o = utils.reg_delete_value(hive, d["path"], d["name"])
        return (True, "自启项已移除") if o else (False, "删除失败，需要管理员权限")

    if kind == "service":
        sn = d["service"]
        reg_p = r"SYSTEM\CurrentControlSet\Services\%s" % sn
        backed = batch.backup_reg(utils.hive_from_name("HKLM"), reg_p, it["label"]) \
            if utils.reg_key_exists(utils.hive_from_name("HKLM"), reg_p) else True
        utils.run_cmd(["sc", "stop", sn], timeout=15)
        code, out = utils.run_cmd(["sc", "delete", sn], timeout=20)
        if code == 0:
            return True, "服务已删除"
        # sc 被杀软拦了，退回注册表删
        if backed and utils.reg_delete_tree(utils.hive_from_name("HKLM"), reg_p):
            batch.note("服务 %s 已用注册表方式删除" % sn)
            return True, "服务已删除（注册表方式，重启后彻底清掉）"
        return False, "删除失败：%s" % (out.strip()[:80] or "需要管理员权限")

    if kind == "task":
        path, name = d.get("path"), d.get("name")
        code, out = utils.run_cmd(
            ["schtasks", "/Delete", "/TN", (path or "\\") + name, "/F"], timeout=25)
        if code == 0:
            return True, "计划任务已删除"
        code2, _ = utils.run_ps(
            "Unregister-ScheduledTask -TaskName '%s' -Confirm:$false -ErrorAction SilentlyContinue"
            % str(name).replace("'", "''"), timeout=30)
        if code2 == 0:
            return True, "计划任务已删除"
        return False, "删除失败：%s" % out.strip()[:80]

    return False, "未知类型"
