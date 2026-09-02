# 텔레그램 봇 설정 가이드

## 🚀 빠른 시작

### 1단계: 텔레그램 봇 토큰 받기

1. 텔레그램을 열고 **@BotFather** 검색
2. 대화 시작 후 `/newbot` 입력
3. 봇 이름 입력 (예: "민증제작봇")
4. 봇 사용자명 입력 (예: "minjung_maker_bot") - 반드시 `bot`으로 끝나야 함
5. 받은 토큰을 복사 (형식: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2단계: 자신의 텔레그램 유저 ID 확인

1. 텔레그램에서 **@userinfobot** 검색
2. 봇에게 아무 메시지 전송
3. 받은 `Id` 숫자 복사 (예: 123456789)

### 3단계: config.py 수정

```python
# config.py 파일 열기
TELEGRAM_TOKEN = "여기에_받은_토큰_붙여넣기"
OWNER_ID = 여기에_자신의_유저ID_입력  # 숫자만, 따옴표 없이
```

### 4단계: 패키지 설치

```bash
pip install python-telegram-bot==21.9
```

또는 전체 패키지 설치:
```bash
pip install -r requirements.txt
```

### 5단계: 봇 실행

**옵션 A: 텔레그램 봇만 실행**
```bash
python telegram_bot.py
```

**옵션 B: 웹 서버 + 텔레그램 봇 동시 실행 (권장)**
```bash
python main_telegram.py
```

## 📱 봇 사용 방법

### 1. 봇 시작하기
텔레그램에서 자신이 만든 봇을 검색하고 `/start` 입력

### 2. 등록하기
```
/register
```
- 봇에 등록되며 고유 ID를 받습니다

### 3. 관리자로서 라이센스 생성
```
/라센생성 30
```
- 30일짜리 라이센스 생성
- 생성된 코드를 복사

### 4. 유저에게 제작 권한 부여
```
/제작유저 <유저의_텔레그램_ID>
```
- 해당 유저에게 자동으로 안내 메시지 전송

### 5. 유저가 민증 제작하기

1. 봇과의 **프라이빗 채팅**에서 라이센스 코드 입력
2. 6단계 정보 입력:
   - 이름
   - 주민등록번호 (예: 040101-1234567)
   - 주소
   - 발급일자 (예: 2021.10.15)
   - 발급지역
   - 증명사진 (사진 파일 업로드)
3. 완료 후 웹 링크 수신

## 🎮 전체 명령어 목록

### 기본 명령어 (모든 유저)
```
/start          - 봇 시작 및 도움말
/register       - 유저 등록
/find           - 자신의 ID 확인
/aboutme <ID>   - 자신의 정보 확인
/cancel         - 현재 대화 취소
```

### 관리자 명령어
```
/라센생성 <일수>           - 라이센스 생성
/라센리스트                - 라이센스 목록 보기
/라센제거 <코드>           - 라이센스 삭제
/제작유저 <유저ID>         - 유저에게 제작 권한 부여
```

### 총관리자 전용 (OWNER_ID 유저만)
```
/관리자추가 <유저ID>       - 관리자 추가
/관리자제거 <유저ID>       - 관리자 제거
/관리자리스트              - 관리자 목록
```

## 🌐 호스팅 (Render.com)

### 1. GitHub에 업로드
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-repo-url>
git push -u origin main
```

### 2. Render.com 설정

1. [Render.com](https://render.com) 접속 및 로그인
2. "New +" → "Web Service" 선택
3. GitHub 레포지토리 연결
4. 설정:
   - **Name**: 원하는 이름
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python main_telegram.py`

5. Environment Variables 추가:
   ```
   TELEGRAM_BOT_TOKEN = 여기에_토큰_입력
   OWNER_ID = 여기에_유저ID_입력
   DOMAIN = https://your-app-name.onrender.com
   ```

6. "Create Web Service" 클릭

### 3. 배포 확인
- 로그에서 "✅ 텔레그램 봇이 시작되었습니다!" 메시지 확인
- 텔레그램 봇에서 `/start` 명령어로 테스트

## 🔧 문제 해결

### Q: 봇이 응답하지 않아요
**A:** 
1. 토큰이 올바른지 확인 (`config.py` 또는 환경변수)
2. `python test_telegram.py` 실행해서 설정 확인
3. 봇 실행 로그에서 에러 메시지 확인

### Q: "권한 없음" 에러가 나와요
**A:**
1. `/find` 명령어로 자신의 ID 확인
2. `config.py`의 `OWNER_ID`와 일치하는지 확인
3. `/관리자추가 <ID>` 명령어로 관리자 추가

### Q: 이미지가 웹에서 안 보여요
**A:**
1. `web.py` 파일이 최신 버전인지 확인
2. `DB/saved_images` 폴더 권한 확인
3. 호스팅 서비스에서 파일 저장 지원 여부 확인 (Render.com은 임시 저장만 지원)

### Q: 호스팅 후 이미지가 사라져요
**A:**
Render.com 무료 플랜은 영구 저장소를 제공하지 않습니다. 해결 방법:
1. AWS S3, Cloudinary 등 외부 저장소 사용
2. 유료 플랜으로 업그레이드
3. 이미지를 base64로 DB에 저장 (권장하지 않음)

## ⚠️ 주의사항

1. **법적 책임**: 위조 민증 제작은 불법입니다. 교육/테스트 목적으로만 사용하세요.
2. **개인정보 보호**: 수집된 정보는 반드시 안전하게 관리하세요.
3. **토큰 보안**: 봇 토큰을 절대 공개하지 마세요.
4. **데이터베이스 백업**: `DB/database.db` 파일을 정기적으로 백업하세요.

## 📞 추가 도움

- 텔레그램 봇 API 문서: https://core.telegram.org/bots/api
- python-telegram-bot 문서: https://docs.python-telegram-bot.org/

## 🎉 디스코드에서 텔레그램으로 변경된 주요 차이점

| 항목 | 디스코드 | 텔레그램 |
|------|---------|---------|
| 봇 생성 | Discord Developer Portal | @BotFather |
| 명령어 형식 | 슬래시 명령어 (`/command`) | 일반 명령어 (`/command`) |
| 파일 업로드 | `attachments` | `photo`, `document` |
| 메시지 포맷 | Embed | Markdown/HTML |
| 대화 관리 | 세션 딕셔너리 | ConversationHandler |
| 이모지 | ✅ 동일 | ✅ 동일 |

---

**제작 완료! 궁금한 점이 있으면 문의하세요.**
