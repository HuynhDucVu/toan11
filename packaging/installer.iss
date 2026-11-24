; Bộ cài đặt Windows (Inno Setup 6) cho bản «thư mục» (PyInstaller --onedir).
; Cài cho riêng người dùng hiện tại (không cần quyền quản trị) vào %LOCALAPPDATA%\Programs\NganHangDe.
; Dựng: iscc /DAppVersion=0.14.0 packaging\installer.iss   (cần dist\NganHangDe\ từ bước --onedir)
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6C1C3B2E-8A61-4C59-9B0E-3F5A2D9E7C41}
AppName=Ngân hàng đề thi
AppVersion={#AppVersion}
AppPublisher=Ngân hàng đề thi
DefaultDirName={localappdata}\Programs\NganHangDe
DefaultGroupName=Ngân hàng đề thi
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=NganHangDe_CaiDat
SetupIconFile=..\nganhangde\assets\app.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\NganHangDe.exe

[Tasks]
Name: "desktopicon"; Description: "Tạo biểu tượng trên màn hình"; GroupDescription: "Biểu tượng:"

[Files]
Source: "..\dist\NganHangDe\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Ngân hàng đề thi"; Filename: "{app}\NganHangDe.exe"
Name: "{group}\Gỡ cài đặt"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Ngân hàng đề thi"; Filename: "{app}\NganHangDe.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\NganHangDe.exe"; Description: "Mở phần mềm"; Flags: nowait postinstall skipifsilent
