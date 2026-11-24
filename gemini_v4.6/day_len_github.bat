@echo off
chcp 65001 >nul
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo [LOI] May chua cai Git. Tai tai: https://git-scm.com/download/win hoac dung GitHub Desktop.
    pause
    exit /b 1
)
set REPO_URL=%~1
if "%REPO_URL%"=="" (
    set /p REPO_URL=Nhap link GitHub repo (VD: https://github.com/HuynhDucVu/toan11.git): 
)
if "%REPO_URL%"=="" (
    echo Chua nhap link repo. Da huy.
    pause
    exit /b 1
)
if not exist ".git" (
    git init
    git branch -M main
)
git add .
git commit -m "Nang cap toan11 v1.0 chuan MyLT 2026 toan dien"
git remote remove origin >nul 2>&1
git remote add origin "%REPO_URL%"
git push -u origin main
echo.
echo [XONG] Mo GitHub -> tab Actions -> tai NganHangDe-Windows-v1.0.
pause
