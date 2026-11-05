; CleanMaster 安装包生成脚本（Inno Setup）
; 用法：安装 Inno Setup 后执行
;   ISCC.exe installer.iss
; 产物：dist_installer\CleanMaster-Setup-2.0.0.exe

[Setup]
AppId={{8E4A21C7-6B3D-4F2E-9A18-CLEANMASTER01}
AppName=CleanMaster
AppVersion=2.0.0
AppPublisher=CleanMaster
DefaultDirName={autopf}\CleanMaster
DefaultGroupName=CleanMaster
UninstallDisplayIcon={app}\CleanMaster.exe
OutputDir=dist_installer
OutputBaseFilename=CleanMaster-Setup-2.0.0
Compression=lzma2
SolidCompression=yes
; 非管理员也能装（装到用户目录时）；允许选择
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern
SetupIconFile=build_assets\app.ico

[Languages]
Name: "chinese"; MessagesFile: "ChineseSimplified.isl"

[Files]
Source: "dist\CleanMaster.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; 开始菜单 + 桌面快捷方式（默认勾选桌面）
Name: "{group}\CleanMaster"; Filename: "{app}\CleanMaster.exe"
Name: "{group}\卸载 CleanMaster"; Filename: "{uninstallexe}"
Name: "{autodesktop}\CleanMaster"; Filename: "{app}\CleanMaster.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项："; Flags: checkedonce

[Run]
Filename: "{app}\CleanMaster.exe"; Description: "立即运行 CleanMaster"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 卸载时清理运行时数据目录
Type: filesandordirs; Name: "{app}\CleanMasterData"
