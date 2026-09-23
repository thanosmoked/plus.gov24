# main_service.py - 웹 서버 + 텔레그램 봇 통합 실행
import os
import threading
import traceback

# 모듈 임포트
import service_bot
from web import app

def start_telegram_bot_in_thread():
    """텔레그램 봇을 백그라운드 스레드에서 실행"""
    try:
        token = service_bot.TOKEN
        if not token or token == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
            print("⚠️  WARNING: TELEGRAM_BOT_TOKEN이 설정되지 않았습니다.")
            print("   봇을 시작하지 않습니다. config.py를 확인하세요.")
            return

        def run_bot():
            try:
                print("🤖 텔레그램 봇 스레드 시작...")
                service_bot.main()
            except Exception as e:
                print(f"❌ 텔레그램 봇 오류: {e}")
                traceback.print_exc()

        bot_thread = threading.Thread(target=run_bot, name="telegram-bot-thread", daemon=True)
        bot_thread.start()
        print("✅ 텔레그램 봇 스레드가 시작되었습니다.")
        
    except Exception as e:
        print(f"❌ 텔레그램 봇 시작 실패: {e}")
        traceback.print_exc()

# 환경변수로 자동 시작 여부 제어 (기본: 자동 시작)
if os.environ.get("RUN_TELEGRAM_AT_IMPORT", "1") == "1":
    start_telegram_bot_in_thread()

if __name__ == "__main__":
    print("=" * 70)
    print("🚀 민증 제작 서비스 시작")
    print("=" * 70)
    print("📡 웹 서버: Flask")
    print("🤖 텔레그램 봇: python-telegram-bot")
    print("=" * 70)
    
    # 포트 설정
    port = int(os.environ.get("PORT", 10000))
    
    print(f"\n🌐 웹 서버 주소: http://localhost:{port}")
    print("💡 Ctrl+C를 눌러 종료합니다.\n")
    print("=" * 70)
    
    # Flask 앱 실행 (메인 스레드에서 실행)
    app.run(host="0.0.0.0", port=port, debug=False)
