@echo off
chcp 65001 >nul
title 민증 제작 서비스

echo ========================================
echo    민증 제작 서비스 v2.0
echo ========================================
echo.

REM Python 경로 자동 감지
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    python run.py
) else (
    echo Python을 찾을 수 없습니다.
    echo Python이 설치되어 있는지 확인하고 PATH에 추가해주세요.
    echo.
    echo 또는 아래 명령어로 직접 실행하세요:
    echo C:\Users\parkc\AppData\Local\Programs\Python\Python310\python.exe run.py
)

pause
