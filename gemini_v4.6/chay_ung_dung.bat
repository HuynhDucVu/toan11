@echo off
chcp 65001 >nul
set PYCMD=python
py -3.12 --version >nul 2>&1
if %errorlevel% equ 0 set PYCMD=py -3.12

echo [1/2] Kiem tra va cai dat thu vien (%PYCMD%)...
%PYCMD% -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [LOI] Khong cai duoc thu vien. Hay cai Python 3.12 (tich Add to PATH) tai python.org.
    pause
    exit /b 1
)
echo [2/2] Dang mo toan11 v1.0 (Ban 0.9.0 + Day du MyLT 2026)...
%PYCMD% run_gui.py
