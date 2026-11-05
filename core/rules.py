# -*- coding: utf-8 -*-
"""
规则库：360 家族特征 / 流氓软件识别 / 磁盘垃圾路径

所有检测都基于"证据"，每条命中都给用户看理由，不做黑盒判断。
"""

# ============================================================
# 一、360 / 奇虎 家族特征
# ============================================================

# 进程名（小写）
PROC_360 = {
    "360tray.exe": "360安全卫士托盘",
    "360sd.exe": "360杀毒",
    "360rp.exe": "360杀毒实时防护",
    "360rps.exe": "360杀毒服务",
    "360safe.exe": "360安全卫士主程序",
    "360se.exe": "360安全浏览器",
    "360se6.exe": "360安全浏览器6",
    "360chromex.exe": "360极速浏览器",
    "360chrome.exe": "360极速浏览器",
    "360leakfixer.exe": "360漏洞修复",
    "360entclient.exe": "360企业版客户端",
    "360netmon.exe": "360网络监控",
    "360speedld.exe": "360测速",
    "360desktop.exe": "360桌面助手",
    "360wallpaper.exe": "360壁纸",
    "360quickinfo.exe": "360快讯",
    "360newslist.exe": "360热点资讯",
    "360login.exe": "360登录组件",
    "360appmgr.exe": "360软件管家",
    "360softmgr.exe": "360软件管家",
    "360zip.exe": "360压缩",
    "360drvinst.exe": "360驱动大师",
    "360hyk.exe": "360硬件检测",
    "360hardware.exe": "360硬件大师",
    "360sysdoctor.exe": "360系统急救箱",
    "360sysrescue.exe": "360系统急救箱",
    "360menusvr.exe": "360右键菜单管理",
    "360brmon.exe": "360浏览器监控",
    "360browerhelper.exe": "360浏览器助手",
    "360imagemgr.exe": "360看图",
    "360videoplay.exe": "360影视",
    "360game.exe": "360游戏大厅",
    "360wangpan.exe": "360云盘",
    "360uyap.exe": "360无限",
    "qhsafe.exe": "360安全卫士(奇虎)",
    "qhsafetray.exe": "360安全卫士托盘(奇虎)",
    "qhsafemon.exe": "360主动防御监控",
    "zhudongfangyu.exe": "360主动防御",
    "qhidefense.exe": "360主动防御",
    "qhaider.exe": "360Aider",
    "liveupdate360.exe": "360升级服务",
    "360upd.exe": "360升级",
    "safemon.exe": "360安全监控",
    "bapmon.exe": "360浏览器保护",
    "whmysql.exe": "360网盾",
    "360netguard.exe": "360网盾",
    "360base.dll": "360基础模块(非进程)",
    "360cir.dll": "360组件",
    "360appsvc.exe": "360应用服务",
    "360p2spmanager.exe": "360 P2P 加速",
    "360p2pservice.exe": "360 P2P 上传服务",
    "360box.exe": "360沙箱",
    "360safebox.exe": "360安全沙箱",
    "360wfp.exe": "360网络过滤",
    "360sysmon.exe": "360系统监控",
    "360traysu.exe": "360提权组件",
    "360repair.exe": "360系统修复",
    "360clean.exe": "360清理",
    "360magicbox.exe": "360魔法盒",
    "360browser.exe": "360浏览器",
    "360ins.exe": "360安装器",
    "360patch.exe": "360补丁",
    "360hotfix.exe": "360热修复",
    "360tray64.exe": "360安全卫士托盘64",
    "360sdupd.exe": "360杀毒升级",
    "360vulscan.exe": "360漏洞扫描",
    "360redmoney.exe": "360红包",
    "360mini.exe": "360迷你窗口",
    "360im.exe": "360即时通讯",
    "360shop.exe": "360商城",
    "360buy.exe": "360购物",
    "360navigate.exe": "360导航",
    "360news.exe": "360新闻",
    "360sport.exe": "360体育",
    "360licai.exe": "360理财",
    "360loan.exe": "360借条",
    "360youqi.exe": "360游戏",
}

# 服务 / 驱动名（小写，支持部分匹配）
SERVICE_360_EXACT = {
    "360antihacker": "360木马防火墙驱动",
    "360box": "360沙箱驱动",
    "360camera": "360摄像头保护",
    "360fsflt": "360文件系统过滤驱动",
    "360hvm": "360硬件虚拟化",
    "360netmon": "360网络监控驱动",
    "360rp": "360杀毒服务",
    "360rps": "360杀毒服务",
    "360sd": "360杀毒服务",
    "360sdupdt": "360杀毒升级",
    "360se": "360浏览器服务",
    "360安全卫士": "360安全卫士服务",
    "360deepscan": "360深度扫描",
    "360devmon": "360设备监控",
    "360wfp": "360网络过滤驱动",
    "360safebox": "360安全沙箱",
    "360trayman": "360托盘管理",
    "bapidrv": "360/Baidu 强删驱动",
    "qhactivedefense": "360主动防御服务",
    "qhprotected": "360自我 protected 服务",
    "qhwactdu": "360主动防御",
    "qhaider": "360Aider 服务",
    "qhwatchdog": "360看门狗",
    "qhsafemon": "360安全监控服务",
    "qhsafe": "360安全卫士服务",
    "qutmdrv": "360 UTM 驱动",
    "safemon": "360安全监控",
    "sfemon": "360安全监控",
    "zhudongfangyu": "360主动防御驱动",
    "360qpesv": "360 QPESV 驱动",
    "360boxfs": "360沙箱文件系统",
    "360antisafe": "360防盗",
    "360netfilter": "360网络过滤",
    "360regdef": "360注册表防护",
    "360selfprotect": "360自保护",
    "360drvman": "360驱动管理",
    "360appsvc": "360应用服务",
    "360ipsvc": "360 IP 服务",
    "360nslookup": "360 DNS 服务",
    "360updatesvc": "360升级服务",
}

SERVICE_360_FUZZY = ["360", "qihoo", "qhsafe", "zhudongfangyu"]

# 安装目录特征（相对盘符/系统盘）
DIR_360 = [
    r"C:\Program Files\360",
    r"C:\Program Files (x86)\360",
    r"C:\Program Files\360safe",
    r"C:\Program Files (x86)\360safe",
    r"C:\Program Files\Qihoo",
    r"C:\Program Files (x86)\Qihoo",
    r"C:\360Safe",
    r"C:\360Rec",
    r"C:\360Downloads",
    r"C:\360WiFi",
    r"C:\360SANDBOX",
    r"C:\360Safe\SoftMgr",
    r"C:\ProgramData\360safe",
    r"C:\ProgramData\360",
    r"C:\ProgramData\360Sec",
    r"C:\ProgramData\Qihoo",
    r"C:\ProgramData\360TotalSecurity",
    r"C:\Users\Public\360Downloads",
    r"C:\Users\Public\Documents\360",
]
DIR_360_USER = [  # 相对 %LOCALAPPDATA% / %APPDATA%
    r"360",
    r"360safe",
    r"360se",
    r"360Chrome",
    r"360Browser",
    r"Qihoo",
    r"360TotalSecurity",
    r"360Desktop",
    r"360Wallpaper",
]

# 注册表软件键特征
REG_360_PREFIX = ["360", "qihoo", "qhsafe", "360safe", "360se", "360sd", "360safe"]

# 计划任务名特征
TASK_360_FUZZY = ["360", "qihoo", "zhudongfangyu"]

# ============================================================
# 二、流氓软件 / 捆绑软件识别
# ============================================================

# 厂商特征：命中就给基础分
# 注意：关键词必须够独特，避免误伤（比如 thunderbolt 不是迅雷）
VENDOR_RULES = [
    # 关键词(小写) , 分 , 厂商显示名
    (["360安全", "360浏览器", "360杀毒", "360压缩", "360驱动", "360壁纸",
      "360软件管家", "360安全卫士", "qihoo", "奇虎"], 62, "360 / 奇虎"),
    (["2345"], 62, "2345 系列"),
    (["金山毒霸", "猎豹浏览器", "liebao", "duba"], 50, "金山 / 猎豹"),
    (["百度卫士", "百度杀毒", "百度浏览器"], 50, "百度安全"),
    (["鲁大师", "ludashi"], 50, "鲁大师"),
    (["驱动精灵", "drivergenius"], 50, "驱动精灵"),
    (["驱动人生", "drivethelife"], 46, "驱动人生"),
    (["快压", "kuaiya"], 58, "快压"),
    (["好压", "2345haozip"], 58, "好压"),
    (["小鸟壁纸", "xiaoniao"], 58, "小鸟壁纸"),
    (["搜狗输入法", "搜狗浏览器", "搜狗拼音", "sogou"], 22, "搜狗"),
    (["迅雷", "xunlei", "thunder network", "thunderplatform"], 22, "迅雷"),
    (["快播", "kuaibo", "qvod"], 58, "快播"),
    (["腾讯电脑管家", "qqpcmgr", "qkpcmgr"], 26, "腾讯电脑管家"),
    (["flash center", "flashcenter", "flash大厅", "flash中国", "flash player 中国"], 58, "Flash 中国版"),
    (["wps", "kingsoft office", "wps office"], 10, "WPS / 金山"),
    (["钉钉", "dingtalk"], 6, "钉钉"),
    (["夸克", "quark"], 18, "夸克"),
    (["游戏大厅", "gamelobby", "游戏盒子", "gamebox", "游戏中心"], 30, "游戏大厅"),
    (["手机助手", "phoneassist", "mobileassist", "手机管家"], 30, "手机助手"),
    (["一键装机", "装机大师", "系统之家", "小白装机"], 58, "装机工具"),
    (["hao123", "网址导航", "导航大全", "2345导航"], 56, "网址导航"),
    (["壁纸", "desktopshow", "桌面秀"], 16, "壁纸/桌面"),
    (["天气"], 8, "天气插件"),
    (["pdf转换", "pdf converter", "pdf工厂", "pdf工具箱"], 28, "PDF 捆绑工具"),
    (["加速器", "系统加速", "开机加速"], 26, "系统加速"),
    (["清理大师", "clean master", "清理助手", "垃圾清理"], 24, "清理工具"),
    (["安全卫士", "电脑管家", "电脑保镖", "安全防护中心"], 24, "安全/管家类"),
]

# 名称特征加分
NAME_RULES = [
    (["推广", "推荐", "特价", "红包", "福利", "返利", "优惠券", "抢购", "广告"], 34, "推广/返利性质"),
    (["安装包", "下载器", "downloader", "极速下载"], 24, "下载器/安装包"),
    (["静默", "捆绑", "bundle", "绿色版"], 32, "捆绑安装特征"),
    (["工具栏", "toolbar"], 20, "浏览器工具栏"),
    (["小助手", "精灵", "神器", "大师", "专家", "管家"], 12, "泛用命名"),
    (["精简版", "破解版", "激活工具", "注册机"], 30, "破解/激活工具"),
    (["影视", "直播", "小说", "漫画"], 10, "娱乐内容"),
    (["我的电脑", "此电脑", "系统工具", "系统优化"], 20, "伪装系统工具"),
]

# 白名单：正规软件，直接降权
WHITELIST_VENDORS = [
    "microsoft", "微软", "windows", "google", "apple", "adobe", "mozilla",
    "jetbrains", "valve", "steam", "epic games", "nvidia", "amd", "intel",
    "realtek", "logitech", "razer", "corsair", "asus", "华硕", "acer", "宏碁",
    "lenovo", "联想", "dell", "戴尔", "hp ", "惠普", "msi", "微星",
    "samsung", "三星", "gigabyte", "技嘉", "asrock", "华擎", "toshiba",
    "python", "node.js", "git", "github", "docker", "vmware", "oracle",
    "autodesk", "unity", "blender", "lively", "obs studio", "obs project",
    "7-zip", "igor pavlov", "videolan", "vlc", "notepad++", "sublime",
    "visual studio", "wps office", "kingsoft office",
    "tencent", "qq", "wechat", "微信", "企业微信", "阿里旺旺", "支付宝",
    "netease", "网易", "baidu netdisk", "百度网盘", "bandizip", "bandisoft",
    "teamviewer", "anydesk", "zoom", "slack", "discord", "spotify", "telegram",
    "thunderbird", "firefox", "chromium", "opera", "brave", "vivaldi",
    "potplayer", "daum", "kmplayer", "gimp", "inkscape", "audacity",
    "wireshark", "postman", "figma", "skype", "line", "whatsapp",
]

WHITELIST_NAMES = [
    "microsoft visual c++", "microsoft .net", "windows sdk", "directx",
    "windows driver package", "microsoft edge", "windows 更新",
    "python ", "node.js", "git version", "7-zip", "vlc media player",
    "steam", "nvidia", "realtek", "intel", "amd ", "google chrome",
    "lively wallpaper", "armoury crate", "myasus", "aura", "asus update",
]

# 高风险安装路径（隐蔽安装）
SUSPICIOUS_INSTALL_PATHS = [
    "\\appdata\\local\\temp",
    "\\windows\\temp",
    "\\users\\public\\",
    "\\programdata\\temp",
    "\\downloads\\",
    "\\recycle",
]

# ============================================================
# 三、磁盘垃圾 / 可清理内容
# ============================================================

# (key, 名称, 路径模板, 说明, 默认勾选, 风险等级)
# 路径模板支持环境变量
JUNK_LOCATIONS = [
    ("user_temp", "用户临时文件", [r"%TEMP%"], "系统和软件运行产生的临时文件，可安全清理", True, "safe"),
    ("win_temp", "Windows 临时文件", [r"%SystemRoot%\Temp"], "系统级临时文件", True, "safe"),
    ("prefetch", "预读取缓存", [r"%SystemRoot%\Prefetch"], "预读取文件，清理后首次打开程序略慢", True, "safe"),
    ("thumbcache", "缩略图缓存", [r"%LOCALAPPDATA%\Microsoft\Windows\Explorer"], "缩略图数据库，清理后需重新生成", True, "safe"),
    ("inetcache", "IE/系统网页缓存", [r"%LOCALAPPDATA%\Microsoft\Windows\INetCache"], "旧版网页缓存", True, "safe"),
    ("crashdump", "崩溃转储文件", [r"%LOCALAPPDATA%\CrashDumps", r"%SystemRoot%\Minidump", r"%SystemRoot%\MEMORY.DMP"], "程序崩溃时的内存转储，通常很大", True, "safe"),
    ("wupdate", "Windows 更新缓存", [r"%SystemRoot%\SoftwareDistribution\Download"], "已安装更新的安装包缓存", True, "safe"),
    ("delivery", "更新分发缓存", [r"%SystemRoot%\ServiceProfiles\NetworkService\AppData\Local\Microsoft\Windows\DeliveryOptimization"], "更新 P2P 分发缓存", True, "safe"),
    ("wer", "错误报告存档", [r"%LOCALAPPDATA%\Microsoft\Windows\WER", r"%ProgramData%\Microsoft\Windows\WER"], "Windows 错误报告", True, "safe"),
    ("logs", "系统日志缓存", [r"%SystemRoot%\Logs\CBS", r"%SystemRoot%\Logs\DISM"], "系统组件安装日志", True, "safe"),
    ("downloads_old", "下载文件夹(旧文件)", [r"%USERPROFILE%\Downloads"], "超过 90 天未修改的下载文件", False, "careful"),
    ("edge_cache", "Edge 浏览器缓存", [
        r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Cache",
        r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Code Cache",
        r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\GPUCache",
        r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Service Worker\CacheStorage",
    ], "网页缓存，清理后部分网站需重新加载", True, "safe"),
    ("chrome_cache", "Chrome 浏览器缓存", [
        r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Cache",
        r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Code Cache",
        r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\GPUCache",
    ], "网页缓存", True, "safe"),
    ("firefox_cache", "Firefox 浏览器缓存", [
        r"%LOCALAPPDATA%\Mozilla\Firefox\Profiles",
    ], "网页缓存", True, "safe"),
    ("recycle", "回收站", ["__RECYCLE__"], "回收站中的文件", True, "safe"),
    ("win_old", "旧系统备份 Windows.old", [r"C:\Windows.old"], "系统升级前的旧系统，通常 10GB+", False, "careful"),
    ("hiberfil", "休眠文件", ["__HIBERFIL__"], "hiberfil.sys，关闭休眠可释放", False, "careful"),
    ("pagefile", "虚拟内存文件", ["__PAGEFILE__"], "pagefile.sys，不建议删除", False, "danger"),
    ("installer_cache", "安装包缓存", [
        r"%SystemRoot%\Installer\$PatchCache$",
        r"%ProgramData%\Package Cache",
    ], "软件安装缓存，清理后修复安装可能需重新下载", False, "careful"),
    ("nvidia_cache", "显卡驱动缓存", [
        r"%ProgramData%\NVIDIA Corporation\Downloader",
        r"%LOCALAPPDATA%\NVIDIA\DXCache",
        r"%LOCALAPPDATA%\NVIDIA\GLCache",
    ], "显卡着色器缓存和驱动安装包", True, "safe"),
    ("dx_cache", "DirectX 着色器缓存", [
        r"%LOCALAPPDATA%\D3DSCache",
        r"%LOCALAPPDATA%\AMD\DxCache",
    ], "游戏着色器缓存，清理后首次进游戏略慢", True, "safe"),
    ("temp_inet", "系统安装临时文件", [
        r"C:\$Windows.~BT", r"C:\$Windows.~WS", r"C:\$WINDOWS.~BT",
    ], "系统升级残留", False, "careful"),
]

# 大文件扫描阈值
LARGE_FILE_MB = 100
HUGE_FILE_MB = 1024

# 不允许删除的系统关键路径（保护）
PROTECTED_PATHS = [
    r"c:\windows\system32",
    r"c:\windows\syswow64",
    r"c:\windows\winsxs",
    r"c:\windows\system",
    r"c:\program files\windows",
    r"c:\users\default",
    r"c:\windows\font",
    r"c:\windows\assembly",
    r"c:\windows\servicing",
]


# ============================================================
# 四、文件类型归类（磁盘盘点用）
# ============================================================
FILE_TYPE_MAP = {
    "视频": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".ts", ".rmvb",
             ".webm", ".m4v", ".mpg", ".mpeg", ".3gp", ".rm", ".vob", ".m2ts"],
    "图片": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff",
             ".psd", ".raw", ".heic", ".svg", ".ico", ".cr2", ".nef", ".arw"],
    "文档": [".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".pdf", ".txt",
             ".md", ".csv", ".rtf", ".odt", ".epub", ".mobi", ".wps", ".et", ".dps"],
    "压缩包": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso",
               ".cab", ".tgz", ".lz", ".zst"],
    "安装包": [".msi", ".msix", ".appx", ".apk", ".dmg", ".pkg"],
    "可执行程序": [".exe", ".dll", ".sys", ".msi_", ".scr", ".com", ".bat",
                   ".cmd", ".ps1", ".vbs", ".jar"],
    "音频": [".mp3", ".flac", ".wav", ".aac", ".m4a", ".ogg", ".wma", ".ape",
             ".opus", ".aiff"],
    "代码工程": [".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h",
                 ".hpp", ".cs", ".go", ".rs", ".rb", ".php", ".swift", ".kt",
                 ".html", ".css", ".scss", ".json", ".xml", ".yaml", ".yml",
                 ".sql", ".sh", ".vue", ".sln", ".csproj", ".gradle"],
    "游戏资源": [".pak", ".bundle", ".assets", ".uasset", ".umap", ".vpk",
                 ".wad", ".bsa", ".ba2", ".rpa", ".arc", ".big", ".dat_"],
    "字体": [".ttf", ".otf", ".woff", ".woff2", ".fon", ".ttc"],
    "虚拟机/磁盘镜像": [".vmdk", ".vdi", ".vhdx", ".vhd", ".qcow2", ".ova", ".ovf"],
}

# 扩展名 → 分类，展开成字典方便查
EXT_TO_TYPE = {}
for _label, _exts in FILE_TYPE_MAP.items():
    for _e in _exts:
        EXT_TO_TYPE[_e] = _label
