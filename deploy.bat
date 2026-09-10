@echo off
chcp 65001 > nul
echo ========================================================
echo  GMAIL INTELLIGENCE SYSTEM - GITHUB DEPLOYMENT SCRIPT
echo ========================================================
echo.

:: 1. Lay ten thu muc lam ten repo
for %%I in ("%CD%") do set "DIR_NAME=%%~nxI"
set "REPO_NAME=%DIR_NAME: =-%"
set "GITHUB_USER=nguyenquocminhtrading-design"
set "TARGET_URL=https://github.com/%GITHUB_USER%/%REPO_NAME%.git"

echo [1/5] Thong tin Repository:
echo     Thu muc hien tai : %DIR_NAME%
echo     Ten Repo GitHub  : %REPO_NAME%
echo     URL GitHub       : %TARGET_URL%
echo.

:: 2. Kiem tra .gitignore
if not exist .gitignore (
    echo [2/5] Tao .gitignore de bao ve secrets...
    (
        echo .env
        echo credentials.json
        echo token.json
        echo *.db
        echo __pycache__/
        echo .pytest_cache/
        echo .venv/
    ) > .gitignore
    echo     .gitignore da duoc tao.
) else (
    echo [2/5] .gitignore da ton tai - bo qua.
)

:: 3. Khoi tao Git repo neu chua co
if not exist .git (
    echo [3/5] Khoi tao Git repository...
    git init
    if errorlevel 1 (
        echo [LOI] Loi khi khoi tao git.
        pause
        exit /b 1
    )
    git branch -M main
) else (
    echo [3/5] Git repository da ton tai - bo qua.
)

:: 4. Kiem tra va tao Repo tren GitHub qua gh CLI neu chua co
echo [4/5] Kiem tra repository tren GitHub...
gh repo view %GITHUB_USER%/%REPO_NAME% >nul 2>&1
if errorlevel 1 (
    echo [INFO] Repo %GITHUB_USER%/%REPO_NAME% chua ton tai tren GitHub. Dang tu dong tao...
    gh repo create %GITHUB_USER%/%REPO_NAME% --public
    if errorlevel 1 (
        echo [LOI] Khong the tao repo tren GitHub qua gh CLI.
        pause
        exit /b 1
    )
    echo [OK] Da tao repo %GITHUB_USER%/%REPO_NAME% tren GitHub.
) else (
    echo [OK] Repo %GITHUB_USER%/%REPO_NAME% da ton tai tren GitHub.
)

:: Thiet lap hoac cap nhat remote origin
git remote get-url origin >nul 2>&1
if errorlevel 1 (
    git remote add origin %TARGET_URL%
) else (
    git remote set-url origin %TARGET_URL%
)

:: 5. Add, Commit va Push
echo.
echo [5/5] Them file vao Git staging va day len GitHub...
git add .
if errorlevel 1 (
    echo [LOI] Loi khi git add.
    pause
    exit /b 1
)

:: Kiem tra co gi de commit khong
git diff --cached --quiet
if not errorlevel 1 (
    echo [INFO] Khong co thay doi moi de commit. Bo qua commit.
    goto :push
)

set /p commitMsg="Nhap commit message (Enter de dung mac dinh 'Auto update'): "
if not defined commitMsg set "commitMsg=Auto update %REPO_NAME%"

git commit -m "%commitMsg%"
if errorlevel 1 (
    echo [LOI] Loi khi commit.
    pause
    exit /b 1
)

:push
echo.
echo Day code len GitHub (branch: main)...
git push -u origin main
if errorlevel 1 (
    echo.
    echo ========================================================
    echo [THAT BAI] Push that bai! Thu cac cau lenh sau:
    echo   1. Neu branch chua ton tai tren remote:
    echo      git push --set-upstream origin main
    echo   2. Neu bi conflict voi remote:
    echo      git pull --rebase origin main
    echo ========================================================
    pause
    exit /b 1
)

echo.
echo ========================================================
echo [THANH CONG] Da day len GitHub!
echo URL Repo: %TARGET_URL%
echo ========================================================

pause
