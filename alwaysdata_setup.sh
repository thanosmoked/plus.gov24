#!/bin/bash
# ============================================================
# Alwaysdata 무료 플랜 배포 스크립트
# 무료 조건: 신용카드 불필요, 슬립 없음, 24/7 상시 운영
# SSH + Services 기능으로 봇 & Flask 웹 동시 운영 가능
# https://www.alwaysdata.com
# ============================================================
# 사용법:
#   1. https://www.alwaysdata.com 에서 무료 계정 생성
#   2. 관리 패널 → SSH 접속 정보 확인
#   3. SSH 접속: ssh [계정명]@ssh-[계정명].alwaysdata.net
#   4. 아래 명령 실행:
#      chmod +x alwaysdata_setup.sh && ./alwaysdata_setup.sh
# ============================================================

set -e

ACCOUNT=$(whoami)
HOME_DIR="/home/$ACCOUNT"
APP_DIR="$HOME_DIR/plus.gov24"
DATA_DIR="$HOME_DIR/data"

echo "=============================="
echo " Alwaysdata 배포 설정 시작"
echo " 계정: $ACCOUNT"
echo "=============================="

# 1. 데이터 디렉토리 생성 (DB 영구 보존)
mkdir -p "$DATA_DIR/saved_images" "$DATA_DIR/payment_proofs"
echo "  DB 디렉토리 생성: $DATA_DIR"

# 2. pip 패키지 설치 (--user 플래그로 권한 없이 설치)
echo "  패키지 설치 중..."
pip3 install -r "$APP_DIR/requirements.txt" --user --quiet
echo "  패키지 설치 완료"

# 3. .env 파일 생성
ENV_FILE="$APP_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    cat > "$ENV_FILE" << EOF
TELEGRAM_TOKEN=여기에_토큰_입력
OWNER_ID=여기에_오너ID_입력
DOMAIN=https://${ACCOUNT}.alwaysdata.net
BANK_NAME=카카오페이 익명 송금
BANK_ACCOUNT=https://qr.kakaopay.com/FMN5EdnTj
BANK_HOLDER=ㅂㅈㅁ
REQUIRED_CHANNEL_ID=@weeminnotice
DB_PATH=${DATA_DIR}/database.db
IMAGES_PATH=${DATA_DIR}/saved_images
PROOFS_PATH=${DATA_DIR}/payment_proofs
PORT=8080
EOF
    echo "  .env 생성 완료 → 값 수정 필요: $ENV_FILE"
else
    echo "  .env 이미 존재: $ENV_FILE"
fi

echo ""
echo "=============================="
echo " 설치 완료!"
echo ""
echo " 다음 단계:"
echo " 1. .env 파일 수정:"
echo "    nano $ENV_FILE"
echo ""
echo " 2. Alwaysdata 관리 패널 설정:"
echo "    [웹사이트] → 사이트 추가 → 아래 참고"
echo "    [서비스]   → 서비스 추가 → 아래 참고"
echo ""
echo " 웹사이트 설정 (Flask):"
echo "    타입: User program"
echo "    명령: $HOME_DIR/.local/bin/gunicorn --chdir $APP_DIR --bind 0.0.0.0:%(PORT)s web:app"
echo ""
echo " 서비스 설정 (텔레그램 봇 - 자동 재시작):"
echo "    명령: /usr/bin/env bash -c 'cd $APP_DIR && source .env 2>/dev/null; python3 service_bot_runner.py'"
echo "=============================="
