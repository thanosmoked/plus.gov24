# main.py
import os
import threading
import time
import traceback

# Import bot and web modules
import bot    # bot.py 파일
from web import app  # web.py의 Flask app 가져오기

# ---------- Discord bot background starter ----------
def _start_discord_bot_in_thread():
    try:
        token = getattr(bot, "TOKEN", None)
        if not token:
            print("ERROR: DISCORD_TOKEN 환경변수가 설정되어 있지 않습니다. 봇을 시작하지 않습니다.")
            return

        def _run():
            try:
                print("Discord bot: starting bot.run() ...")
                # bot.bot은 bot.py에서 생성된 commands.Bot 인스턴스여야 합니다.
                bot.bot.run(token)
            except Exception:
                print("Discord bot: 예외 발생(스택트레이스 출력)")
                traceback.print_exc()

        t = threading.Thread(target=_run, name="discord-bot-thread", daemon=True)
        t.start()
        print("✅ Discord bot thread started.")
    except Exception:
        print("Discord bot: starter failed")
        traceback.print_exc()

# 환경변수로 자동 시작 여부 제어 (기본: 자동 시작)
if os.environ.get("RUN_DISCORD_AT_IMPORT", "1") == "1":
    _start_discord_bot_in_thread()

# if you want to run locally with `python main.py`
if __name__ == "__main__":
    print("=" * 50)
    print("🚀 봇 + 웹 서버 실행 중...")
    print("=" * 50)
    port = int(os.environ.get("PORT", 10000))
    print(f"📡 웹 서버: http://localhost:{port}")
    print("=" * 50)
    app.run(host="0.0.0.0", port=port, debug=False)

