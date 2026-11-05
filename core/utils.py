# -*- coding: utf-8 -*-
"""
底层工具层：管理员权限 / 注册表读写备份 / 进程服务 / 文件隔离区 / 日志

设计原则（参考 RogueCleaner）：
  1. 任何删除动作之前，先备份；备份失败 → 取消该操作
  2. 文件不直接删除，移动到隔离区，可一键还原
  3. 注册表用 reg.exe export 导出 .reg 文件备份
"""
import os
import sys
import json
import time
import shutil
import ctypes
import winreg
import subprocess
import datetime
import threading

APP_NAME = "CleanMaster"
DATA_DIR = os.path.join(os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
                        else os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "CleanMasterData")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
QUARANTINE_DIR = os.path.join(DATA_DIR, "quarantine")
LOG_DIR = os.path.join(DATA_DIR, "logs")
REPORT_DIR = os.path.join(DATA_DIR, "reports")

for _d in (DATA_DIR, BACKUP_DIR, QUARANTINE_DIR, LOG_DIR, REPORT_DIR):
    os.makedirs(_d, exist_ok=True)


# ============================================================
# 日志
# ============================================================
_log_lock = threading.Lock()


def log(msg, tag="INFO"):
    line = "[%s] [%s] %s" % (datetime.datetime.now().strftime("%H:%M:%S"), tag, msg)
    with _log_lock:
        try:
            with open(os.path.join(LOG_DIR, "run-%s.log" % datetime.date.today().isoformat()),
                      "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass


# ============================================================
# 管理员权限
# ============================================================
def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin():
    """以管理员身份重启自己，返回是否成功发起"""
    try:
        if getattr(sys, "frozen", False):
            exe = sys.executable
            params = " ".join('"%s"' % a for a in sys.argv[1:])
        else:
            exe = sys.executable
            params = '"%s" ' % os.path.abspath(sys.argv[0]) + \
                     " ".join('"%s"' % a for a in sys.argv[1:])
        r = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
        return r > 32
    except Exception as e:
        log("提权失败: %s" % e, "ERR")
        return False


# ============================================================
# 子进程封装（Windows 中文输出常用 gbk）
# ============================================================
def CREATE_NO_WINDOW():
    return 0x08000000


def run_cmd(args, timeout=30, shell=False):
    """执行命令，返回 (code, stdout+stderr)"""
    try:
        kw = dict(stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                  timeout=timeout, shell=shell,
                  creationflags=0x08000000)
        p = subprocess.run(args, **kw)
        out = p.stdout or b""
        for enc in ("gbk", "utf-8", "latin-1"):
            try:
                return p.returncode, out.decode(enc)
            except Exception:
                continue
        return p.returncode, out.decode("utf-8", "ignore")
    except subprocess.TimeoutExpired:
        return -1, "timeout"
    except Exception as e:
        return -1, str(e)


def run_ps(script, timeout=60):
    """执行 PowerShell 脚本"""
    return run_cmd(["powershell", "-NoProfile", "-NonInteractive",
                    "-ExecutionPolicy", "Bypass", "-Command", script], timeout=timeout)


# ============================================================
# 注册表辅助
# ============================================================
HIVE_NAMES = {
    winreg.HKEY_LOCAL_MACHINE: "HKLM",
    winreg.HKEY_CURRENT_USER: "HKCU",
    winreg.HKEY_CLASSES_ROOT: "HKCR",
    winreg.HKEY_USERS: "HKU",
}

# 名字 → 常量（winreg 没有 HKCU 这种短名属性）
HIVE_CONST = {
    "HKLM": winreg.HKEY_LOCAL_MACHINE,
    "HKCU": winreg.HKEY_CURRENT_USER,
    "HKCR": winreg.HKEY_CLASSES_ROOT,
    "HKU": winreg.HKEY_USERS,
}


def hive_from_name(name):
    return HIVE_CONST.get(name, winreg.HKEY_LOCAL_MACHINE)


def reg_path_str(hive, path):
    return "%s\\%s" % (HIVE_NAMES.get(hive, "HKLM"), path)


def reg_key_exists(hive, path):
    try:
        with winreg.OpenKey(hive, path, 0, winreg.KEY_READ) as k:
            return True
    except Exception:
        return False


def reg_read_value(hive, path, name):
    try:
        with winreg.OpenKey(hive, path, 0, winreg.KEY_READ) as k:
            v, _ = winreg.QueryValueEx(k, name)
            return v
    except Exception:
        return None


def reg_list_subkeys(hive, path):
    """列出子键名，读不到返回 []"""
    out = []
    try:
        with winreg.OpenKey(hive, path, 0, winreg.KEY_READ) as k:
            i = 0
            while True:
                try:
                    out.append(winreg.EnumKey(k, i))
                    i += 1
                except OSError:
                    break
    except Exception:
        pass
    return out


def reg_list_values(hive, path):
    """列出 (name, value, type)"""
    out = []
    try:
        with winreg.OpenKey(hive, path, 0, winreg.KEY_READ) as k:
            i = 0
            while True:
                try:
                    name, val, typ = winreg.EnumValue(k, i)
                    out.append((name, val, typ))
                    i += 1
                except OSError:
                    break
    except Exception:
        pass
    return out


def reg_delete_tree(hive, path):
    """递归删除注册表项"""
    def _del(h, p):
        for sub in reg_list_subkeys(h, p):
            _del(h, p + "\\" + sub)
        try:
            winreg.DeleteKey(h, p)
            return True
        except Exception as e:
            log("删除注册表失败 %s: %s" % (p, e), "WARN")
            return False
    return _del(hive, path)


def reg_delete_value(hive, path, name):
    try:
        with winreg.OpenKey(hive, path, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, name)
        return True
    except Exception as e:
        log("删除注册表值失败 %s\\%s: %s" % (path, name, e), "WARN")
        return False


def reg_set_value(hive, path, name, value, typ=winreg.REG_SZ):
    try:
        with winreg.CreateKeyEx(hive, path, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, name, 0, typ, value)
        return True
    except Exception as e:
        log("写注册表失败 %s\\%s: %s" % (path, name, e), "WARN")
        return False


# ------------------------------------------------------------
# 纯 Python 注册表导出/还原（不依赖 reg.exe，被杀软拦截也能用）
# ------------------------------------------------------------
def dump_key(hive, path, depth=0):
    """
    递归导出注册表键为可序列化结构。
    返回 {'values': [...], 'keys': {name: subtree}} 或 None（读不到）
    """
    if depth > 24:
        return {"values": [], "keys": {}}
    node = {"values": [], "keys": {}}
    try:
        with winreg.OpenKey(hive, path, 0, winreg.KEY_READ) as k:
            i = 0
            while True:
                try:
                    name, val, typ = winreg.EnumValue(k, i)
                    node["values"].append({"name": name,
                                           "value": _jsonable(val),
                                           "type": typ})
                    i += 1
                except OSError:
                    break
    except Exception:
        return None
    for sub in reg_list_subkeys(hive, path):
        child = dump_key(hive, path + "\\" + sub, depth + 1)
        if child is not None:
            node["keys"][sub] = child
    return node


def restore_key(hive, path, node):
    """把 dump_key 的结果写回注册表"""
    try:
        with winreg.CreateKeyEx(hive, path, 0, winreg.KEY_WRITE) as k:
            for v in node.get("values", []):
                name = v["name"]
                val = _unjsonable(v["value"])
                typ = v["type"]
                if typ == winreg.REG_MULTI_SZ and not isinstance(val, list):
                    val = [val] if val else []
                winreg.SetValueEx(k, name, 0, typ, val)
    except Exception as e:
        log("还原注册表失败 %s: %s" % (path, e), "WARN")
        return False
    for name, child in (node.get("keys") or {}).items():
        restore_key(hive, path + "\\" + name, child)
    return True


# ============================================================
# 备份批次（恢复中心的核心）
# ============================================================
class BackupBatch:
    """
    一次清理动作对应一个批次目录：
        backups/<batch_id>/
            manifest.json     记录所有可回滚动作
            reg/*.reg         注册表导出备份
            files/...         被移动的文件（隔离区）
    """

    def __init__(self, batch_id=None, title=""):
        self.batch_id = batch_id or datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.title = title
        self.dir = os.path.join(BACKUP_DIR, self.batch_id)
        self.reg_dir = os.path.join(self.dir, "reg")
        self.file_dir = os.path.join(self.dir, "files")
        os.makedirs(self.reg_dir, exist_ok=True)
        os.makedirs(self.file_dir, exist_ok=True)
        self.actions = []
        self._lock = threading.Lock()
        self._save()

    # ---------- 注册表 ----------
    def backup_reg(self, hive, path, label=""):
        """
        导出注册表项；失败返回 False（调用方应据此取消删除）。
        主备份用 winreg 递归导出 JSON —— 不依赖 reg.exe，被安全软件拦了也能用；
        同时尽力再导出一个 .reg 文件，方便用户手动检查。
        """
        if not reg_key_exists(hive, path):
            return True  # 本来就不存在，无需备份

        n = len(self.actions) + 1
        node = dump_key(hive, path)
        if node is None:
            log("注册表读取失败，无法备份: %s" % reg_path_str(hive, path), "ERR")
            return False

        jf = os.path.join(self.reg_dir, "reg_%03d.json" % n)
        try:
            with open(jf, "w", encoding="utf-8") as f:
                json.dump(node, f, ensure_ascii=False)
        except Exception as e:
            log("写注册表备份失败: %s" % e, "ERR")
            return False

        # 附加的可读副本（失败不影响主备份）
        rf = os.path.join(self.reg_dir, "reg_%03d.reg" % n)
        try:
            run_cmd(["reg", "export", reg_path_str(hive, path), rf, "/y"], timeout=30)
        except Exception:
            pass

        with self._lock:
            self.actions.append({
                "type": "reg_key",
                "target": reg_path_str(hive, path),
                "hive": HIVE_NAMES.get(hive, "HKLM"),
                "path": path,
                "backup": os.path.relpath(jf, self.dir),
                "reg_file": (os.path.relpath(rf, self.dir)
                             if os.path.exists(rf) else None),
                "label": label or path,
                "time": time.time(),
            })
        self._save()
        return True

    def backup_reg_value(self, hive, path, name, label=""):
        """备份单个值的当前状态（用于值级修改）"""
        val = reg_read_value(hive, path, name)
        with self._lock:
            self.actions.append({
                "type": "reg_value",
                "hive": HIVE_NAMES.get(hive, "HKLM"),
                "path": path,
                "name": name,
                "old": _jsonable(val),
                "label": label or ("%s\\%s" % (path, name)),
                "time": time.time(),
            })
        self._save()
        return True

    # ---------- 文件 ----------
    def quarantine(self, src, label=""):
        """把文件/目录移动到隔离区，返回 (成功, 说明)"""
        if not os.path.exists(src):
            return True, "已不存在"
        base = os.path.basename(src.rstrip("\\/")) or "item"
        dst = os.path.join(self.file_dir, "%03d_%s" % (len(self.actions) + 1, base))
        try:
            shutil.move(src, dst)
        except Exception as e:
            log("隔离失败 %s: %s" % (src, e), "ERR")
            return False, str(e)
        with self._lock:
            self.actions.append({
                "type": "file",
                "original": src,
                "stored": os.path.relpath(dst, self.dir),
                "label": label or src,
                "time": time.time(),
            })
        self._save()
        return True, "已隔离"

    def backup_file_copy(self, src, label=""):
        """复制一份文件做备份（用于原地修改的 lnk / json），返回 (成功, 说明)"""
        if not os.path.exists(src):
            return False, "文件不存在"
        base = os.path.basename(src.rstrip("\\/")) or "item"
        dst = os.path.join(self.file_dir, "%03d_copy_%s" % (len(self.actions) + 1, base))
        try:
            shutil.copy2(src, dst)
        except Exception as e:
            log("复制备份失败 %s: %s" % (src, e), "ERR")
            return False, str(e)
        with self._lock:
            self.actions.append({
                "type": "file_copy",
                "original": src,
                "stored": os.path.relpath(dst, self.dir),
                "label": label or src,
                "time": time.time(),
            })
        self._save()
        return True, "已备份"

    def note(self, label, detail=""):
        """记录一个不可回滚动作（如结束进程），仅作审计"""
        with self._lock:
            self.actions.append({
                "type": "note", "label": label, "detail": detail,
                "time": time.time(),
            })
        self._save()

    # ---------- 持久化 ----------
    def _save(self):
        data = {
            "batch_id": self.batch_id,
            "title": self.title,
            "created": time.time(),
            "created_str": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "restored": False,
            "actions": self.actions,
        }
        try:
            with open(os.path.join(self.dir, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log("写 manifest 失败: %s" % e, "ERR")

    @property
    def count(self):
        return len([a for a in self.actions if a["type"] != "note"])


def _jsonable(v):
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if isinstance(v, bytes):
        return {"__bytes__": v.hex()}
    if isinstance(v, (list, tuple)):
        return {"__list__": [_jsonable(i) for i in v]}
    return str(v)


def _unjsonable(v):
    if isinstance(v, dict):
        if "__bytes__" in v:
            return bytes.fromhex(v["__bytes__"])
        if "__list__" in v:
            return [_unjsonable(i) for i in v["__list__"]]
        return str(v)
    return v


def backup_batch_file_copy(batch, path, label=""):
    """模块级快捷方式：复制文件备份"""
    return batch.backup_file_copy(path, label)


def list_batches():
    """列出所有备份批次（新→旧）"""
    out = []
    if not os.path.isdir(BACKUP_DIR):
        return out
    for name in os.listdir(BACKUP_DIR):
        mf = os.path.join(BACKUP_DIR, name, "manifest.json")
        if not os.path.exists(mf):
            continue
        try:
            with open(mf, encoding="utf-8") as f:
                d = json.load(f)
            d["_dir"] = os.path.join(BACKUP_DIR, name)
            size = 0
            for root, _, files in os.walk(d["_dir"]):
                for fn in files:
                    try:
                        size += os.path.getsize(os.path.join(root, fn))
                    except Exception:
                        pass
            d["_size"] = size
            out.append(d)
        except Exception:
            continue
    out.sort(key=lambda x: x.get("created", 0), reverse=True)
    return out


def restore_batch(batch_id, progress=None):
    """
    回滚一个批次的全部动作。返回 (成功数, 失败数, 失败详情)
    """
    mf = os.path.join(BACKUP_DIR, batch_id, "manifest.json")
    if not os.path.exists(mf):
        return 0, 1, ["批次不存在"]
    with open(mf, encoding="utf-8") as f:
        d = json.load(f)
    bdir = os.path.dirname(mf)
    ok = fail = 0
    fails = []
    for act in reversed(d.get("actions", [])):
        t = act["type"]
        if t == "note":
            continue
        try:
            if t == "reg_key":
                bfile = os.path.join(bdir, act["backup"])
                # 兼容旧格式：从 target 字符串解析
                if act.get("hive"):
                    hive = hive_from_name(act["hive"])
                    path = act["path"]
                else:
                    target = act["target"]
                    if target.startswith("HKCU\\"):
                        hive, path = winreg.HKEY_CURRENT_USER, target[5:]
                    elif target.startswith("HKCR\\"):
                        hive, path = winreg.HKEY_CLASSES_ROOT, target[5:]
                    else:
                        hive, path = winreg.HKEY_LOCAL_MACHINE, target[5:]
                # 先删掉当前的残留，再写回备份
                reg_delete_tree(hive, path)
                if bfile.endswith(".json") and os.path.exists(bfile):
                    with open(bfile, encoding="utf-8") as f:
                        node = json.load(f)
                    if restore_key(hive, path, node):
                        ok += 1
                    else:
                        fail += 1
                        fails.append("%s: 写回失败" % act.get("target", path))
                else:
                    code, out = run_cmd(["reg", "import", bfile], timeout=30)
                    if code == 0:
                        ok += 1
                    else:
                        fail += 1
                        fails.append("%s: %s" % (act.get("target", path),
                                                 out.strip()[:120]))
            elif t == "reg_value":
                hive = hive_from_name(act["hive"])
                old = act["old"]
                if old is None:
                    reg_delete_value(hive, act["path"], act["name"])
                else:
                    if isinstance(old, dict) and "__bytes__" in old:
                        reg_set_value(hive, act["path"], act["name"],
                                      bytes.fromhex(old["__bytes__"]), winreg.REG_BINARY)
                    elif isinstance(old, int):
                        reg_set_value(hive, act["path"], act["name"], old, winreg.REG_DWORD)
                    else:
                        reg_set_value(hive, act["path"], act["name"], str(old))
                ok += 1
            elif t == "file":
                src = os.path.join(bdir, act["stored"])
                dst = act["original"]
                if os.path.exists(src):
                    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
                    if os.path.exists(dst):
                        shutil.rmtree(dst, ignore_errors=True) if os.path.isdir(dst) \
                            else os.remove(dst)
                    shutil.move(src, dst)
                    ok += 1
                else:
                    fail += 1
                    fails.append("%s: 备份文件丢失" % dst)
            elif t == "file_copy":
                src = os.path.join(bdir, act["stored"])
                dst = act["original"]
                if os.path.exists(src):
                    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
                    shutil.copy2(src, dst)
                    ok += 1
                else:
                    fail += 1
                    fails.append("%s: 备份文件丢失" % dst)
        except Exception as e:
            fail += 1
            fails.append("%s: %s" % (act.get("label", "?"), e))
        if progress:
            progress(act)

    d["restored"] = True
    d["restored_str"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(mf, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return ok, fail, fails


# ============================================================
# 进程 / 服务 / 计划任务
# ============================================================
def list_processes():
    """
    返回 [{'pid','name','exe','cmdline'}]，用 CIM 拿命令行
    """
    code, out = run_ps(
        "Get-CimInstance Win32_Process | Select-Object ProcessId,Name,ExecutablePath,CommandLine "
        "| ConvertTo-Json -Compress", timeout=40)
    procs = []
    if code == 0 and out.strip().startswith("["):
        try:
            for p in json.loads(out):
                procs.append({
                    "pid": p.get("ProcessId"),
                    "name": (p.get("Name") or "").lower(),
                    "exe": p.get("ExecutablePath") or "",
                    "cmdline": p.get("CommandLine") or "",
                })
        except Exception:
            pass
    if not procs:
        # 降级：tasklist
        code, out = run_cmd(["tasklist", "/fo", "csv", "/nh"], timeout=30)
        for line in out.splitlines():
            parts = [x.strip('"') for x in line.split('","')]
            if len(parts) >= 2:
                procs.append({"pid": parts[1], "name": parts[0].lower(),
                              "exe": "", "cmdline": ""})
    return procs


def kill_process(pid=None, name=None, tree=True):
    """结束进程，返回 (成功, 输出)"""
    if pid:
        args = ["taskkill", "/F", "/PID", str(pid)]
        if tree:
            args.insert(2, "/T")
        return run_cmd(args, timeout=20)
    if name:
        return run_cmd(["taskkill", "/F", "/IM", name, "/T"], timeout=20)
    return False, "no target"


def list_services():
    """
    返回 [{'name','display','state','start','path'}]，含驱动
    """
    base = r"SYSTEM\CurrentControlSet\Services"
    out = []
    for sub in reg_list_subkeys(winreg.HKEY_LOCAL_MACHINE, base):
        p = base + "\\" + sub
        disp = reg_read_value(winreg.HKEY_LOCAL_MACHINE, p, "DisplayName") or sub
        img = reg_read_value(winreg.HKEY_LOCAL_MACHINE, p, "ImagePath") or ""
        typ = reg_read_value(winreg.HKEY_LOCAL_MACHINE, p, "Type")
        start = reg_read_value(winreg.HKEY_LOCAL_MACHINE, p, "Start")
        out.append({
            "name": sub,
            "display": str(disp),
            "image": str(img),
            "type": typ,
            "start": start,
            "is_driver": typ in (1, 2) if isinstance(typ, int) else False,
        })
    # 补充运行状态
    code, txt = run_cmd(["sc", "query", "state=", "all"], timeout=30)
    running = set()
    cur = None
    for line in txt.splitlines():
        s = line.strip()
        if s.startswith("SERVICE_NAME:"):
            cur = s.split(":", 1)[1].strip()
        elif "RUNNING" in s and cur:
            running.add(cur)
    for s in out:
        s["state"] = "RUNNING" if s["name"] in running else "STOPPED"
    return out


def stop_service(name):
    return run_cmd(["sc", "stop", name], timeout=30)


def delete_service(name):
    return run_cmd(["sc", "delete", name], timeout=30)


def list_tasks():
    """返回 [{'name','path','state'}]"""
    tasks = []
    code, out = run_ps(
        "Get-ScheduledTask | Select-Object TaskName,TaskPath,State | ConvertTo-Json -Compress",
        timeout=45)
    if code == 0 and out.strip().startswith("["):
        try:
            for t in json.loads(out):
                tasks.append({
                    "name": t.get("TaskName") or "",
                    "path": t.get("TaskPath") or "",
                    "state": str(t.get("State") or ""),
                })
        except Exception:
            pass
    return tasks


def delete_task(path, name):
    full = (path or "\\") + name
    return run_cmd(["schtasks", "/Delete", "/TN", full, "/F"], timeout=25)


# ============================================================
# 杂项
# ============================================================
def human_size(n):
    if n is None:
        return "-"
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return ("%.0f %s" % (n, unit)) if unit == "B" else ("%.1f %s" % (n, unit))
        n /= 1024.0
    return "%.1f PB" % n


def dir_size(path, max_seconds=8):
    """快速统计目录大小"""
    total = 0
    t0 = time.time()
    try:
        for root, dirs, files in os.walk(path, onerror=lambda e: None):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except Exception:
                    pass
            if time.time() - t0 > max_seconds:
                break
    except Exception:
        pass
    return total


def is_protected(path):
    from core.rules import PROTECTED_PATHS
    p = os.path.abspath(path).lower().rstrip("\\")
    for prot in PROTECTED_PATHS:
        if p == prot or p.startswith(prot + "\\"):
            return True
    return False


def get_drives():
    """返回 [(盘符, 总容量, 已用, 可用)]"""
    drives = []
    try:
        buf = ctypes.create_unicode_buffer(512)
        ctypes.windll.kernel32.GetLogicalDriveStringsW(512, buf)
        for d in buf.value.split("\x00"):
            if not d.strip():
                continue
            try:
                free = ctypes.c_ulonglong(0)
                total = ctypes.c_ulonglong(0)
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    ctypes.c_wchar_p(d),
                    ctypes.byref(free), ctypes.byref(total), None)
                drives.append((d.rstrip("\\"), total.value, total.value - free.value, free.value))
            except Exception:
                pass
    except Exception:
        pass
    return drives


def open_path(path):
    try:
        os.startfile(path)
        return True
    except Exception:
        return False
