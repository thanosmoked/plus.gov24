# test_telegram.py - 텔레그램 봇 설정 테스트
import os
import sys

print("=" * 60)
print("텔레그램 봇 설정 테스트")
print("=" * 60)

# 1. config.py 로드 테스트
try:
    import config
    print("✅ config.py 로드 성공")
except Exception as e:
    print(f"❌ config.py 로드 실패: {e}")
    sys.exit(1)

# 2. 텔레그램 토큰 확인
telegram_token = getattr(config, "TELEGRAM_TOKEN", None)
if not telegram_token or telegram_token == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
    print("❌ 텔레그램 봇 토큰이 설정되지 않았습니다!")
    print("   config.py에서 TELEGRAM_TOKEN을 설정하거나")
    print("   환경변수 TELEGRAM_BOT_TOKEN을 설정하세요.")
    print("")
    print("   텔레그램 봇 토큰 받는 방법:")
    print("   1. 텔레그램에서 @BotFather 봇 찾기")
    print("   2. /newbot 명령어로 새 봇 생성")
    print("   3. 받은 토큰을 config.py에 입력")
else:
    print(f"✅ 텔레그램 토큰: {telegram_token[:10]}... (앞 10자만 표시)")

# 3. OWNER_ID 확인
owner_id = getattr(config, "OWNER_ID", None)
if owner_id:
    print(f"✅ OWNER_ID: {owner_id}")
else:
    print("⚠️  OWNER_ID가 설정되지 않았습니다.")
    print("   자신의 텔레그램 유저 ID를 확인하려면:")
    print("   1. 텔레그램에서 @userinfobot 봇 찾기")
    print("   2. 봇에게 아무 메시지 전송")
    print("   3. 받은 ID를 config.py에 입력")

# 4. DB 경로 확인
db_path = getattr(config, "db_path", "DB/database.db")
print(f"✅ DB 경로: {db_path}")

# 5. 도메인 확인
domain = getattr(config, "domain", "")
print(f"✅ 도메인: {domain}")

# 6. python-telegram-bot 패키지 확인
try:
    import telegram
    print(f"✅ python-telegram-bot 버전: {telegram.__version__}")
except ImportError:
    print("❌ python-telegram-bot이 설치되지 않았습니다!")
    print("   설치 방법: pip install python-telegram-bot==21.9")
    sys.exit(1)

# 7. 데이터베이스 테이블 확인
try:
    import sqlite3
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cur.fetchall()]
        conn.close()
        print(f"✅ 데이터베이스 테이블: {', '.join(tables)}")
    else:
        print("⚠️  데이터베이스 파일이 없습니다. (처음 실행시 자동 생성됩니다)")
except Exception as e:
    print(f"⚠️  데이터베이스 확인 중 오류: {e}")

print("")
print("=" * 60)
if telegram_token and telegram_token != "YOUR_TELEGRAM_BOT_TOKEN_HERE":
    print("✅ 모든 설정이 완료되었습니다!")
    print("   봇 실행: python telegram_bot.py")
    print("   또는 웹+봇: python main_telegram.py")
else:
    print("⚠️  텔레그램 토큰을 먼저 설정해주세요!")
print("=" * 60)
