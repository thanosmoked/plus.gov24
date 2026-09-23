# main_telegram.py - 텔레그램 봇 + 웹 서버 통합 실행
import os
import threading
import traceback

# Import telegram bot and web modules
import telegram_bot
from web import app

# ---------- Telegram bot background starter ----------
def _start_telegram_bot_in_thread():
    try:
        token = getattr(telegram_bot, "TOKEN", None)
        if not token or token == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
            print("ERROR: TELEGRAM_BOT_TOKEN 환경변수가 설정되어 있지 않습니다.")
            print("config.py에서 TELEGRAM_TOKEN을 설정하거나 환경변수를 설정하세요.")
            return

        def _run():
            try:
                print("Telegram bot: starting...")
                telegram_bot.main()
            except Exception:
                print("Telegram bot: 예외 발생")
                traceback.print_exc()

        t = threading.Thread(target=_run, name="telegram-bot-thread", daemon=True)
        t.start()
        print("✅ Telegram bot thread started.")
    except Exception:
        print("Telegram bot: starter failed")
        traceback.print_exc()

# 환경변수로 자동 시작 여부 제어 (기본: 자동 시작)
if os.environ.get("RUN_TELEGRAM_AT_IMPORT", "1") == "1":
    _start_telegram_bot_in_thread()

# 로컬 실행용
if __name__ == "__main__":
    print("=" * 50)
    print("🚀 텔레그램 봇 + 웹 서버 실행 중...")
    print("=" * 50)
    port = int(os.environ.get("PORT", 10000))
    print(f"📡 웹 서버: http://localhost:{port}")
    print("=" * 50)
    app.run(host="0.0.0.0", port=port, debug=False)
