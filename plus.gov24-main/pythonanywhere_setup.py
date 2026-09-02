"""
PythonAnywhere 배포 설정 스크립트
======================================
무료 플랜 조건 (2025년 기준):
- 신용카드 불필요
- 웹앱 1개 (Flask/Django) 상시 운영
- SQLite DB 무제한 수정 가능 (512MB 디스크 내)
- 월 CPU 제한 있음 (과부하 시 슬로우다운, 차단 없음)
- 3개월 미접속 시 웹앱 일시정지 → 콘솔에서 재활성화하면 됨

사용법:
1. https://www.pythonanywhere.com 에서 무료 계정 생성
2. Dashboard → Bash Console 열기
3. 아래 명령 실행:
   git clone https://github.com/YOUR_USERNAME/plus.gov24.git
   cd plus.gov24
   pip3.10 install -r requirements.txt --user
   python pythonanywhere_setup.py

주의: PythonAnywhere 무료 플랜은 텔레그램 외부 API 호출이 제한됨
      → telegram API (api.telegram.org) 은 허용 도메인에 포함되어 있음
"""

import os
import sys

# PythonAnywhere 기본 경로
BASE_DIR = os.path.expanduser("~/plus.gov24")
DATA_DIR = os.path.expanduser("~/mysite_data")

def setup():
    print("PythonAnywhere 배포 설정 시작...")

    # 1. 데이터 디렉토리 생성 (DB 영구 보존용)
    os.makedirs(os.path.join(DATA_DIR, "saved_images"), exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, "payment_proofs"), exist_ok=True)
    print(f"  DB 디렉토리 생성: {DATA_DIR}")

    # 2. .env 파일 생성 안내
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_path):
        env_content = f"""TELEGRAM_TOKEN=여기에_토큰_입력
OWNER_ID=여기에_오너ID_입력
DOMAIN=https://YOUR_USERNAME.pythonanywhere.com
BANK_NAME=카카오페이 익명 송금
BANK_ACCOUNT=https://qr.kakaopay.com/FMN5EdnTj
BANK_HOLDER=ㅂㅈㅁ
REQUIRED_CHANNEL_ID=@weeminnotice
DB_PATH={DATA_DIR}/database.db
IMAGES_PATH={DATA_DIR}/saved_images
PROOFS_PATH={DATA_DIR}/payment_proofs
PORT=8080
"""
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(env_content)
        print(f"  .env 파일 생성: {env_path}")
        print("  ⚠️  .env 파일에서 TELEGRAM_TOKEN, OWNER_ID, DOMAIN 을 실제 값으로 수정하세요!")
    else:
        print(f"  .env 파일 이미 존재: {env_path}")

    # 3. WSGI 파일 내용 출력 (PythonAnywhere 웹앱 설정에 붙여넣기)
    username = os.environ.get("USER", "YOUR_USERNAME")
    wsgi_content = f"""
# ============================================================
# PythonAnywhere WSGI 설정
# Web 탭 → WSGI configuration file 에 아래 내용 붙여넣기
# ============================================================
import sys
import os

# 환경변수 로드
from dotenv import load_dotenv
load_dotenv('/home/{username}/plus.gov24/.env')

# 앱 경로 추가
path = '/home/{username}/plus.gov24'
if path not in sys.path:
    sys.path.insert(0, path)

# DB 초기화
from database_schema import init_database, refill_license_stock
init_database()
refill_license_stock()

# Flask 앱 가져오기
from web import app as application

# 텔레그램 봇은 별도 스케줄 태스크로 실행
# (PythonAnywhere → Tasks 탭에서 아래 명령을 Always-on task로 등록)
# python /home/{username}/plus.gov24/telegram_bot_runner.py
"""

    print("\n" + "="*60)
    print("WSGI 파일 내용 (PythonAnywhere Web 탭에 붙여넣기):")
    print("="*60)
    print(wsgi_content)
    print("="*60)

    # 4. 텔레그램 봇 러너 스크립트 생성 (Always-on task용)
    runner_path = os.path.join(BASE_DIR, "telegram_bot_runner.py")
    runner_content = f"""#!/usr/bin/env python3
\"\"\"
PythonAnywhere Always-on Task용 텔레그램 봇 러너
Tasks 탭 → Command: python /home/{username}/plus.gov24/telegram_bot_runner.py
\"\"\"
import os
import sys
from dotenv import load_dotenv

load_dotenv('/home/{username}/plus.gov24/.env')
sys.path.insert(0, '/home/{username}/plus.gov24')

from database_schema import init_database, refill_license_stock
init_database()
refill_license_stock()

import service_bot
service_bot.main()
"""
    with open(runner_path, "w", encoding="utf-8") as f:
        f.write(runner_content)
    print(f"\n  텔레그램 봇 러너 생성: {runner_path}")
    print("\n배포 설정 완료!")
    print("\n다음 단계:")
    print("  1. .env 파일 수정 (TELEGRAM_TOKEN, OWNER_ID, DOMAIN)")
    print("  2. PythonAnywhere → Web 탭 → Add new web app → Flask")
    print("  3. WSGI 파일에 위 내용 붙여넣기")
    print("  4. Tasks 탭 → Always-on task 등록 (봇 실행)")
    print("  5. Web 탭 → Reload 클릭")

if __name__ == "__main__":
    setup()
