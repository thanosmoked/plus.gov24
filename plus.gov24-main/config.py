# config.py
import os

# ========== .env 파일 자동 로드 (로컬/PythonAnywhere 등) ========== #
try:
    from dotenv import load_dotenv
    _env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(_env_file):
        load_dotenv(_env_file)
except ImportError:
    pass  # python-dotenv 없으면 환경변수 직접 주입 방식 사용

# ========== 봇 토큰 ========== #
TOKEN = ""
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# ========== DB 경로 (멀티 플랫폼 자동 감지) ========== #
#
#  우선순위:
#  1. 환경변수 DB_PATH / IMAGES_PATH / PROOFS_PATH (명시적 지정 최우선)
#  2. Railway  → RAILWAY_VOLUME_MOUNT_PATH  (ex. /data)
#  3. Oracle Cloud / Docker → /data 디렉토리 존재 여부
#  4. Alwaysdata → ~/data
#  5. 기본값 → 프로젝트 내 DB/ 폴더 (로컬 개발용)
#
def _resolve_base() -> str:
    # 1. Railway 볼륨
    railway_vol = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
    if railway_vol and os.path.isdir(railway_vol):
        return railway_vol

    # 2. /data 볼륨 (Oracle Cloud systemd, Docker 등)
    if os.path.isdir("/data"):
        return "/data"

    # 3. Alwaysdata → ~/data
    home = os.path.expanduser("~")
    ad_data = os.path.join(home, "data")
    if os.path.isdir(ad_data):
        return ad_data

    # 4. 로컬 개발 기본값
    return os.path.join(os.path.dirname(__file__), "DB")

_base = _resolve_base()

db_path     = os.getenv("DB_PATH",     os.path.join(_base, "database.db"))
images_path = os.getenv("IMAGES_PATH", os.path.join(_base, "saved_images"))
proofs_path = os.getenv("PROOFS_PATH", os.path.join(_base, "payment_proofs"))

# DB 디렉토리가 없으면 자동 생성
for _dir in [images_path, proofs_path]:
    os.makedirs(_dir, exist_ok=True)

# ========== 도메인 ========== #
domain = os.getenv("DOMAIN", "https://gov24.up.railway.app")

# ========== 가격 ========== #
LICENSE_PRICE    = 5000   # 영구권 일반 가격
DIST_PRICE       = 3500   # 총판 판매 가격
DIST_BUY_PRICE   = 30000  # 총판 권한 구매 가격

# ========== 기본 입금 계좌 (총판 없는 사용자용) ========== #
BANK_INFO = {
    "bank_name":    os.getenv("BANK_NAME",    "카카오페이 익명 송금"),
    "account_number": os.getenv("BANK_ACCOUNT", "https://qr.kakaopay.com/FMN5EdnTj"),
    "account_holder": os.getenv("BANK_HOLDER",  "ㅂㅈㅁ"),
}

# ========== 채널 필수 가입 설정 ========== #
REQUIRED_CHANNEL_ID = os.getenv("REQUIRED_CHANNEL_ID", "@weeminnotice")  # 공개채널 username 또는 채널 ID
REQUIRED_CHANNEL_LINK = "https://t.me/weeminnotice"

# ========== 기타 ========== #
AUTO_LICENSE_STOCK = 200
ADMIN_NOTIFICATION = True
