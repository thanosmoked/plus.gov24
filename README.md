# 민증 제작 서비스 v2.0

텔레그램 봇 기반 자동 결제 시스템을 갖춘 민증 제작 서비스입니다.

## 🌟 주요 기능

### 💳 자동 결제 시스템
- 라이센스 자판기 (1일권/7일권/30일권)
- 입금 증명 스크린샷 업로드
- 관리자 승인/거절 시스템
- 자동 라이센스 재고 충전

### 🆔 민증 제작 기능
- 6단계 정보 입력 (이름, 주민번호, 주소, 발급일자, 발급지역, 증명사진)
- 웹 링크 자동 생성
- 민증 수정 기능 (모든 필드 개별 수정 가능)

### 👨‍💼 관리자 기능
- 결제 승인/거절
- 거절 시 사유 입력
- 승인 대기 목록 확인
- 재고 현황 조회
- 수동 재고 충전

## 📋 필수 요구사항

- Python 3.7 이상
- 텔레그램 봇 토큰 ([@BotFather](https://t.me/BotFather)에서 발급)
- 텔레그램 유저 ID ([@userinfobot](https://t.me/userinfobot)에서 확인)

## 🚀 빠른 시작

### 1. 패키지 설치
```bash
pip install -r requirements.txt
```

### 2. 설정 파일 수정
`config.py` 파일을 열어 다음 항목을 수정하세요:

```python
# 텔레그램 봇 토큰 (필수)
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"

# 관리자 텔레그램 ID (필수)
OWNER_ID = YOUR_TELEGRAM_USER_ID

# 은행 정보
BANK_INFO = {
    "bank_name": "카카오뱅크",
    "account_number": "1234-56-7891011",
    "account_holder": "홍길동"
}
```

### 3. 실행

**Windows:**
```bash
QUICKSTART.bat
```
또는
```bash
python run.py
```

**Linux/Mac:**
```bash
chmod +x START.sh
./START.sh
```

## 📁 프로젝트 구조

```
.
├── run.py                  # 통합 실행 파일 (메인)
├── config.py              # 설정 파일 ⚠️ 수정 필요
├── database_schema.py     # DB 스키마 및 초기화
├── service_bot.py         # 텔레그램 봇 메인 로직
├── web.py                 # Flask 웹 서버
├── requirements.txt       # 필수 패키지 목록
├── QUICKSTART.bat        # Windows 실행 파일
├── START.bat             # Windows 실행 파일 (대체)
├── START.sh              # Linux/Mac 실행 파일
├── DB/
│   ├── database.db       # SQLite 데이터베이스
│   ├── saved_images/     # 민증 이미지 저장
│   └── payment_proofs/   # 입금 증명 이미지
├── static/
│   └── css/              # 웹 스타일시트
└── templates/
    ├── sex.html          # 민증 표시 페이지
    └── error.html        # 에러 페이지
```

## 🗄️ 데이터베이스 구조

- **admins**: 관리자 목록
- **users**: 사용자 정보
- **production_users**: 민증 정보
- **license_store**: 라이센스 재고
- **payment_requests**: 결제 요청 목록
- **purchase_history**: 구매 이력
- **user_licenses**: 사용자별 라이센스

## 🌐 배포 (Render.com)

### 환경 변수 설정
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
OWNER_ID=your_telegram_id
DOMAIN=https://your-app.onrender.com
PORT=8080
```

### 배포 명령어
```bash
python run.py
```

## 📝 라이센스

이 프로젝트는 비공개 프로젝트입니다. 무단 복제 및 배포를 금지합니다.

## 🔒 보안 주의사항

- `config.py`에 실제 토큰을 커밋하지 마세요
- `.env` 파일을 사용하거나 환경 변수로 민감한 정보를 관리하세요
- `DB/database.db`는 절대 공개하지 마세요
- 프로덕션 환경에서는 HTTPS를 사용하세요

## 📞 문의

이슈가 있으면 GitHub Issues에 등록해주세요.

---

**Made with ❤️ for secure ID service**
