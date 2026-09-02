# 🚀 빠른 시작 가이드

## 1️⃣ 텔레그램 봇 토큰 받기 (2분)

1. 텔레그램 앱 열기
2. **@BotFather** 검색 및 대화 시작
3. `/newbot` 입력
4. 봇 이름 입력 (예: "민증제작서비스")
5. 봇 사용자명 입력 (예: "minjung_service_bot") - 반드시 `bot`으로 끝나야 함
6. 받은 토큰 복사 (예: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

## 2️⃣ 본인 텔레그램 ID 확인 (1분)

1. 텔레그램에서 **@userinfobot** 검색
2. 봇에게 아무 메시지 전송
3. `Id` 숫자 복사 (예: 1234567890)

## 3️⃣ config.py 수정 (1분)

파일 열기: `config.py`

```python
# 받은 봇 토큰 입력
TELEGRAM_TOKEN = "여기에_받은_토큰_붙여넣기"

# 본인 ID 입력 (숫자만, 따옴표 없이)
OWNER_ID = 여기에_본인ID_입력

# 은행 정보 (고객이 입금할 계좌)
BANK_INFO = {
    "bank_name": "카카오뱅크",        # 은행명 변경
    "account_number": "3333-01-1234567",  # 계좌번호 변경
    "account_holder": "홍길동"        # 예금주 변경
}
```

## 4️⃣ 실행 (10초)

```bash
python main_service.py
```

끝! 🎉

## ✅ 확인사항

1. ✅ 데이터베이스 초기화 완료
2. ✅ 라이센스 재고 150개 생성 (1일권 50개, 7일권 50개, 30일권 50개)
3. ✅ 웹 서버 시작 (http://localhost:8080)
4. ✅ 텔레그램 봇 시작

## 📱 봇 테스트

1. 텔레그램에서 생성한 봇 검색
2. `/start` 입력
3. 메인 메뉴 확인

---

## 🎯 사용 흐름

### 👤 일반 사용자
1. 🛒 라이센스 구매 → 기간 선택
2. 💰 계좌로 입금
3. 📸 입금 증빙 스크린샷 업로드
4. ⏳ 관리자 승인 대기
5. ✅ 승인 후 라이센스 활성화
6. 🆕 민증 제작 (6단계 정보 입력)
7. 🔗 웹 링크로 민증 확인
8. ✏️ 필요시 민증 수정

### 👨‍💼 관리자
1. 🔔 결제 요청 알림 수신
2. 📸 입금 증빙 확인
3. ✅ 승인 또는 ❌ 거절 (사유 입력)
4. 📊 재고 관리 (자동 충전)
5. 👥 관리자 계정 관리

---

## 🆘 문제 발생 시

### 봇이 응답 안 함
```bash
# 1. DB 재초기화
python database_schema.py

# 2. 봇 재시작
python main_service.py
```

### 토큰 오류
- config.py에서 `TELEGRAM_TOKEN`을 다시 확인
- 따옴표 안에 토큰 전체를 입력했는지 확인

### 권한 오류
- config.py의 `OWNER_ID`가 본인 ID인지 확인
- @userinfobot에서 확인한 숫자와 일치하는지 확인

---

## 📊 가격 변경

config.py에서 수정:

```python
LICENSE_PRICE_1DAY = 5000      # 1일권 가격
LICENSE_PRICE_7DAY = 15000     # 7일권 가격
LICENSE_PRICE_30DAY = 40000    # 30일권 가격
```

변경 후 재시작하면 자동 반영됩니다.

---

## 🌐 호스팅 (Render.com)

### 1단계: GitHub 업로드
```bash
git init
git add .
git commit -m "Initial commit"
git push origin main
```

### 2단계: Render.com 설정
1. https://render.com 접속
2. "New +" → "Web Service"
3. GitHub 연결
4. 환경변수 입력:
   - `TELEGRAM_BOT_TOKEN`: 봇 토큰
   - `OWNER_ID`: 본인 ID
   - `DOMAIN`: `https://your-app-name.onrender.com`
5. Start Command: `python main_service.py`
6. Deploy 클릭

### 3단계: config.py 업데이트
```python
domain = "https://your-app-name.onrender.com"
```

완료! 🎉

---

**제작: 민증 제작 서비스 v2.0**
