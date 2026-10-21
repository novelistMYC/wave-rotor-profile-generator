; 波形转子 DXF 生成器 v2.0 —— Inno Setup 6 打包脚本
; 用法：ISCC.exe 本文件
; 说明：按“当前用户”安装（不弹 UAC），默认装到 %LOCALAPPDATA%\Programs\波形转子DXF生成器

#define AppName "波形转子 DXF 生成器"
#define AppVersion "2.0"
#define AppExeName "波形转子生成器.exe"
#define SrcDir "F:\工作文件\自研程序\wave-rotor-dxf-v2"
#define StageDir "F:\工作文件\自研程序\wave-rotor-dxf-v2\安装包"

[Setup]
AppId={{7C3E9A21-6B4D-4F18-9E5A-2D8C1B0F4A73}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=皿洋草
AppComments=等半径圆弧波形转子轮廓生成器，输出 DXF（R12）
DefaultDirName={localappdata}\Programs\波形转子DXF生成器
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=F:\工作文件\自研程序
OutputBaseFilename=波形转子DXF生成器_安装包_v{#AppVersion}
SetupIconFile={#SrcDir}\波形转子.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ShowLanguageDialog=no
AllowNoIcons=no

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务："

[Files]
Source: "{#SrcDir}\dist\波形转子生成器_v2.exe"; DestDir: "{app}"; DestName: "{#AppExeName}"; Flags: ignoreversion
Source: "{#StageDir}\使用说明.txt"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "{#SrcDir}\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "{#SrcDir}\波形转子.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\波形转子 DXF 生成器\波形转子 DXF 生成器"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\波形转子.ico"
Name: "{autoprograms}\波形转子 DXF 生成器\使用说明"; Filename: "{app}\使用说明.txt"
Name: "{autoprograms}\波形转子 DXF 生成器\卸载 波形转子 DXF 生成器"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\波形转子.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "立即运行 {#AppName}"; Flags: nowait postinstall skipifsilent

[Messages]
SetupAppTitle=安装
SetupWindowTitle=安装 - %1
ButtonBack=< 上一步
ButtonNext=下一步 >
ButtonInstall=安装
ButtonFinish=完成
ButtonCancel=取消
ButtonBrowse=浏览...
WelcomeLabel1=欢迎安装 [name]
WelcomeLabel2=安装程序将把 [name/ver] 安装到你的电脑。%n%n继续之前，建议先关闭其他正在运行的程序。
SelectDirLabel3=安装程序将把 [name] 安装到下面的文件夹。
SelectDirBrowseLabel=要继续请点「下一步」；想换文件夹请点「浏览」。
DiskSpaceMBLabel=至少需要 [mb] MB 可用磁盘空间。
SelectTasksDesc=要执行哪些附加任务？
SelectTasksLabel2=选择安装程序要执行的附加任务，然后点「下一步」。
ReadyLabel1=安装程序已准备好，即将开始安装 [name]。
ReadyLabel2a=点「安装」开始安装；想修改设置请点「上一步」。
ReadyLabel2b=点「安装」开始安装。
FinishedHeadingLabel=正在完成 [name] 安装
FinishedLabel=安装完成。桌面和开始菜单都已有快捷方式，双击即可使用。
WizardSelectTasks=附加任务
ReadyMemoTasks=附加任务：
ClickFinish=点「完成」退出安装程序。
ExitSetupTitle=退出安装
ExitSetupMessage=安装尚未完成，确定要退出吗？
