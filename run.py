#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import threading
import traceback
import time
import asyncio

# ========== 1단계: 환경 확인 ========== #
print("[1/4] 환경 확인 중...")
for module in ['flask', 'telegram', 'sqlite3']:
    try:
        __import__(module)
        print(f"  OK: {module}")
    except ImportError:
        print(f"  ERROR: {module} not found")
        sys.exit(1)

# ========== 2단계: 설정 확인 ========== #
print("[2/4] 설정 확인 중...")
try:
    import config
    TOKEN = config.TELEGRAM_TOKEN
    if not TOKEN:
        print("  ERROR: TELEGRAM_TOKEN not set")
        sys.exit(1)
    print(f"  OK: Token configured, OWNER_ID={config.OWNER_ID}")
    print(f"  DB: {config.db_path}")
    print(f"  /data exists: {os.path.isdir('/data')}")
except Exception as e:
    print(f"  ERROR: {e}"); sys.exit(1)

# ========== 3단계: DB 초기화 ========== #
print("[3/4] DB 초기화 중...")
try:
    from database_schema import init_database, refill_license_stock
    init_database()
    refill_license_stock()
    print("  OK: DB ready")
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()
    sys.exit(1)

# ========== 4단계: Flask 먼저, 봇은 나중에 ========== #
print("[4/4] 서비스 시작 중...")

def run_bot():
    """Flask가 뜬 후 3초 뒤 봇 시작"""
    time.sleep(3)
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        import service_bot
        print("  BOT: starting...")
        service_bot.main()
    except Exception as e:
        if "Conflict" in str(e):
            print("  BOT ERROR: Another instance is running!")
        else:
            print(f"  BOT ERROR: {e}")
            traceback.print_exc()

# 봇을 데몬 스레드로 백그라운드 실행
bot_thread = threading.Thread(target=run_bot, daemon=True, name="bot")
bot_thread.start()

# Flask를 메인 스레드에서 즉시 실행 (Railway health check용)
try:
    from web import app
    port = int(os.environ.get("PORT", 8080))
    print(f"  OK: Web server on port {port}")
    print("=" * 50)
    print("All services starting!")
    print("=" * 50)
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False, threaded=True)
except KeyboardInterrupt:
    print("\nStopped.")
    sys.exit(0)
except Exception as e:
    print(f"ERROR: Flask failed: {e}")
    traceback.print_exc()
    sys.exit(1)
