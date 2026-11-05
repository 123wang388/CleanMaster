# -*- coding: utf-8 -*-
"""
广告查杀：找出电脑上真正弹广告的东西

判定原则（很重要）：
  只认"明确的广告特征"，绝不把更新程序、正常服务当广告。
  宁可漏报，也不能让人误删系统组件。

真正会弹广告的地方：
  1. 浏览器通知授权 —— 现在网页弹窗广告的主要来源，占了大多数
  2. 计划任务里定时弹资讯/热点的任务
  3. 开机自启里的推广程序
  4. 弹窗进程本身
  5. Windows 自带的推荐/建议/锁屏广告
  6. hosts 劫持与购物导航快捷方式

所有清除动作先备份，可回滚。
"""
import os
import re
import json
import glob
import shutil
import winreg

from core import utils
from core.utils import reg_list_values, reg_list_subkeys, reg_read_value

HKLM = winreg.HKEY_LOCAL_MACHINE
HKCU = winreg.HKEY_CURRENT_USER

# ============================================================
# 特征库
# ============================================================

# 明确的广告关键词（出现在名称/路径里才算）
AD_STRICT = (
    "热点", "资讯", "快讯", "弹窗", "广告", "推广", "推送",
    "返利", "红包", "抽奖", "秒杀", "特价", "优惠券",
    "hotnews", "newslist", "adpopup", "adpush", "popnews",
    "newspush", "advert", "promotion", "adflash", "adshow",
)

# 已知会弹广告的组件（只放真正会弹的，不放 update / 升级）
AD_FAMILIES = [
    (("360news", "360快资讯", "快资讯", "360热点", "360桌面助手",
      "360壁纸", "360safe\\news", "360se\\news"), "360 资讯/弹窗组件"),
    (("2345news", "2345资讯", "2345导航", "2345影视"), "2345 资讯弹窗"),
    (("hao123", "hao.360.cn"), "hao123 导航"),
    (("kuaizip", "快压"), "快压弹窗"),
    (("toutiaonews", "今日头条新闻", "头条资讯", "头条推送"), "头条资讯弹窗"),
    (("dubanews", "毒霸资讯", "猎豹资讯", "金山资讯"), "金山资讯弹窗"),
    (("wpsnews", "wps推送", "wps热点", "wps资讯"), "WPS 资讯弹窗"),
    (("baidunews", "百度热点", "百度资讯"), "百度热点"),
    (("sohunews", "搜狐资讯"), "搜狐资讯"),
    (("ifengnews", "凤凰资讯"), "凤凰资讯"),
]

# 这些路径里的东西一律不碰（系统组件/大厂正规程序）
SAFE_HINTS = (
    "\\windows\\system32", "\\windows\\syswow64", "\\windowsapps",
    "\\microsoft\\", "\\google\\", "\\nvidia", "\\asus\\", "\\intel\\",
    "\\amd\\", "\\realtek", "\\apple\\", "\\adobe\\", "\\mozilla\\",
    "\\python", "\\nodejs", "\\steam", "\\valve", "\\jetbrains",
    "onedrive", "defender", "wemeet", "\\tencent\\qq", "wechat",
)

# 浏览器通知：这些站点属于正常用途，不列为可疑
TRUSTED_DOMAINS = (
    "google.com", "googleusercontent.com", "bing.com", "microsoft.com",
    "live.com", "office.com", "github.com", "youtube.com", "gmail.com",
    "outlook.com", "apple.com", "icloud.com", "qq.com", "weixin.qq.com",
    "wechat.com", "tencent.com", "taobao.com", "tmall.com", "jd.com",
    "alipay.com", "aliyun.com", "bilibili.com", "zhihu.com", "douban.com",
    "weibo.com", "163.com", "126.com", "baidu.com", "csdn.net",
    "stackoverflow.com", "notion.so", "figma.com", "slack.com",
    "discord.com", "telegram.org", "zoom.us", "feishu.cn", "dingtalk.com",
    "npmjs.com", "pypi.org", "cloudflare.com", "amazonaws.com",
)

# 一眼就像广告站的域名特征
AD_DOMAIN_HINTS = (
    ".top", ".xyz", ".cc", ".buzz", ".click", ".link", ".online",
    "ad.", "ads.", "push.", "news.", "hot.", "banner.", "pop.",
    "advert", "promotion", "click", "popup", "spam",
)

# Windows 自带推荐/广告开关
WIN_AD_SWITCHES = [
    ("SubscribedContent-310093Enabled", "锁屏界面推荐广告", True),
    ("SubscribedContent-338388Enabled", "开始菜单推荐内容", True),
    ("SubscribedContent-338389Enabled", "设置页推荐内容", True),
    ("SubscribedContent-338393Enabled", "开始菜单应用建议", True),
    ("SubscribedContent-353694Enabled", "Windows 欢迎体验推送", True),
    ("SubscribedContent-353696Enabled", "Windows 使用技巧推送", True),
    ("SilentInstalledAppsEnabled", "静默安装推荐应用", True),
    ("SoftLandingEnabled", "Windows 提示气泡", True),
    ("RotatingLockScreenOverlayEnabled", "锁屏聚焦广告", True),
    ("ContentDeliveryAllowed", "内容分发总开关", True),
    ("OemPreInstalledAppsEnabled", "厂商预装应用推荐", True),
    ("PreInstalledAppsEnabled", "预装应用推荐", True),
]
WIN_AD_KEY = r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"


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
        # 默认是否勾选：高风险默认勾，也可以显式指定
        "default_checked": (level == "high") if default is None else bool(default),
    }


def _safe_path(p):
    pl = (p or "").lower()
    return any(s in pl for s in SAFE_HINTS)


def _strict_hit(text):
    tl = (text or "").lower()
    for k in AD_STRICT:
        if k in tl:
            return k
    return None


def _family_hit(text):
    tl = (text or "").lower()
    for kws, desc in AD_FAMILIES:
        for k in kws:
            if k in tl:
                return desc, k
    return None


def _domain_of(pattern):
    """从 chrome 通知权限的 pattern 里取出域名"""
    m = re.match(r"^https?://([^/:,]+)", pattern or "")
    return m.group(1).lower() if m else ""


def _is_trusted_domain(d):
    return any(d == t or d.endswith("." + t) for t in TRUSTED_DOMAINS)


def _looks_like_ad_domain(d):
    for h in AD_DOMAIN_HINTS:
        if h in d:
            return h
    return None


# ============================================================
# 扫描
# ============================================================
def scan(progress=None):
    items = []
    steps = [
        ("检查浏览器通知授权（弹窗广告主要来源）…", _scan_browser_notifications),
        ("检查计划任务…", _scan_tasks),
        ("检查开机自启项…", _scan_run_keys),
        ("检查启动文件夹…", _scan_startup_folders),
        ("检查正在运行的弹窗程序…", _scan_ad_processes),
        ("检查 Windows 自带推荐广告…", _scan_win_ads),
        ("检查 hosts 劫持…", _scan_hosts),
        ("检查购物导航快捷方式…", _scan_ad_shortcuts),
    ]
    for i, (msg, fn) in enumerate(steps):
        if progress:
            progress(msg, int(i * 100 / len(steps)))
        try:
            items.extend(fn())
        except Exception as e:
            utils.log("广告扫描 %s 出错: %s" % (msg, e), "ERR")
    if progress:
        progress("检查完成", 100)
    order = {"high": 0, "mid": 1, "low": 2}
    items.sort(key=lambda x: (order.get(x["level"], 3), x["category"]))
    return items


# ---------- 1. 浏览器通知（重点） ----------
def browser_user_data_dirs():
    la = os.environ.get("LOCALAPPDATA", "")
    out = []
    for b, label in ((r"Microsoft\Edge\User Data", "Edge"),
                     (r"Google\Chrome\User Data", "Chrome"),
                     (r"360Chrome\Chrome\User Data", "360浏览器")):
        p = os.path.join(la, b)
        if os.path.isdir(p):
            out.append((p, label))
    return out


def _scan_browser_notifications():
    items = []
    for ud, browser in browser_user_data_dirs():
        for prof_dir in glob.glob(os.path.join(ud, "*")):
            if not os.path.isdir(prof_dir):
                continue
            prof = os.path.basename(prof_dir)
            pref = os.path.join(prof_dir, "Preferences")
            if not os.path.exists(pref):
                continue
            try:
                with open(pref, encoding="utf-8", errors="ignore") as f:
                    data = json.load(f)
            except Exception:
                continue

            exc = (((data.get("profile") or {}).get("content_settings") or {})
                   .get("exceptions") or {}).get("notifications") or {}
            if not isinstance(exc, dict):
                continue

            for pattern, conf in exc.items():
                if not isinstance(conf, dict):
                    continue
                if conf.get("setting") != 1:      # 1 = 允许
                    continue
                d = _domain_of(pattern)
                if not d or _is_trusted_domain(d):
                    continue
                ad_hint = _looks_like_ad_domain(d)
                items.append(_mk(
                    "浏览器通知" if not ad_hint else "浏览器通知（广告站）",
                    "%s · %s" % (browser, d),
                    "这个网站被允许给你发通知，关掉页面也会弹。\n"
                    "配置：%s / %s\n%s"
                    % (prof, os.path.basename(pref),
                       "→ 域名特征像广告站（%s）" % ad_hint if ad_hint
                       else "→ 系统通知权限开着，如果不是你常用的网站，建议撤销"),
                    "notif|%s|%s" % (pref, pattern), "browser_notif",
                    level="high" if ad_hint else "mid",
                    default=bool(ad_hint),
                    data={"file": pref, "pattern": pattern,
                          "browser": browser, "profile": prof, "domain": d},
                    extra=d))
    return items


# ---------- 2. 计划任务 ----------
def _scan_tasks():
    items = []
    code, out = utils.run_ps(
        "$t=Get-ScheduledTask -ErrorAction SilentlyContinue | "
        "Where-Object {$_.TaskPath -notlike '*Microsoft*'};"
        "foreach($x in $t){"
        "$a=($x.Actions|ForEach-Object{''+$_.Execute+' '+$_.Arguments}) -join ' ';"
        "Write-Output ($x.TaskPath+'/'+$x.TaskName+'|||'+$x.State+'|||'+$a)}",
        timeout=60)
    if code != 0:
        return items
    for line in out.splitlines():
        line = line.strip()
        if "|||" not in line:
            continue
        parts = line.split("|||", 2)
        if len(parts) < 3:
            continue
        tname, state, action = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if not action or _safe_path(action):
            continue

        kw = _strict_hit(tname) or _strict_hit(action)
        fam = _family_hit(tname + " " + action)
        if not kw and not fam:
            continue

        why = []
        if fam:
            why.append("已知广告组件「%s」" % fam[0])
        if kw:
            why.append("名称/动作含广告特征词「%s」" % kw)
        items.append(_mk(
            "计划任务", tname,
            "状态 %s\n动作：%s\n→ %s" % (state, action[:170], "；".join(why)),
            "task|" + tname, "task",
            level="high",
            data={"task": tname, "action": action},
            extra=action[:200]))
    return items


# ---------- 3. 注册表自启 ----------
RUN_KEYS = [
    (HKLM, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", "HKLM"),
    (HKLM, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run", "HKLM64"),
    (HKLM, r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce", "HKLM"),
    (HKCU, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", "HKCU"),
    (HKCU, r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce", "HKCU"),
]


def _scan_run_keys():
    items = []
    for hive, path, hname in RUN_KEYS:
        for name, val, _ in reg_list_values(hive, path):
            val_s = str(val)
            if _safe_path(val_s):
                continue
            kw = _strict_hit(name) or _strict_hit(val_s)
            fam = _family_hit(name + " " + val_s)
            if not kw and not fam:
                continue
            why = []
            if fam:
                why.append("已知广告组件「%s」" % fam[0])
            if kw:
                why.append("含广告特征词「%s」" % kw)
            items.append(_mk(
                "开机自启", name,
                "命令：%s\n→ %s" % (val_s[:180], "；".join(why)),
                "%s\\%s\\%s" % (hname, path, name), "run",
                level="high",
                data={"hive": utils.HIVE_NAMES[hive], "path": path,
                      "name": name, "cmd": val_s},
                extra=val_s[:200]))
    return items


# ---------- 4. 启动文件夹 ----------
def _startup_dirs():
    out = []
    for base in (os.environ.get("APPDATA", ""), os.environ.get("PROGRAMDATA", "")):
        p = os.path.join(base, r"Microsoft\Windows\Start Menu\Programs\Startup")
        if os.path.isdir(p):
            out.append(p)
    return out


def _scan_startup_folders():
    items = []
    from core.mod_edge import read_lnks_batch
    for d in _startup_dirs():
        lnks = glob.glob(os.path.join(d, "*.lnk"))
        infos = read_lnks_batch(lnks)
        for p in glob.glob(os.path.join(d, "*")):
            name = os.path.basename(p)
            target = ""
            if p.lower().endswith(".lnk"):
                info = infos.get(p) or {}
                target = (str(info.get("target", "")) + " " +
                          str(info.get("args", ""))).strip()
            if _safe_path(target):
                continue
            kw = _strict_hit(name) or _strict_hit(target)
            fam = _family_hit(name + " " + target)
            if not kw and not fam:
                continue
            why = []
            if fam:
                why.append("已知广告组件「%s」" % fam[0])
            if kw:
                why.append("含广告特征词「%s」" % kw)
            items.append(_mk(
                "启动文件夹", name,
                "位置：%s\n目标：%s\n→ %s" % (d, target[:140], "；".join(why)),
                p, "startup_file", level="high",
                data={"path": p}, extra=target[:200]))
    return items


# ---------- 5. 弹窗进程 ----------
def _scan_ad_processes():
    items = []
    seen = set()
    for p in utils.list_processes():
        n = p["name"]
        if not n.endswith(".exe"):
            continue
        if n in seen:
            continue
        exe = p.get("exe") or ""
        if _safe_path(exe):
            continue
        kw = _strict_hit(n) or _strict_hit(exe)
        fam = _family_hit(n + " " + exe)
        if not kw and not fam:
            continue
        seen.add(n)
        why = ("已知广告组件「%s」" % fam[0]) if fam else ("含广告特征词「%s」" % kw)
        items.append(_mk(
            "弹窗进程", n,
            "正在运行：%s\nPID %s\n→ %s" % (exe or "路径未知", p["pid"], why),
            "proc|%s" % p["pid"], "proc",
            level="high",
            data={"name": n, "pid": p["pid"], "exe": exe},
            extra=exe))
    return items


# ---------- 6. Windows 自带推荐广告 ----------
def _scan_win_ads():
    items = []
    for name, label, want_off in WIN_AD_SWITCHES:
        v = reg_read_value(HKCU, WIN_AD_KEY, name)
        if v != 1:
            continue
        items.append(_mk(
            "系统广告", label,
            "注册表 HKCU\\%s\\%s = 1\n"
            "→ 关掉后开始菜单/锁屏/设置页不再推应用和广告" % (WIN_AD_KEY, name),
            "winad|%s" % name, "win_ad",
            level="mid", default=True,
            data={"name": name, "path": WIN_AD_KEY, "label": label},
            extra=str(v)))

    # 搜索框推荐
    bing = reg_read_value(HKCU, r"Software\Microsoft\Windows\CurrentVersion\Search",
                          "BingSearchEnabled")
    if bing == 1:
        items.append(_mk(
            "系统广告", "搜索框网络推荐",
            "注册表 Search\\BingSearchEnabled = 1\n→ 开始菜单搜索会混入网络推广内容",
            "winad|BingSearchEnabled", "win_ad",
            level="mid", default=True,
            data={"name": "BingSearchEnabled",
                  "path": r"Software\Microsoft\Windows\CurrentVersion\Search",
                  "label": "搜索框网络推荐"},
            extra="1"))

    # 开始菜单推荐
    ir = reg_read_value(HKCU, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                        "Start_IrisRecommendations")
    if ir == 1:
        items.append(_mk(
            "系统广告", "开始菜单建议",
            "注册表 Explorer\\Advanced\\Start_IrisRecommendations = 1\n→ 开始菜单会推荐应用",
            "winad|Start_IrisRecommendations", "win_ad",
            level="mid", default=True,
            data={"name": "Start_IrisRecommendations",
                  "path": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                  "label": "开始菜单建议"},
            extra="1"))
    return items


# ---------- 7. hosts ----------
def _scan_hosts():
    items = []
    p = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                     r"System32\drivers\etc\hosts")
    if not os.path.exists(p):
        return items
    try:
        with open(p, encoding="utf-8-sig", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return items

    bad = []
    for ln in lines:
        s = ln.strip().lstrip("\ufeff")
        if not s or s.startswith("#"):
            continue
        parts = s.split()
        if len(parts) < 2:
            continue
        host = parts[1].lower()
        if host in ("localhost", "localhost.localdomain") or host.startswith("127."):
            continue
        if host in ("::1",):
            continue
        bad.append(s)

    if bad:
        items.append(_mk(
            "hosts 劫持", "hosts 里有 %d 条自定义重定向" % len(bad),
            "文件：%s\n\n%s\n→ 这些域名被强制指向指定 IP，是广告/劫持常用手法"
            % (p, "\n".join(bad[:8])),
            p, "hosts", level="mid", default=False,
            data={"path": p, "entries": bad}, extra="\n".join(bad[:20])))
    return items


# ---------- 8. 购物导航快捷方式 ----------
def _scan_ad_shortcuts():
    items = []
    up = os.environ.get("USERPROFILE", "")
    pub = os.environ.get("PUBLIC", r"C:\Users\Public")
    pd = os.environ.get("PROGRAMDATA", "")
    dirs = [
        os.path.join(up, "Desktop"),
        os.path.join(pub, "Desktop"),
        os.path.join(pd, r"Microsoft\Windows\Start Menu\Programs"),
        os.path.join(up, r"Microsoft\Windows\Start Menu\Programs"),
    ]
    ad_url_kw = ("hao.360", "360.cn", "2345.com", "hao123", "duba.com",
                 "taobao.com", "jd.com", "tmall.com", "pinduoduo",
                 "yangkeduo", "wps.cn", "sj.qq.com", "myapp.com")
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for p in glob.glob(os.path.join(d, "*.url")) + \
                glob.glob(os.path.join(d, "*", "*.url")):
            try:
                with open(p, encoding="utf-8", errors="ignore") as f:
                    txt = f.read()
            except Exception:
                continue
            m = re.search(r"URL=(.+)", txt, re.I)
            if not m:
                continue
            url = m.group(1).strip()
            if not any(k in url.lower() for k in ad_url_kw):
                continue
            items.append(_mk(
                "购物/导航快捷方式", os.path.basename(p),
                "指向：%s\n→ 双击即打开购物/导航页，属典型推广手法" % url[:150],
                p, "ad_url", level="mid",
                data={"path": p, "url": url}, extra=url[:200]))
    return items


# ============================================================
# 清除
# ============================================================
def kill(items, batch, progress=None):
    ok = fail = 0
    msgs = []
    total = len(items) or 1

    # 先杀进程，避免文件被占用
    order = {"proc": 0, "task": 1, "run": 2, "startup_file": 3,
             "browser_notif": 4, "win_ad": 5, "hosts": 6, "ad_url": 7}
    items = sorted(items, key=lambda x: order.get(x["kind"], 9))

    for i, it in enumerate(items):
        if progress:
            progress("清除：%s" % it["name"], int(i * 100 / total))
        try:
            r, msg = _kill_one(it, batch)
        except Exception as e:
            r, msg = False, str(e)
        if r:
            ok += 1
        else:
            fail += 1
        msgs.append("%s %s — %s" % ("✓" if r else "✗", it["name"], msg))
        utils.log("广告清除 %s: %s (%s)" % (it["name"], msg, "OK" if r else "FAIL"))

    if progress:
        progress("清除完成", 100)
    return ok, fail, msgs


def _kill_one(it, batch):
    kind = it["kind"]
    d = it["data"]

    # ---------- 进程 ----------
    if kind == "proc":
        pid = d.get("pid")
        name = d.get("name")
        code, out = utils.kill_process(pid=pid)
        if code != 0:
            code, out = utils.kill_process(name=name)
        if code == 0:
            batch.note("结束弹窗进程 %s" % name)
            return True, "进程已结束"
        return False, "结束失败，可能需要管理员权限"

    # ---------- 计划任务 ----------
    if kind == "task":
        full = d.get("task", "")
        code, out = utils.run_cmd(["schtasks", "/Delete", "/TN", full, "/F"], timeout=25)
        if code == 0:
            batch.note("删除广告计划任务 %s" % full)
            return True, "计划任务已删除"
        # 退回 PowerShell
        code2, out2 = utils.run_ps(
            "Unregister-ScheduledTask -TaskName '%s' -Confirm:$false -ErrorAction SilentlyContinue"
            % full.split("/")[-1].replace("'", "''"), timeout=30)
        if code2 == 0:
            batch.note("删除广告计划任务 %s" % full)
            return True, "计划任务已删除"
        return False, "删除失败: %s" % out.strip()[:80]

    # ---------- 自启项 ----------
    if kind == "run":
        hive = utils.hive_from_name(d["hive"])
        batch.backup_reg_value(hive, d["path"], d["name"], "广告自启 " + d["name"])
        if utils.reg_delete_value(hive, d["path"], d["name"]):
            return True, "自启项已移除"
        return False, "删除失败（需要管理员权限）"

    # ---------- 启动文件夹文件 ----------
    if kind == "startup_file":
        p = d["path"]
        if not os.path.exists(p):
            return True, "已不存在"
        ok, msg = batch.quarantine(p, it["name"])
        return (True, "已移入隔离区") if ok else (False, msg)

    # ---------- 浏览器通知权限 ----------
    if kind == "browser_notif":
        pref = d["file"]
        pattern = d["pattern"]
        try:
            utils.backup_batch_file_copy(batch, pref, "浏览器配置")
            with open(pref, encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
        except Exception as e:
            return False, "读取配置失败（浏览器可能在运行）: %s" % e

        exc = (((data.get("profile") or {}).get("content_settings") or {})
               .setdefault("exceptions", {}).setdefault("notifications", {}))
        if pattern not in exc:
            return True, "权限已被移除"
        exc[pattern]["setting"] = 2      # 2 = 阻止
        try:
            tmp = pref + ".cmtmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            shutil.move(tmp, pref)
        except Exception as e:
            return False, "写入失败（请先关闭浏览器）: %s" % e
        return True, "该站点的通知权限已撤销"

    # ---------- Windows 广告开关 ----------
    if kind == "win_ad":
        hive = HKCU
        batch.backup_reg_value(hive, d["path"], d["name"], "系统广告开关 " + d.get("label", ""))
        if utils.reg_set_value(hive, d["path"], d["name"], 0, winreg.REG_DWORD):
            return True, "已关闭"
        return False, "写入失败"

    # ---------- hosts ----------
    if kind == "hosts":
        p = d["path"]
        entries = set(d.get("entries", []))
        try:
            utils.backup_batch_file_copy(batch, p, "hosts 文件")
            with open(p, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            kept = [ln for ln in lines if ln.strip() not in entries]
            with open(p, "w", encoding="utf-8", errors="ignore") as f:
                f.writelines(kept)
            return True, "已移除 %d 条重定向" % len(entries)
        except Exception as e:
            return False, "修改失败（需要管理员权限）: %s" % e

    # ---------- 购物网址快捷方式 ----------
    if kind == "ad_url":
        p = d["path"]
        if not os.path.exists(p):
            return True, "已不存在"
        ok, msg = batch.quarantine(p, it["name"])
        return (True, "已移入隔离区") if ok else (False, msg)

    return False, "未知类型"
