#!/usr/bin/env python3
"""
Alwaysdata Services 전용 봇 러너
- Alwaysdata 관리 패널 → 고급 → 서비스 → 명령어로 등록
- 크래시 시 Alwaysdata가 자동 재시작
- .env 파일 자동 로드
"""
import os
import sys

# .env 로드
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(env_path)
except ImportError:
    pass

# 경로 추가
sys.path.insert(0, os.path.dirname(__file__))

# DB 초기화
from database_schema import init_database, refill_license_stock
init_database()
refill_license_stock()

# 봇 실행
import service_bot
print("봇 시작...", flush=True)
service_bot.main()
