@echo off
chcp 65001 >nul
cls

echo ======================================================================
echo                     민증 제작 서비스 v2.0
echo ======================================================================
echo.
echo [1/3] Python 확인 중...

C:\Users\parkc\AppData\Local\Programs\Python\Python310\python.exe --version
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Python이 설치되지 않았거나 경로가 잘못되었습니다.
    echo.
    pause
    exit /b 1
)

echo ✅ Python 확인 완료
echo.
echo [2/3] 필수 패키지 확인 중...
C:\Users\parkc\AppData\Local\Programs\Python\Python310\python.exe -m pip list | findstr "flask telegram" >nul
if %ERRORLEVEL% NEQ 0 (
    echo ⚠️  필수 패키지가 설치되지 않았을 수 있습니다.
    echo    자동 설치를 시도합니다...
    C:\Users\parkc\AppData\Local\Programs\Python\Python310\python.exe -m pip install -r requirements.txt
)

echo ✅ 패키지 확인 완료
echo.
echo [3/3] 서비스 시작 중...
echo.
echo ======================================================================
echo.

C:\Users\parkc\AppData\Local\Programs\Python\Python310\python.exe run.py

pause
