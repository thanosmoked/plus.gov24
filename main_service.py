# main_service.py - 웹 서버 단독 실행
import os
from web import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"🌐 웹 서버 시작: http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
