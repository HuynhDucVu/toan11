@echo off
chcp 65001 >nul
set PYCMD=python
py -3.12 --version >nul 2>&1
if %errorlevel% equ 0 set PYCMD=py -3.12

echo [1/3] Cai dat thu vien (%PYCMD%)...
%PYCMD% -m pip install -r requirements.txt
if %errorlevel% neq 0 exit /b %errorlevel%

echo [2/3] Chay 5 bo kiem thu tu dong...
set QT_QPA_PLATFORM=offscreen
%PYCMD% -m pytest tests/test_extest_v33.py tests/test_shuffler_invariants.py tests/test_cv7991_cv1239.py tests/test_db_fts5_migration.py tests/test_converters_mock.py -v
if %errorlevel% neq 0 exit /b %errorlevel%

echo [3/3] Dong goi NganHangDe.exe (--onedir toi uu)...
%PYCMD% -m PyInstaller --noconfirm --clean NganHangDe.spec
if %errorlevel% neq 0 exit /b %errorlevel%

echo.
echo [THANH CONG] Mo tep chay tai: dist\NganHangDe\NganHangDe.exe
pause
