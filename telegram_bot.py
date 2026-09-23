# telegram_bot.py - 텔레그램 봇 버전
import os
import sqlite3
import traceback
import random, string
from datetime import datetime, timedelta
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

import config  # config.py 사용

# ---------- 유틸 ----------
def now_str(fmt="%Y-%m-%d %H:%M:%S"):
    return datetime.now().strftime(fmt)

def gen_key(n=14):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=n))

def gen_query(n=12):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=n))

# ---------- 설정 ----------
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or getattr(config, "TELEGRAM_TOKEN", None)
OWNER_ID = config.OWNER_ID
DB_PATH = config.db_path
DOMAIN = config.domain.rstrip("/")

# 대화 상태 정의
(WAITING_LICENSE, INPUT_NAME, INPUT_SSN, INPUT_ADDRESS, 
 INPUT_ISSUE_DATE, INPUT_REGION, INPUT_PHOTO) = range(7)

# ---------- DB 초기화 ----------
def ensure_tables():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # admins: 관리자로 지정된 유저
    cur.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY
    )""")
    
    # licenses: 발급된 코드
    cur.execute("""
    CREATE TABLE IF NOT EXISTS licenses (
        license_key TEXT PRIMARY KEY,
        user_id INTEGER,
        expire_date TEXT
    )""")
    
    # users: 웹 템플릿 접속용 코드 저장
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        expiredate TEXT,
        query TEXT,
        osname TEXT
    )""")
    
    # 기존 users 테이블 컬럼 추가 (마이그레이션)
    columns_to_add = [
        ('query', 'TEXT'),
        ('expiredate', 'TEXT'),
        ('osname', 'TEXT')
    ]
    
    for col_name, col_type in columns_to_add:
        try:
            cur.execute(f"SELECT {col_name} FROM users LIMIT 1")
        except sqlite3.OperationalError:
            print(f"⚠️ users 테이블에 {col_name} 컬럼 추가 중...")
            cur.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
            print(f"✅ {col_name} 컬럼 추가 완료")
    
    # production_users: 수집된 정보
    cur.execute("""
    CREATE TABLE IF NOT EXISTS production_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER,
        name TEXT,
        ssn TEXT,
        address TEXT,
        issue_date TEXT,
        region TEXT,
        image_path TEXT,
        created_at TEXT
    )""")
    
    # dm_allowed: 관리자가 허용한 유저만 프라이빗 메시지 처리 가능
    cur.execute("""
    CREATE TABLE IF NOT EXISTS dm_allowed (
        telegram_id INTEGER PRIMARY KEY
    )""")
    
    conn.commit()
    conn.close()
    print("✅ 데이터베이스 초기화 완료")

ensure_tables()

# ---------- 권한 헬퍼 ----------
def is_owner(uid: int) -> bool:
    return uid == OWNER_ID

def is_admin(uid: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM admins WHERE user_id=?", (uid,))
    r = cur.fetchone()
    conn.close()
    return r is not None

def is_dm_allowed(uid: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM dm_allowed WHERE telegram_id=?", (uid,))
    r = cur.fetchone()
    conn.close()
    return r is not None

# ========== 기본 명령어 ========== #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """시작 명령어"""
    await update.message.reply_text(
        "안녕하세요! 민증 제작 봇입니다.\n\n"
        "사용 가능한 명령어:\n"
        "/register - 등록\n"
        "/find - 내 ID 찾기\n"
        "/aboutme <ID> - 내 정보 확인\n\n"
        "관리자 명령어:\n"
        "/관리자추가 - 관리자 추가\n"
        "/관리자제거 - 관리자 제거\n"
        "/관리자리스트 - 관리자 목록\n"
        "/라센생성 <일수> - 라이센스 생성\n"
        "/라센리스트 - 라이센스 목록\n"
        "/라센제거 <코드> - 라이센스 삭제\n"
        "/제작유저 - 유저에게 제작 권한 부여"
    )

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """유저 등록"""
    try:
        uid = str(update.effective_user.id)
        username = update.effective_user.username or update.effective_user.first_name
        
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO users (id, osname) VALUES (?, ?)", (uid, username))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ 가입 완료!\n당신의 ID는 `{uid}` 입니다.", parse_mode='Markdown')
    except Exception as e:
        traceback.print_exc()
        await update.message.reply_text("❌ 가입 중 오류가 발생했습니다.")

async def find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """자신의 ID 찾기"""
    try:
        uid = str(update.effective_user.id)
        
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE id=?", (uid,))
        r = cur.fetchone()
        conn.close()
        
        if r:
            await update.message.reply_text(f"✅ 당신의 ID는 `{uid}` 입니다.", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ 아직 가입되지 않았습니다. /register 명령어를 사용하세요.")
    except Exception as e:
        traceback.print_exc()
        await update.message.reply_text("❌ ID 조회 중 오류가 발생했습니다.")

async def aboutme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """본인 정보 확인"""
    try:
        if not context.args:
            await update.message.reply_text("❌ 사용법: /aboutme <ID>")
            return
        
        user_id = context.args[0]
        
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT * FROM production_users WHERE telegram_id=?", (user_id,))
        row = cur.fetchone()
        conn.close()
        
        if not row:
            await update.message.reply_text("❌ 해당 ID로 등록된 정보가 없습니다.")
            return
        
        text = (
            f"📋 내 정보\n\n"
            f"이름: {row[2]}\n"
            f"주민번호: {row[3]}\n"
            f"주소: {row[4]}\n"
            f"발급일자: {row[5]}\n"
            f"발급지역: {row[6]}\n"
            f"사진경로: {row[7]}\n"
            f"등록일: {row[8]}"
        )
        await update.message.reply_text(text)
    except Exception as e:
        traceback.print_exc()
        await update.message.reply_text("❌ 정보 조회 중 오류가 발생했습니다.")

# ========== 관리자 명령어 ========== #

async def 관리자추가(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """관리자 추가 (총관리자 전용)"""
    try:
        if not is_owner(update.effective_user.id):
            await update.message.reply_text("❌ 권한 없음: 총관리자만 사용 가능합니다.")
            return
        
        if not context.args:
            await update.message.reply_text("❌ 사용법: /관리자추가 <사용자ID>")
            return
        
        target_id = int(context.args[0])
        
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (target_id,))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ 사용자 {target_id}가 관리자에 추가되었습니다.")
    except Exception as e:
        traceback.print_exc()
        await update.message.reply_text("❌ 관리자 추가 중 오류가 발생했습니다.")

async def 관리자제거(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """관리자 제거 (총관리자 전용)"""
    try:
        if not is_owner(update.effective_user.id):
            await update.message.reply_text("❌ 권한 없음: 총관리자만 사용 가능합니다.")
            return
        
        if not context.args:
            await update.message.reply_text("❌ 사용법: /관리자제거 <사용자ID>")
            return
        
        target_id = int(context.args[0])
        
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("DELETE FROM admins WHERE user_id=?", (target_id,))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ 사용자 {target_id}가 관리자에서 제거되었습니다.")
    except Exception as e:
        traceback.print_exc()
        await update.message.reply_text("❌ 관리자 제거 중 오류가 발생했습니다.")

async def 관리자리스트(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """관리자 목록"""
    try:
        if not is_owner(update.effective_user.id):
            await update.message.reply_text("❌ 권한 없음: 총관리자만 사용 가능합니다.")
            return
        
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM admins")
        rows = cur.fetchall()
        conn.close()
        
        if not rows:
            await update.message.reply_text("❌ 등록된 관리자가 없습니다.")
            return
        
        text = "👥 관리자 목록:\n\n" + "\n".join([f"• {r[0]}" for r in rows])
        await update.message.reply_text(text)
    except Exception as e:
        traceback.print_exc()
        await update.message.reply_text("❌ 관리자 목록 조회 중 오류가 발생했습니다.")

async def 라센생성(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """라이센스 생성"""
    try:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ 권한 없음: 관리자만 사용 가능합니다.")
            return
        
        if not context.args:
            await update.message.reply_text("❌ 사용법: /라센생성 <일수>")
            return
        
        days = int(context.args[0])
        if days < 1 or days > 9999:
            await update.message.reply_text("❌ 기간은 1~9999일 사이여야 합니다.")
            return
        
        key = gen_key(14)
        expire = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("INSERT INTO licenses (license_key, user_id, expire_date) VALUES (?, NULL, ?)", (key, expire))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            f"✅ 라이센스 생성 완료!\n\n"
            f"키: `{key}`\n"
            f"만료: {expire}",
            parse_mode='Markdown'
        )
    except Exception as e:
        traceback.print_exc()
        await update.message.reply_text("❌ 라이센스 생성 중 오류가 발생했습니다.")

async def 라센리스트(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """라이센스 목록"""
    try:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ 권한 없음: 관리자만 사용 가능합니다.")
            return
        
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT license_key, user_id, expire_date FROM licenses")
        rows = cur.fetchall()
        conn.close()
        
        if not rows:
            await update.message.reply_text("❌ 활성 라이센스가 없습니다.")
            return
        
        text = "📜 활성 라이센스 목록:\n\n" + "\n".join([
            f"`{r[0]}`\n유저: {r[1] or '미할당'} / 만료: {r[2]}\n"
            for r in rows
        ])
        await update.message.reply_text(text, parse_mode='Markdown')
    except Exception as e:
        traceback.print_exc()
        await update.message.reply_text("❌ 라이센스 목록 조회 중 오류가 발생했습니다.")

async def 라센제거(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """라이센스 삭제"""
    try:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ 권한 없음: 관리자만 사용 가능합니다.")
            return
        
        if not context.args:
            await update.message.reply_text("❌ 사용법: /라센제거 <라이센스키>")
            return
        
        key = context.args[0]
        
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("DELETE FROM licenses WHERE license_key=?", (key,))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ 라이센스 `{key}` 가 삭제되었습니다.", parse_mode='Markdown')
    except Exception as e:
        traceback.print_exc()
        await update.message.reply_text("❌ 라이센스 삭제 중 오류가 발생했습니다.")

async def 제작유저(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """유저에게 제작 권한 부여"""
    try:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ 권한 없음: 관리자만 사용 가능합니다.")
            return
        
        if not context.args:
            await update.message.reply_text("❌ 사용법: /제작유저 <사용자ID>")
            return
        
        target_id = int(context.args[0])
        
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO dm_allowed (telegram_id) VALUES (?)", (target_id,))
        conn.commit()
        conn.close()
        
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="📩 안내: 라이센스를 입력해 주세요. 올바른 라이센스를 입력하면 6단계 정보수집이 시작됩니다."
            )
            await update.message.reply_text(f"✅ 사용자 {target_id}에게 안내 메시지를 전송했습니다.")
        except Exception as e:
            await update.message.reply_text(f"⚠️ 메시지 전송 실패: {e}")
    except Exception as e:
        traceback.print_exc()
        await update.message.reply_text("❌ 제작유저 처리 중 오류가 발생했습니다.")

# ========== 대화형 정보 수집 ========== #

async def start_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """라이센스 입력으로 대화 시작"""
    uid = update.effective_user.id
    
    if not is_dm_allowed(uid):
        await update.message.reply_text("❌ 권한 없음: 관리자가 /제작유저 로 허용해야 입력이 가능합니다.")
        return ConversationHandler.END
    
    code = update.message.text.strip()
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT license_key, expire_date, user_id FROM licenses WHERE license_key=?", (code,))
    row = cur.fetchone()
    
    if not row:
        conn.close()
        await update.message.reply_text("❌ 유효한 라이센스를 입력해 주세요.")
        return ConversationHandler.END
    
    license_key, expire_date_str, assigned_user = row
    expire_date = datetime.strptime(expire_date_str, "%Y-%m-%d")
    
    if expire_date < datetime.now():
        conn.close()
        await update.message.reply_text("❌ 해당 라이센스는 만료되었습니다.")
        return ConversationHandler.END
    
    if assigned_user is None:
        cur.execute("UPDATE licenses SET user_id=? WHERE license_key=?", (uid, license_key))
        conn.commit()
    elif assigned_user != uid:
        conn.close()
        await update.message.reply_text("❌ 이 라이센스는 이미 다른 사용자에게 할당되었습니다.")
        return ConversationHandler.END
    
    conn.close()
    
    # 컨텍스트에 라이센스 정보 저장
    context.user_data['license'] = license_key
    context.user_data['answers'] = []
    
    await update.message.reply_text(
        "✅ 라이센스가 확인되었습니다!\n6단계 정보 입력을 시작합니다.\n\n"
        "[1/6] 이름을 입력해 주세요."
    )
    return INPUT_NAME

async def input_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """이름 입력"""
    context.user_data['answers'].append(update.message.text.strip())
    await update.message.reply_text("[2/6] 주민등록번호를 입력해 주세요. (예: 040101-1234567)")
    return INPUT_SSN

async def input_ssn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """주민번호 입력"""
    context.user_data['answers'].append(update.message.text.strip())
    await update.message.reply_text("[3/6] 주소를 입력해 주세요.")
    return INPUT_ADDRESS

async def input_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """주소 입력"""
    context.user_data['answers'].append(update.message.text.strip())
    await update.message.reply_text("[4/6] 주민등록증 발급일자를 입력해 주세요. (예: 2021.10.15)")
    return INPUT_ISSUE_DATE

async def input_issue_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """발급일자 입력"""
    context.user_data['answers'].append(update.message.text.strip())
    await update.message.reply_text("[5/6] 민증 발급 지역을 입력해 주세요.")
    return INPUT_REGION

async def input_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """발급 지역 입력"""
    context.user_data['answers'].append(update.message.text.strip())
    await update.message.reply_text("[6/6] 증명사진을 첨부해 주세요.")
    return INPUT_PHOTO

async def input_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """사진 업로드 및 완료"""
    try:
        uid = update.effective_user.id
        
        if not update.message.photo:
            await update.message.reply_text("❌ 사진 파일을 첨부해 주세요.")
            return INPUT_PHOTO
        
        # 가장 큰 사진 선택
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        
        # 파일 저장
        save_dir = os.path.join(os.path.dirname(DB_PATH), "saved_images")
        os.makedirs(save_dir, exist_ok=True)
        filename = f"{uid}_{int(datetime.now().timestamp())}_{photo.file_id}.png"
        save_path = os.path.join(save_dir, filename)
        
        await file.download_to_drive(save_path)
        
        # DB에 저장
        answers = context.user_data['answers']
        license_key = context.user_data['license']
        
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        # production_users에 저장
        cur.execute("""INSERT INTO production_users
                       (telegram_id, name, ssn, address, issue_date, region, image_path, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (uid, answers[0], answers[1], answers[2], answers[3], answers[4], save_path, now_str()))
        
        # 웹 접속용 query 생성
        query = gen_query(12)
        
        # 라이센스 만료일 가져오기
        cur.execute("SELECT expire_date FROM licenses WHERE license_key=?", (license_key,))
        lic_row = cur.fetchone()
        expire_date_str = lic_row[0] if lic_row else None
        
        # users 테이블 업데이트
        cur.execute("SELECT * FROM users WHERE id=?", (str(uid),))
        if cur.fetchone():
            cur.execute("UPDATE users SET query=?, expiredate=? WHERE id=?",
                        (query, expire_date_str, str(uid)))
        else:
            cur.execute("INSERT INTO users (id, expiredate, query, osname) VALUES (?, ?, ?, ?)",
                        (str(uid), expire_date_str, query, f"telegram-{uid}"))
        
        conn.commit()
        conn.close()
        
        # 링크 생성
        link = f"{DOMAIN}/{query}" if DOMAIN else f"http://localhost:8080/{query}"
        
        # 완료 메시지
        await update.message.reply_text(
            f"✅ {answers[0]} 이(가) 제작되었습니다!\n\n"
            f"아래 링크를 통해 이용해주시기 바랍니다:\n\n"
            f"{link}\n\n"
            f"- 위조 민증이기에 QR코드는 작동하지 않습니다.\n"
            f"- 알아서 말 지어내시고 고비를 넘기시길..."
        )
        
        # 컨텍스트 정리
        context.user_data.clear()
        
        return ConversationHandler.END
    
    except Exception as e:
        traceback.print_exc()
        await update.message.reply_text("❌ 처리 중 오류가 발생했습니다.")
        context.user_data.clear()
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """대화 취소"""
    context.user_data.clear()
    await update.message.reply_text("❌ 대화가 취소되었습니다.")
    return ConversationHandler.END

# ========== 봇 실행 ========== #

def main():
    """메인 함수"""
    if not TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN 환경변수가 설정되어 있지 않습니다.")
        raise SystemExit(1)
    
    print("✅ 텔레그램 봇 시작 중...")
    
    # Application 생성
    application = Application.builder().token(TOKEN).build()
    
    # 기본 명령어 핸들러
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("register", register))
    application.add_handler(CommandHandler("find", find))
    application.add_handler(CommandHandler("aboutme", aboutme))
    
    # 관리자 명령어 핸들러
    application.add_handler(CommandHandler("관리자추가", 관리자추가))
    application.add_handler(CommandHandler("관리자제거", 관리자제거))
    application.add_handler(CommandHandler("관리자리스트", 관리자리스트))
    application.add_handler(CommandHandler("라센생성", 라센생성))
    application.add_handler(CommandHandler("라센리스트", 라센리스트))
    application.add_handler(CommandHandler("라센제거", 라센제거))
    application.add_handler(CommandHandler("제작유저", 제작유저))
    
    # 대화형 핸들러 (라이센스 입력 -> 정보 수집)
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, start_conversation)],
        states={
            INPUT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_name)],
            INPUT_SSN: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_ssn)],
            INPUT_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_address)],
            INPUT_ISSUE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_issue_date)],
            INPUT_REGION: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_region)],
            INPUT_PHOTO: [MessageHandler(filters.PHOTO, input_photo)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
        per_chat=True
    )
    application.add_handler(conv_handler)
    
    # 봇 실행
    print("✅ 텔레그램 봇이 시작되었습니다!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
