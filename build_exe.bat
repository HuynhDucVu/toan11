@echo off
chcp 65001 >nul
REM ================================================================
REM  Đóng gói phần mềm Ngân hàng đề thi thành file NganHangDe.exe
REM  Yêu cầu: đã cài Python 3.10+ (python.org, tích "Add to PATH")
REM  Cách dùng: nhấp đúp file này. Kết quả: dist\NganHangDe.exe
REM ================================================================
cd /d "%~dp0"

if not exist .venv (
    echo [1/3] Tao moi truong ao .venv ...
    python -m venv .venv || goto :loi
)
call .venv\Scripts\activate.bat

echo [2/3] Cai thu vien PySide6, PyInstaller ...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements-dev.txt || goto :loi

echo [3/3] Dong goi bang PyInstaller ...
pyinstaller --noconfirm --clean --onefile --windowed ^
    --name NganHangDe ^
    --icon nganhangde\assets\app.ico ^
    --add-data "nganhangde/templates:nganhangde/templates" ^
    --add-data "nganhangde/assets:nganhangde/assets" ^
    --add-data "nganhangde/data:nganhangde/data" ^
    --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick --exclude-module PySide6.QtWebEngineCore ^
    --exclude-module tkinter ^
    run_gui.py || goto :loi

echo.
echo XONG! File chay: %cd%\dist\NganHangDe.exe
pause
exit /b 0

:loi
echo.
echo CO LOI xay ra, xem thong bao phia tren.
pause
exit /b 1
