# GitHub 비공개 레포지토리 업로드 가이드

## 방법 1: GitHub Desktop 사용 (추천)

### 1. GitHub Desktop 다운로드
https://desktop.github.com/ 에서 다운로드 및 설치

### 2. GitHub 계정 로그인
GitHub Desktop을 실행하고 GitHub 계정으로 로그인

### 3. 새 레포지토리 생성
1. File → Add Local Repository 클릭
2. "Choose..." 버튼 클릭
3. `c:\Users\parkc\Downloads\Fake-id-program-fixed` 폴더 선택
4. "create a repository" 링크 클릭
5. 설정:
   - Name: `fake-id-service` (또는 원하는 이름)
   - Description: `민증 제작 서비스 v2.0`
   - **☑️ Keep this code private** 체크 (중요!)
   - Git Ignore: Python
   - License: None
6. "Create Repository" 버튼 클릭

### 4. 첫 커밋
1. 좌측에서 변경된 파일 확인
2. 하단 Summary에 입력: `Initial commit - 민증 제작 서비스 v2.0`
3. "Commit to main" 버튼 클릭

### 5. GitHub에 업로드
1. 상단 "Publish repository" 버튼 클릭
2. **☑️ Keep this code private** 체크 확인 (중요!)
3. "Publish Repository" 버튼 클릭

완료! 🎉

---

## 방법 2: 웹 브라우저 사용 (Git 미설치)

### 1. GitHub 레포지토리 생성
1. https://github.com/new 접속
2. 설정:
   - Repository name: `fake-id-service`
   - Description: `민증 제작 서비스 v2.0`
   - **Private** 선택 (중요!)
   - Add .gitignore: Python
3. "Create repository" 클릭

### 2. 파일 업로드
1. "uploading an existing file" 링크 클릭
2. 프로젝트 폴더의 모든 파일을 드래그 앤 드롭
   - ⚠️ 주의: `.git` 폴더는 제외
   - ⚠️ 주의: `DB/database.db` 파일 제외 (민감 정보)
   - ⚠️ 주의: `DB/saved_images/` 내의 이미지들 제외
3. Commit 메시지 입력: `Initial commit - 민증 제작 서비스 v2.0`
4. "Commit changes" 버튼 클릭

완료! 🎉

---

## 방법 3: Git 명령어 사용 (Git 설치 필요)

### 1. Git 설치
https://git-scm.com/download/win 에서 다운로드 및 설치

### 2. Git 초기화 및 업로드
```bash
cd c:\Users\parkc\Downloads\Fake-id-program-fixed

# Git 초기화
git init

# 원격 레포지토리 연결 (먼저 GitHub에서 레포지토리 생성 필요)
git remote add origin https://github.com/YOUR_USERNAME/fake-id-service.git

# 파일 추가
git add .

# 커밋
git commit -m "Initial commit - 민증 제작 서비스 v2.0"

# 푸시
git branch -M main
git push -u origin main
```

완료! 🎉

---

## 🔒 보안 체크리스트

업로드 **전에** 반드시 확인하세요:

- ✅ `.gitignore` 파일 확인
- ✅ `config.py`의 토큰이 예시 값인지 확인
- ✅ `DB/database.db` 제외되었는지 확인
- ✅ `DB/saved_images/` 이미지들 제외되었는지 확인
- ✅ `DB/payment_proofs/` 이미지들 제외되었는지 확인
- ✅ 레포지토리가 **Private**로 설정되었는지 확인
- ✅ `.env` 파일이 제외되었는지 확인

---

## 📦 배포 후 설정 (팀원 또는 다른 PC에서)

### 1. 레포지토리 클론
```bash
git clone https://github.com/YOUR_USERNAME/fake-id-service.git
cd fake-id-service
```

### 2. 패키지 설치
```bash
pip install -r requirements.txt
```

### 3. config.py 수정
실제 토큰 및 설정 값 입력

### 4. 실행
```bash
python run.py
```

---

## 🆘 문제 해결

### Q: "Permission denied" 오류
A: GitHub 계정에 로그인되어 있는지 확인

### Q: 파일이 너무 많아서 업로드가 안 됨
A: `.gitignore`가 제대로 설정되었는지 확인. `DB/` 폴더의 이미지들이 제외되어야 함

### Q: 토큰이 노출되었을 때
A: 
1. 즉시 @BotFather에서 토큰 재발급 (`/revoke`)
2. GitHub에서 해당 커밋 삭제 또는 레포지토리를 Private으로 변경
3. 새 토큰으로 업데이트

---

## 💡 권장사항

1. **환경 변수 사용**: 민감한 정보는 환경 변수로 관리
   ```bash
   # Windows
   set TELEGRAM_TOKEN=your_token_here
   set OWNER_ID=your_id_here
   python run.py
   ```

2. **config_local.py 사용**: 
   - `config_local.py`를 만들어 실제 토큰 저장
   - `.gitignore`에 `config_local.py` 추가
   - `config.py`에서 `config_local.py` 임포트

3. **브랜치 전략**:
   - `main`: 프로덕션 코드
   - `dev`: 개발 중인 코드
   - `feature/*`: 새 기능 개발

---

**안전한 배포를 위해 이 가이드를 꼭 따라주세요!** 🔒
