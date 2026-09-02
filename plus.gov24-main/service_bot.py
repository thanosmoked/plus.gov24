# service_bot.py
import os
import sqlite3
import traceback
from datetime import datetime
import asyncio

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, ContextTypes, filters
)

import config
from database_schema import (
    init_database, refill_license_stock, gen_query, gen_key, gen_referral,
    get_distributor, get_distributor_by_code, is_member, has_license
)

TOKEN          = config.TELEGRAM_TOKEN
OWNER_ID       = config.OWNER_ID
DB_PATH        = config.db_path
DOMAIN         = config.domain
BANK_INFO      = config.BANK_INFO
LICENSE_PRICE  = config.LICENSE_PRICE
DIST_PRICE     = config.DIST_PRICE
DIST_BUY_PRICE = config.DIST_BUY_PRICE
CHANNEL_ID     = config.REQUIRED_CHANNEL_ID
CHANNEL_LINK   = config.REQUIRED_CHANNEL_LINK

# ===== 대화 상태 =====
# 가입 플로우
(JOIN_REFERRAL, JOIN_NAME) = range(2)
# 라이센스 구매
UPLOAD_PROOF = 10
# 총판 신청 증빙 (별도 상태로 분리 - 충돌 방지)
UPLOAD_PROOF_DIST = 11
# 관리자 거절
REJECT_REASON = 20
# 민증 제작
(ID_NAME, ID_SSN, ID_ADDR, ID_DATE, ID_REGION, ID_PHOTO) = range(30, 36)
# 민증 수정
(EDIT_FIELD, EDIT_VALUE) = range(40, 42)
# 총판 가입
(DIST_CODE, DIST_BANK_NAME, DIST_BANK_ACCT, DIST_BANK_HOLDER) = range(50, 54)
# 총판 계좌 수정
DIST_SET_BANK = 60


# ===== 유틸 =====
def now_str(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

async def check_channel(bot, user_id: int) -> bool:
    """채널 가입 여부 확인"""
    # CHANNEL_ID가 설정 안 됐으면 체크 건너뜀
    if not CHANNEL_ID or CHANNEL_ID == "0" or CHANNEL_ID == 0:
        return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status not in ("left", "kicked", "banned")
    except Exception as e:
        print(f"[채널 확인 오류] {e}")
        return True  # 확인 불가 시 통과

async def require_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """채널 미가입이면 안내 메시지 전송 후 False 반환"""
    uid = update.effective_user.id
    if await check_channel(context.bot, uid):
        return True
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("📢 채널 참여하기", url=CHANNEL_LINK)
    ]])
    text = (
        "⚠️ <b>채널 참여 필수</b>\n\n"
        "서비스를 이용하려면 먼저 공지 채널에 참여해야 합니다.\n\n"
        f"👉 <a href='{CHANNEL_LINK}'>채널 바로가기</a>\n\n"
        "참여 후 다시 시도해주세요!"
    )
    if update.message:
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=kb,
                                        disable_web_page_preview=True)
    elif update.callback_query:
        await update.callback_query.answer("채널에 먼저 참여해주세요!", show_alert=True)
        await update.callback_query.message.reply_text(text, parse_mode='HTML', reply_markup=kb,
                                                       disable_web_page_preview=True)
    return False

def is_owner(uid): return uid == OWNER_ID

def is_admin(uid):
    if is_owner(uid): return True
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM admins WHERE user_id=?", (uid,))
    r = cur.fetchone(); conn.close(); return r is not None

def db():
    return sqlite3.connect(DB_PATH)

def get_user(user_id):
    conn = db(); cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id=?", (str(user_id),))
    row = cur.fetchone(); conn.close(); return row

def get_id_info(user_id):
    conn = db(); cur = conn.cursor()
    cur.execute("""SELECT id,name,ssn,address,issue_date,region,image_path,created_at,updated_at
                   FROM production_users WHERE telegram_id=? AND is_active=1
                   ORDER BY updated_at DESC LIMIT 1""", (user_id,))
    row = cur.fetchone(); conn.close(); return row

def get_payment_info(user_id):
    """총판이 있으면 총판 계좌, 없으면 기본 계좌"""
    dist = get_distributor_by_uid_from_member(user_id)
    if dist and dist.get('bank_account'):
        return {
            "bank_name": dist['bank_name'],
            "account_number": dist['bank_account'],
            "account_holder": dist['bank_holder'],
        }
    return BANK_INFO

def get_distributor_by_uid_from_member(user_id):
    conn = db(); cur = conn.cursor()
    cur.execute("SELECT distributor_id FROM members WHERE user_id=?", (user_id,))
    row = cur.fetchone(); conn.close()
    if not row or not row[0]: return None
    conn = db(); cur = conn.cursor()
    cur.execute("SELECT * FROM distributors WHERE id=? AND is_active=1", (row[0],))
    drow = cur.fetchone(); conn.close()
    if drow:
        cols = ['id','user_id','username','referral_code','bank_name','bank_account','bank_holder','sell_price','is_active','created_at']
        return dict(zip(cols, drow))
    return None

def get_price_for_user(user_id):
    """총판 회원이면 3500원, 아니면 5000원"""
    dist = get_distributor_by_uid_from_member(user_id)
    if dist: return DIST_PRICE
    return LICENSE_PRICE


# ===== 키보드 =====
def main_kb(user_id):
    """가입 여부, 라이센스 여부에 따라 버튼 구성"""
    kb = []
    try:
        member = is_member(user_id)
        licensed = has_license(user_id)
        id_info = get_id_info(user_id)
        admin = is_admin(user_id)
        dist = get_distributor(user_id)
    except Exception:
        member = licensed = id_info = admin = dist = False

    if not member:
        kb.append([KeyboardButton("📝 서비스 가입")])
        kb.append([KeyboardButton("❓ 도움말")])
        return ReplyKeyboardMarkup(kb, resize_keyboard=True)

    if not licensed:
        kb.append([KeyboardButton("🛒 라이센스 구매")])
    else:
        kb.append([KeyboardButton("📋 내 라이센스")])
        if id_info:
            kb.append([KeyboardButton("📝 내 민증 보기"), KeyboardButton("✏️ 민증 수정")])
        else:
            kb.append([KeyboardButton("🆕 민증 제작")])

    kb.append([KeyboardButton("❓ 도움말")])

    if dist:
        kb.append([KeyboardButton("🏪 총판 메뉴")])
    elif member:
        kb.append([KeyboardButton("💼 총판 신청")])

    if admin:
        kb.append([KeyboardButton("👨‍💼 관리자 메뉴")])

    return ReplyKeyboardMarkup(kb, resize_keyboard=True)


# ===== 봇 초기화 =====
async def post_init(application):
    init_database()
    refill_license_stock()
    print("✅ 봇 초기화 완료")

# ===== /start =====
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    uname = user.username or user.first_name or str(uid)

    # 채널 가입 확인
    if not await require_channel(update, context):
        return

    conn = db(); cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (id,username,osname) VALUES (?,?,?)",
                (str(uid), uname, f"tg-{uid}"))
    conn.commit(); conn.close()
    member = is_member(uid)
    if member:
        text = f"👋 다시 오셨군요, {uname}님!\n아래 메뉴를 이용하세요."
    else:
        text = (f"👋 안녕하세요, {uname}님!\n\n"
                "🎫 <b>민증 제작 서비스</b>에 오신 것을 환영합니다.\n\n"
                "서비스를 이용하려면 먼저 <b>가입</b>이 필요합니다.\n"
                "아래 버튼을 눌러 가입해주세요!")
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=main_kb(uid))


# ===== 가입 플로우 =====
async def join_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not await require_channel(update, context):
        return ConversationHandler.END
    if is_member(uid):
        await update.message.reply_text("이미 가입된 회원입니다.", reply_markup=main_kb(uid))
        return ConversationHandler.END
    await update.message.reply_text(
        "📝 <b>서비스 가입</b>\n\n"
        "추천인 코드가 있으신가요?\n"
        "코드를 입력하거나 <b>없음</b> 을 입력하세요.",
        parse_mode='HTML', reply_markup=ReplyKeyboardRemove()
    )
    return JOIN_REFERRAL

async def join_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.upper() == "없음" or text == "-":
        context.user_data['referral'] = None
        context.user_data['dist_id'] = None
    else:
        dist = get_distributor_by_code(text.upper())
        if not dist:
            await update.message.reply_text("❌ 유효하지 않은 추천인 코드입니다.\n다시 입력하거나 <b>없음</b> 을 입력하세요.", parse_mode='HTML')
            return JOIN_REFERRAL
        context.user_data['referral'] = text.upper()
        context.user_data['dist_id'] = dist['id']
    await update.message.reply_text("✅ 확인됐습니다!\n\n실명(이름)을 입력해주세요:")
    return JOIN_NAME

async def join_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    uname = update.effective_user.username or str(uid)
    real_name = update.message.text.strip()
    referral = context.user_data.get('referral')
    dist_id = context.user_data.get('dist_id')
    conn = db(); cur = conn.cursor()
    cur.execute("""INSERT OR IGNORE INTO members (user_id,username,real_name,distributor_id,referral_code)
                   VALUES (?,?,?,?,?)""", (uid, uname, real_name, dist_id, referral))
    cur.execute("UPDATE users SET is_registered=1, real_name=?, referral_used=?, distributor_id=? WHERE id=?",
                (real_name, referral, dist_id, str(uid)))
    conn.commit(); conn.close()
    context.user_data.clear()
    txt = f"🎉 <b>가입 완료!</b>\n\n이름: {real_name}\n"
    if referral:
        txt += f"추천인 코드: {referral}\n"
    txt += "\n이제 라이센스를 구매하고 서비스를 이용하세요!"
    await update.message.reply_text(txt, parse_mode='HTML', reply_markup=main_kb(uid))
    return ConversationHandler.END

async def join_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("가입이 취소됐습니다.", reply_markup=main_kb(update.effective_user.id))
    return ConversationHandler.END


# ===== 라이센스 구매 =====
async def show_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_member(uid):
        await update.message.reply_text("❌ 먼저 가입을 완료해주세요.", reply_markup=main_kb(uid))
        return
    if has_license(uid):
        await update.message.reply_text("✅ 이미 영구 라이센스를 보유하고 있습니다.", reply_markup=main_kb(uid))
        return
    price = get_price_for_user(uid)
    pay = get_payment_info(uid)
    text = (
        "🛒 <b>라이센스 구매</b>\n\n"
        "💳 <b>영구 이용권</b> — 한 번 구매로 영구 사용\n"
        f"💰 가격: <b>{price:,}원</b>\n\n"
        f"📌 <b>입금 정보</b>\n"
        f"은행: {pay['bank_name']}\n"
        f"계좌: {pay['account_number']}\n"
        f"예금주: {pay['account_holder']}\n\n"
        f"⚠️ 정확히 <b>{price:,}원</b>을 입금 후\n"
        "입금 스크린샷을 이 채팅으로 보내주세요."
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 취소", callback_data="cancel_purchase")]])
    msg = update.message or (update.callback_query and update.callback_query.message)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode='HTML', reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=kb)
    context.user_data['buying_license'] = True
    return UPLOAD_PROOF

async def receive_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    uname = update.effective_user.username or str(uid)
    if not update.message.photo:
        await update.message.reply_text("❌ 스크린샷 이미지를 보내주세요.")
        return UPLOAD_PROOF
    price = get_price_for_user(uid)
    dist = get_distributor_by_uid_from_member(uid)
    dist_id = dist['id'] if dist else None
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    os.makedirs(config.proofs_path, exist_ok=True)
    save_path = os.path.join(config.proofs_path, f"pay_{uid}_{int(datetime.now().timestamp())}.jpg")
    await file.download_to_drive(save_path)
    conn = db(); cur = conn.cursor()
    cur.execute("""INSERT INTO payment_requests
                   (user_id,username,price,payment_image_path,payment_type,status,distributor_id)
                   VALUES (?,?,?,?,'license','pending',?)""",
                (uid, uname, price, save_path, dist_id))
    req_id = cur.lastrowid
    conn.commit(); conn.close()
    await update.message.reply_text(
        f"✅ <b>입금 증빙 접수!</b>\n요청 번호: #{req_id}\n\n관리자 승인 후 라이센스가 활성화됩니다.",
        parse_mode='HTML', reply_markup=main_kb(uid)
    )
    await _notify_admins_payment(context, req_id, uid, uname, price, save_path, dist_id)
    context.user_data.clear()
    return ConversationHandler.END

async def _notify_admins_payment(context, req_id, uid, uname, price, image_path, dist_id):
    """결제 알림 전송
    - 총판 주문: 총판에게만 승인/거절 버튼 전송, 관리자에게는 알림만(버튼 없음)
    - 일반 주문: 관리자에게만 승인/거절 버튼 전송
    """
    conn = db(); cur = conn.cursor()
    cur.execute("SELECT user_id FROM admins")
    admins = [r[0] for r in cur.fetchall()]
    conn.close()
    if OWNER_ID not in admins:
        admins.append(OWNER_ID)

    kb_action = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ 승인", callback_data=f"apv_{req_id}"),
        InlineKeyboardButton("❌ 거절", callback_data=f"rej_{req_id}")
    ]])

    if dist_id:
        # 총판 주문: 총판에게 승인/거절 버튼
        conn = db(); cur = conn.cursor()
        cur.execute("SELECT user_id FROM distributors WHERE id=?", (dist_id,))
        row = cur.fetchone(); conn.close()
        dist_uid = row[0] if row else None

        # 총판에게 승인/거절 버튼 포함 전송
        if dist_uid:
            text_dist = (f"🏪 <b>총판 회원 결제 요청 #{req_id}</b>\n"
                         f"👤 {uname} (<code>{uid}</code>)\n"
                         f"💰 {price:,}원")
            try:
                if os.path.exists(image_path):
                    await context.bot.send_photo(chat_id=dist_uid, photo=open(image_path,'rb'),
                                                 caption=text_dist, parse_mode='HTML', reply_markup=kb_action)
                else:
                    await context.bot.send_message(chat_id=dist_uid, text=text_dist,
                                                   parse_mode='HTML', reply_markup=kb_action)
            except Exception as e:
                print(f"총판 알림 전송 실패 {dist_uid}: {e}")

        # 관리자에게는 버튼 없이 정보만 전송
        text_adm = (f"📋 <b>총판 주문 발생 #{req_id}</b>\n"
                    f"👤 {uname} (<code>{uid}</code>)\n"
                    f"💰 {price:,}원\n"
                    f"🏪 총판 처리 중 (관리자 개입 불필요)")
        for admin_id in admins:
            if admin_id == dist_uid:
                continue  # 총판=관리자인 경우 중복 방지
            try:
                await context.bot.send_message(chat_id=admin_id, text=text_adm, parse_mode='HTML')
            except Exception as e:
                print(f"관리자 알림 실패 {admin_id}: {e}")
    else:
        # 일반 주문: 관리자에게만 승인/거절 버튼
        text = (f"🔔 <b>결제 요청 #{req_id}</b>\n"
                f"👤 {uname} (<code>{uid}</code>)\n"
                f"💰 {price:,}원\n"
                f"📦 일반 주문")
        for admin_id in admins:
            try:
                if os.path.exists(image_path):
                    await context.bot.send_photo(chat_id=admin_id, photo=open(image_path,'rb'),
                                                 caption=text, parse_mode='HTML', reply_markup=kb_action)
                else:
                    await context.bot.send_message(chat_id=admin_id, text=text,
                                                   parse_mode='HTML', reply_markup=kb_action)
            except Exception as e:
                print(f"관리자 알림 전송 실패 {admin_id}: {e}")

async def cancel_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    uid = update.effective_user.id
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ 구매가 취소됐습니다.")
    else:
        await update.message.reply_text("❌ 구매가 취소됐습니다.", reply_markup=main_kb(uid))
    return ConversationHandler.END


# ===== 관리자/총판 결제 승인/거절 =====
def can_approve(approver_id: int, req_id: int) -> bool:
    """승인 권한 확인 - 관리자이거나 해당 주문의 총판"""
    if is_admin(approver_id):
        return True
    # 총판 확인: 이 요청의 distributor_id와 매칭되는지
    conn = db(); cur = conn.cursor()
    cur.execute("SELECT distributor_id FROM payment_requests WHERE id=?", (req_id,))
    row = cur.fetchone(); conn.close()
    if not row or not row[0]:
        return False
    dist = get_distributor(approver_id)
    return dist is not None and dist['id'] == row[0]

async def approve_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    req_id = int(query.data.split("_")[1])
    approver_id = query.from_user.id
    if not can_approve(approver_id, req_id):
        await query.answer("❌ 권한 없음", show_alert=True); return
    conn = db(); cur = conn.cursor()
    cur.execute("SELECT user_id,username,price,status FROM payment_requests WHERE id=?", (req_id,))
    req = cur.fetchone()
    if not req:
        await query.answer("❌ 요청 없음", show_alert=True); conn.close(); return
    uid, uname, price, status = req
    if status != 'pending':
        await query.answer("이미 처리된 요청", show_alert=True); conn.close(); return
    # 라이센스 발급
    cur.execute("SELECT license_key FROM license_store WHERE is_sold=0 LIMIT 1")
    lic = cur.fetchone()
    if not lic:
        from database_schema import refill_license_stock as rfl
        conn.close(); rfl()
        conn = db(); cur = conn.cursor()
        cur.execute("SELECT license_key FROM license_store WHERE is_sold=0 LIMIT 1")
        lic = cur.fetchone()
    if not lic:
        await query.answer("❌ 재고 없음", show_alert=True); conn.close(); return
    lkey = lic[0]
    cur.execute("UPDATE license_store SET is_sold=1,sold_to=?,sold_at=? WHERE license_key=?",
                (uid, now_str(), lkey))
    cur.execute("INSERT OR REPLACE INTO user_licenses (user_id,license_key,is_active) VALUES (?,?,1)",
                (uid, lkey))
    cur.execute("UPDATE users SET expiredate='9999-12-31' WHERE id=?", (str(uid),))
    cur.execute("INSERT INTO purchase_history (user_id,username,license_key,price) VALUES (?,?,?,?)",
                (uid, uname, lkey, price))
    cur.execute("UPDATE payment_requests SET status='approved',admin_id=?,license_key=?,updated_at=? WHERE id=?",
                (query.from_user.id, lkey, now_str(), req_id))
    conn.commit(); conn.close()
    cap = (query.message.caption or "") + "\n\n✅ <b>승인 완료</b>"
    try:
        await query.edit_message_caption(caption=cap, parse_mode='HTML')
    except Exception:
        pass
    try:
        await context.bot.send_message(
            chat_id=uid,
            text=(f"🎉 <b>결제 승인!</b>\n\n"
                  f"🔑 라이센스 키: <code>{lkey}</code>\n"
                  f"💳 영구 이용권 활성화 완료!\n\n이제 민증을 제작할 수 있습니다."),
            parse_mode='HTML', reply_markup=main_kb(uid)
        )
    except Exception as e:
        print(f"사용자 알림 실패: {e}")

async def reject_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    req_id = int(query.data.split("_")[1])
    approver_id = query.from_user.id
    if not can_approve(approver_id, req_id):
        await query.answer("❌ 권한 없음", show_alert=True); return
    context.user_data['rej_req_id'] = req_id
    conn = db(); cur = conn.cursor()
    cur.execute("SELECT user_id FROM payment_requests WHERE id=?", (req_id,))
    row = cur.fetchone(); conn.close()
    if row: context.user_data['rej_user_id'] = row[0]
    try:
        await query.edit_message_caption(
            caption=(query.message.caption or "") + "\n\n📝 거절 사유를 입력해주세요:",
            parse_mode='HTML'
        )
    except Exception:
        await query.message.reply_text("📝 거절 사유를 입력해주세요:")
    return REJECT_REASON

async def receive_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text.strip()
    req_id = context.user_data.get('rej_req_id')
    uid = context.user_data.get('rej_user_id')
    if req_id:
        conn = db(); cur = conn.cursor()
        cur.execute("UPDATE payment_requests SET status='rejected',admin_response=?,admin_id=?,updated_at=? WHERE id=?",
                    (reason, update.effective_user.id, now_str(), req_id))
        conn.commit(); conn.close()
    await update.message.reply_text(f"✅ #{req_id} 거절 완료")
    if uid:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"❌ <b>결제 거절</b>\n\n사유: {reason}\n\n문의사항은 관리자에게 연락해주세요.",
                parse_mode='HTML', reply_markup=main_kb(uid)
            )
        except Exception: pass
    context.user_data.clear()
    return ConversationHandler.END


# ===== 내 라이센스 확인 =====
async def my_license(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not has_license(uid):
        await update.message.reply_text("❌ 라이센스가 없습니다. 먼저 구매해주세요.", reply_markup=main_kb(uid))
        return
    conn = db(); cur = conn.cursor()
    cur.execute("SELECT license_key, activated_at FROM user_licenses WHERE user_id=? AND is_active=1", (uid,))
    row = cur.fetchone(); conn.close()
    if row:
        await update.message.reply_text(
            f"✅ <b>영구 라이센스 보유중</b>\n\n🔑 키: <code>{row[0]}</code>\n📅 활성화: {row[1]}",
            parse_mode='HTML', reply_markup=main_kb(uid)
        )


# ===== 민증 제작 플로우 =====
async def id_create_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_member(uid):
        await update.message.reply_text("❌ 먼저 가입해주세요.", reply_markup=main_kb(uid))
        return ConversationHandler.END
    if not has_license(uid):
        await update.message.reply_text("❌ 라이센스가 필요합니다.", reply_markup=main_kb(uid))
        return ConversationHandler.END
    context.user_data['id_answers'] = []
    await update.message.reply_text(
        "🆕 <b>민증 제작 시작</b>\n\n📝 [1/6] <b>이름</b>을 입력하세요:",
        parse_mode='HTML', reply_markup=ReplyKeyboardRemove()
    )
    return ID_NAME

async def id_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['id_answers'] = [update.message.text.strip()]
    await update.message.reply_text("📝 [2/6] <b>주민등록번호</b>를 입력하세요.\n(예: 990101-1234567)", parse_mode='HTML')
    return ID_SSN

async def id_ssn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['id_answers'].append(update.message.text.strip())
    await update.message.reply_text("📝 [3/6] <b>주소</b>를 입력하세요.", parse_mode='HTML')
    return ID_ADDR

async def id_addr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['id_answers'].append(update.message.text.strip())
    await update.message.reply_text("📝 [4/6] <b>발급일자</b>를 입력하세요.\n(예: 2020.01.15)", parse_mode='HTML')
    return ID_DATE

async def id_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['id_answers'].append(update.message.text.strip())
    await update.message.reply_text("📝 [5/6] <b>발급 지역</b>을 입력하세요.\n(예: 서울특별시장)", parse_mode='HTML')
    return ID_REGION

async def id_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['id_answers'].append(update.message.text.strip())
    await update.message.reply_text("📝 [6/6] <b>증명사진</b>을 업로드하세요.", parse_mode='HTML')
    return ID_PHOTO

async def id_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not update.message.photo:
        await update.message.reply_text("❌ 사진을 보내주세요.")
        return ID_PHOTO
    answers = context.user_data.get('id_answers', [])
    if len(answers) < 5:
        await update.message.reply_text("❌ 정보가 부족합니다. /start 후 다시 시도해주세요.", reply_markup=main_kb(uid))
        context.user_data.clear()
        return ConversationHandler.END
    name, ssn, address, issue_date, region = answers
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    os.makedirs(config.images_path, exist_ok=True)
    save_path = os.path.join(config.images_path, f"{uid}_{int(datetime.now().timestamp())}.png")
    await file.download_to_drive(save_path)
    conn = db(); cur = conn.cursor()
    cur.execute("UPDATE production_users SET is_active=0 WHERE telegram_id=?", (uid,))
    cur.execute("""INSERT INTO production_users
                   (telegram_id,name,ssn,address,issue_date,region,image_path,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (uid, name, ssn, address, issue_date, region, save_path, now_str(), now_str()))
    query_code = gen_query(12)
    cur.execute("SELECT id FROM users WHERE id=?", (str(uid),))
    if cur.fetchone():
        cur.execute("UPDATE users SET query=? WHERE id=?", (query_code, str(uid)))
    else:
        cur.execute("INSERT INTO users (id, query) VALUES (?,?)", (str(uid), query_code))
    conn.commit(); conn.close()
    web_link = f"{DOMAIN}/{query_code}"
    await update.message.reply_text(
        f"✅ <b>민증 제작 완료!</b>\n\n"
        f"👤 이름: {name}\n🆔 주민번호: {ssn}\n🏠 주소: {address}\n"
        f"📅 발급일: {issue_date}\n📍 발급지역: {region}\n\n"
        f"🔗 <b>웹 링크:</b>\n{web_link}",
        parse_mode='HTML', reply_markup=main_kb(uid)
    )
    context.user_data.clear()
    return ConversationHandler.END

async def id_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    uid = update.effective_user.id
    await update.message.reply_text("❌ 취소됐습니다.", reply_markup=main_kb(uid))
    return ConversationHandler.END


# ===== 내 민증 보기 =====
async def show_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    row = get_id_info(uid)
    if not row:
        await update.message.reply_text("❌ 제작된 민증이 없습니다.", reply_markup=main_kb(uid))
        return
    _, name, ssn, address, issue_date, region, image_path, created_at, updated_at = row
    conn = db(); cur = conn.cursor()
    cur.execute("SELECT query FROM users WHERE id=?", (str(uid),))
    qrow = cur.fetchone(); conn.close()
    web_link = f"{DOMAIN}/{qrow[0]}" if qrow and qrow[0] else "링크 없음"
    text = (f"📋 <b>내 민증 정보</b>\n\n"
            f"👤 이름: {name}\n🆔 주민번호: {ssn}\n🏠 주소: {address}\n"
            f"📅 발급일: {issue_date}\n📍 발급지역: {region}\n\n"
            f"🔗 웹 링크: {web_link}\n🕐 수정일: {updated_at}")
    if image_path and os.path.exists(image_path):
        try:
            await update.message.reply_photo(photo=open(image_path,'rb'), caption=text, parse_mode='HTML', reply_markup=main_kb(uid))
            return
        except Exception: pass
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=main_kb(uid))

# ===== 민증 수정 플로우 =====
async def id_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not has_license(uid):
        await update.message.reply_text("❌ 라이센스가 필요합니다.", reply_markup=main_kb(uid))
        return ConversationHandler.END
    row = get_id_info(uid)
    if not row:
        await update.message.reply_text("❌ 수정할 민증이 없습니다.", reply_markup=main_kb(uid))
        return ConversationHandler.END
    _, name, ssn, address, issue_date, region, _, _, _ = row
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 이름", callback_data="ef_name"),
         InlineKeyboardButton("🆔 주민번호", callback_data="ef_ssn")],
        [InlineKeyboardButton("🏠 주소", callback_data="ef_address"),
         InlineKeyboardButton("📅 발급일자", callback_data="ef_issue_date")],
        [InlineKeyboardButton("📍 발급지역", callback_data="ef_region"),
         InlineKeyboardButton("📸 사진", callback_data="ef_photo")],
        [InlineKeyboardButton("❌ 취소", callback_data="ef_cancel")]
    ])
    text = (f"✏️ <b>민증 수정</b>\n\n현재 정보:\n"
            f"👤 {name} | 🆔 {ssn}\n🏠 {address}\n📅 {issue_date} | 📍 {region}\n\n수정할 항목을 선택하세요:")
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode='HTML', reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=kb)
    return EDIT_FIELD

async def edit_field_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    field = query.data.split("_", 1)[1]
    if field == "cancel":
        await query.edit_message_text("❌ 수정이 취소됐습니다.")
        return ConversationHandler.END
    field_names = {'name':'이름','ssn':'주민번호','address':'주소',
                   'issue_date':'발급일자','region':'발급지역','photo':'증명사진'}
    context.user_data['edit_field'] = field
    if field == 'photo':
        await query.edit_message_text(f"📸 새로운 <b>증명사진</b>을 업로드해주세요.", parse_mode='HTML')
    else:
        await query.edit_message_text(f"✏️ <b>{field_names[field]}</b>의 새 값을 입력해주세요.", parse_mode='HTML')
    return EDIT_VALUE

async def edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    field = context.user_data.get('edit_field')
    if not field:
        await update.message.reply_text("❌ 세션 만료. 다시 시도해주세요.", reply_markup=main_kb(uid))
        return ConversationHandler.END
    field_map = {'name':'name','ssn':'ssn','address':'address',
                 'issue_date':'issue_date','region':'region','photo':'image_path'}
    field_names = {'name':'이름','ssn':'주민번호','address':'주소',
                   'issue_date':'발급일자','region':'발급지역','photo':'증명사진'}
    if field == 'photo':
        if not update.message.photo:
            await update.message.reply_text("❌ 사진을 보내주세요.")
            return EDIT_VALUE
        # 기존 사진 삭제
        row = get_id_info(uid)
        if row and row[6] and os.path.exists(row[6]):
            try: os.remove(row[6])
            except Exception: pass
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        os.makedirs(config.images_path, exist_ok=True)
        save_path = os.path.join(config.images_path, f"{uid}_{int(datetime.now().timestamp())}.png")
        await file.download_to_drive(save_path)
        new_value = save_path
        display = "사진 업데이트됨"
    else:
        new_value = update.message.text.strip()
        display = new_value
    db_field = field_map[field]
    conn = db(); cur = conn.cursor()
    cur.execute(f"UPDATE production_users SET {db_field}=?, updated_at=? WHERE telegram_id=? AND is_active=1",
                (new_value, now_str(), uid))
    cur.execute("SELECT query FROM users WHERE id=?", (str(uid),))
    qrow = cur.fetchone()
    if not qrow or not qrow[0]:
        qcode = gen_query(12)
        cur.execute("INSERT OR REPLACE INTO users (id, query) VALUES (?,?)", (str(uid), qcode))
        query_code = qcode
    else:
        query_code = qrow[0]
    conn.commit(); conn.close()
    web_link = f"{DOMAIN}/{query_code}"
    await update.message.reply_text(
        f"✅ <b>{field_names[field]}</b> 업데이트 완료!\n값: {display}\n\n🔗 웹 링크: {web_link}",
        parse_mode='HTML', reply_markup=main_kb(uid)
    )
    context.user_data.clear()
    return ConversationHandler.END


# ===== 총판 신청 플로우 =====
async def dist_apply_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_member(uid):
        await update.message.reply_text("❌ 먼저 가입해주세요.", reply_markup=main_kb(uid))
        return ConversationHandler.END
    if get_distributor(uid):
        await update.message.reply_text("✅ 이미 총판 권한이 있습니다.", reply_markup=main_kb(uid))
        return ConversationHandler.END
    pay = BANK_INFO
    await update.message.reply_text(
        f"💼 <b>총판 신청</b>\n\n"
        f"총판 권한 가격: <b>{DIST_BUY_PRICE:,}원</b>\n\n"
        f"총판이 되면:\n"
        f"• 나만의 추천인 코드 설정 가능\n"
        f"• 내 회원들은 <b>{DIST_PRICE:,}원</b>에 구매\n"
        f"• 전용 입금 계좌 설정 가능\n"
        f"• 내 회원 목록 조회 가능\n\n"
        f"📌 입금 정보\n"
        f"은행: {pay['bank_name']}\n"
        f"계좌: {pay['account_number']}\n"
        f"예금주: {pay['account_holder']}\n\n"
        f"{DIST_BUY_PRICE:,}원 입금 후 스크린샷을 보내주세요.",
        parse_mode='HTML', reply_markup=ReplyKeyboardRemove()
    )
    context.user_data['buying_dist'] = True
    return UPLOAD_PROOF_DIST

async def dist_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    dist = get_distributor(uid)
    if not dist:
        await update.message.reply_text("❌ 총판 권한이 없습니다.", reply_markup=main_kb(uid))
        return
    conn = db(); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM members WHERE distributor_id=?", (dist['id'],))
    member_count = cur.fetchone()[0]
    conn.close()
    bank_str = f"{dist['bank_name']} {dist['bank_account']} ({dist['bank_holder']})" if dist.get('bank_account') else "미설정"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 내 회원 목록", callback_data="dist_members")],
        [InlineKeyboardButton("📥 회원 입금 신청", callback_data="dist_pending")],
        [InlineKeyboardButton("🏦 입금 계좌 설정", callback_data="dist_set_bank")],
        [InlineKeyboardButton("🔑 추천인 코드 확인", callback_data="dist_code")],
    ])
    await update.message.reply_text(
        f"🏪 <b>총판 메뉴</b>\n\n"
        f"추천인 코드: <code>{dist['referral_code']}</code>\n"
        f"회원 수: {member_count}명\n"
        f"입금 계좌: {bank_str}\n"
        f"판매 가격: {dist['sell_price']:,}원",
        parse_mode='HTML', reply_markup=kb
    )

async def dist_members_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    dist = get_distributor(uid)
    if not dist:
        await query.answer("권한 없음", show_alert=True); return
    conn = db(); cur = conn.cursor()
    cur.execute("""SELECT m.user_id, m.username, m.real_name, m.joined_at,
                          p.name as id_name
                   FROM members m
                   LEFT JOIN production_users p ON p.telegram_id=m.user_id AND p.is_active=1
                   WHERE m.distributor_id=? ORDER BY m.joined_at DESC LIMIT 20""", (dist['id'],))
    rows = cur.fetchall(); conn.close()
    if not rows:
        await query.edit_message_text("👥 회원이 없습니다.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 뒤로", callback_data="dist_back")]]))
        return
    text = "👥 <b>내 회원 목록</b>\n\n"
    for i, (m_uid, m_uname, m_real, m_joined, m_idname) in enumerate(rows, 1):
        text += f"{i}. {m_real or m_uname} (@{m_uname})\n   민증명: {m_idname or '미제작'} | {m_joined[:10]}\n"
    await query.edit_message_text(text, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 뒤로", callback_data="dist_back")]]))

async def dist_set_bank_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🏦 <b>입금 계좌 설정</b>\n\n은행명을 입력하세요:\n(예: 카카오뱅크)",
        parse_mode='HTML'
    )
    context.user_data['setting_bank'] = True
    return DIST_BANK_NAME

async def dist_bank_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['bank_name'] = update.message.text.strip()
    await update.message.reply_text("계좌번호를 입력하세요:")
    return DIST_BANK_ACCT

async def dist_bank_acct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['bank_acct'] = update.message.text.strip()
    await update.message.reply_text("예금주를 입력하세요:")
    return DIST_BANK_HOLDER

async def dist_bank_holder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    bank_name = context.user_data.get('bank_name', '')
    bank_acct = context.user_data.get('bank_acct', '')
    bank_holder = update.message.text.strip()
    conn = db(); cur = conn.cursor()
    cur.execute("UPDATE distributors SET bank_name=?,bank_account=?,bank_holder=? WHERE user_id=?",
                (bank_name, bank_acct, bank_holder, uid))
    conn.commit(); conn.close()
    context.user_data.clear()
    await update.message.reply_text(
        f"✅ 계좌 설정 완료!\n\n은행: {bank_name}\n계좌: {bank_acct}\n예금주: {bank_holder}",
        reply_markup=main_kb(uid)
    )
    return ConversationHandler.END

async def dist_code_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    dist = get_distributor(uid)
    if dist:
        await query.edit_message_text(
            f"🔑 내 추천인 코드: <code>{dist['referral_code']}</code>\n\n이 코드를 회원들에게 공유하세요!",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 뒤로", callback_data="dist_back")]])
        )

async def dist_pending_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """총판이 자기 회원의 입금 신청 목록 조회"""
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    dist = get_distributor(uid)
    if not dist:
        await query.answer("권한 없음", show_alert=True); return
    conn = db(); cur = conn.cursor()
    cur.execute("""SELECT id, user_id, username, price, status, created_at
                   FROM payment_requests
                   WHERE distributor_id=? AND payment_type='license'
                   ORDER BY created_at DESC LIMIT 15""", (dist['id'],))
    rows = cur.fetchall(); conn.close()
    if not rows:
        await query.edit_message_text("📥 입금 신청 없음.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 뒤로", callback_data="dist_back")]])); return
    text = "📥 <b>회원 입금 신청 목록</b>\n\n"
    status_map = {'pending': '⏳ 대기', 'approved': '✅ 승인', 'rejected': '❌ 거절'}
    for rid, ruid, runame, rprice, rstatus, rcreated in rows:
        text += f"#{rid} @{runame} | {rprice:,}원 | {status_map.get(rstatus, rstatus)} | {rcreated[:10]}\n"
    await query.edit_message_text(text, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 뒤로", callback_data="dist_back")]]))


async def dist_back_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.delete_message()


# ===== 총판 구매 증빙 수신 (UPLOAD_PROOF 공용) =====
async def receive_proof_dist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """총판 신청 증빙 처리"""
    uid = update.effective_user.id
    uname = update.effective_user.username or str(uid)
    if not update.message.photo:
        await update.message.reply_text("❌ 스크린샷을 보내주세요.")
        return UPLOAD_PROOF
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    os.makedirs(config.proofs_path, exist_ok=True)
    save_path = os.path.join(config.proofs_path, f"dist_{uid}_{int(datetime.now().timestamp())}.jpg")
    await file.download_to_drive(save_path)
    conn = db(); cur = conn.cursor()
    cur.execute("""INSERT INTO payment_requests
                   (user_id,username,price,payment_image_path,payment_type,status)
                   VALUES (?,?,?,?,'distributor','pending')""",
                (uid, uname, DIST_BUY_PRICE, save_path))
    req_id = cur.lastrowid
    conn.commit(); conn.close()
    await update.message.reply_text(
        f"✅ <b>총판 신청 접수!</b>\n요청 번호: #{req_id}\n\n관리자 승인 후 총판 권한이 부여됩니다.",
        parse_mode='HTML', reply_markup=main_kb(uid)
    )
    # 관리자 알림
    conn = db(); cur = conn.cursor()
    cur.execute("SELECT user_id FROM admins"); admins = [r[0] for r in cur.fetchall()]; conn.close()
    if OWNER_ID not in admins: admins.append(OWNER_ID)
    text = (f"🏪 <b>총판 신청 #{req_id}</b>\n"
            f"👤 {uname} (<code>{uid}</code>)\n💰 {DIST_BUY_PRICE:,}원")
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ 총판 승인", callback_data=f"dapv_{req_id}_{uid}"),
        InlineKeyboardButton("❌ 거절", callback_data=f"rej_{req_id}")
    ]])
    for admin_id in admins:
        try:
            await context.bot.send_photo(chat_id=admin_id, photo=open(save_path,'rb'),
                                         caption=text, parse_mode='HTML', reply_markup=kb)
        except Exception as e:
            print(f"총판 알림 실패: {e}")
    context.user_data.clear()
    return ConversationHandler.END

async def approve_distributor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.answer("❌ 권한 없음", show_alert=True); return
    parts = query.data.split("_")
    req_id = int(parts[1]); uid = int(parts[2])
    conn = db(); cur = conn.cursor()
    cur.execute("SELECT username FROM users WHERE id=?", (str(uid),))
    urow = cur.fetchone()
    uname = urow[0] if urow else str(uid)
    # 추천인 코드 생성
    code = gen_referral(8)
    while True:
        cur.execute("SELECT 1 FROM distributors WHERE referral_code=?", (code,))
        if not cur.fetchone(): break
        code = gen_referral(8)
    cur.execute("""INSERT OR IGNORE INTO distributors
                   (user_id,username,referral_code,sell_price) VALUES (?,?,?,?)""",
                (uid, uname, code, DIST_PRICE))
    cur.execute("UPDATE payment_requests SET status='approved',admin_id=?,updated_at=? WHERE id=?",
                (query.from_user.id, now_str(), req_id))
    conn.commit(); conn.close()
    try:
        await query.edit_message_caption(
            caption=(query.message.caption or "") + "\n\n✅ <b>총판 승인 완료</b>", parse_mode='HTML')
    except Exception: pass
    try:
        await context.bot.send_message(
            chat_id=uid,
            text=(f"🎉 <b>총판 권한 승인!</b>\n\n"
                  f"🔑 추천인 코드: <code>{code}</code>\n"
                  f"💰 회원 판매가: {DIST_PRICE:,}원\n\n"
                  f"총판 메뉴에서 계좌를 설정하고 코드를 공유하세요!"),
            parse_mode='HTML', reply_markup=main_kb(uid)
        )
    except Exception as e:
        print(f"총판 승인 알림 실패: {e}")


# ===== 관리자 메뉴 =====
async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("❌ 권한 없음"); return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 대기 목록", callback_data="adm_pending"),
         InlineKeyboardButton("👥 사용자 조회", callback_data="adm_users")],
        [InlineKeyboardButton("📊 재고 현황", callback_data="adm_stock"),
         InlineKeyboardButton("🏪 총판 목록", callback_data="adm_dists")],
    ])
    await update.message.reply_text("👨‍💼 <b>관리자 메뉴</b>", parse_mode='HTML', reply_markup=kb)

async def adm_pending_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.answer("권한 없음", show_alert=True); return
    conn = db(); cur = conn.cursor()
    cur.execute("""SELECT id,user_id,username,price,payment_type,created_at
                   FROM payment_requests WHERE status='pending'
                   ORDER BY created_at DESC LIMIT 10""")
    rows = cur.fetchall(); conn.close()
    if not rows:
        await query.edit_message_text("✅ 대기 중인 요청 없음.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="adm_back")]])); return
    text = "📥 <b>승인 대기 목록</b>\n\n"
    buttons = []
    for r in rows:
        rid, ruid, runame, rprice, rtype, rcreated = r
        label = "🏪 총판" if rtype == 'distributor' else "💳 라이센스"
        text += f"#{rid} {label} - {runame} ({rprice:,}원) {rcreated[:10]}\n"
        buttons.append([InlineKeyboardButton(f"#{rid} 처리", callback_data=f"adm_view_{rid}")])
    buttons.append([InlineKeyboardButton("🔙 뒤로", callback_data="adm_back")])
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(buttons))

async def adm_users_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.answer("권한 없음", show_alert=True); return
    await _adm_users_list(query)


async def adm_user_detail_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """특정 유저 상세"""
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    target_uid = int(query.data.split("_")[2])
    await _adm_user_detail(query, target_uid)


async def adm_revoke_license_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """라이센스 몰수"""
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    target_uid = int(query.data.split("_")[2])
    conn = db(); cur = conn.cursor()
    cur.execute("UPDATE user_licenses SET is_active=0 WHERE user_id=?", (target_uid,))
    cur.execute("UPDATE users SET expiredate=NULL WHERE id=?", (str(target_uid),))
    conn.commit(); conn.close()
    await query.answer("✅ 라이센스 몰수 완료", show_alert=True)
    try:
        await context.bot.send_message(
            chat_id=target_uid,
            text="⚠️ <b>라이센스가 관리자에 의해 회수되었습니다.</b>\n문의는 관리자에게 연락해주세요.",
            parse_mode='HTML'
        )
    except Exception: pass
    await _adm_user_detail(query, target_uid)


async def adm_revoke_dist_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """총판 권한 회수"""
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    target_uid = int(query.data.split("_")[3])
    conn = db(); cur = conn.cursor()
    cur.execute("UPDATE distributors SET is_active=0 WHERE user_id=?", (target_uid,))
    conn.commit(); conn.close()
    await query.answer("✅ 총판 권한 회수 완료", show_alert=True)
    try:
        await context.bot.send_message(
            chat_id=target_uid,
            text="⚠️ <b>총판 권한이 관리자에 의해 회수되었습니다.</b>",
            parse_mode='HTML'
        )
    except Exception: pass
    await _adm_user_detail(query, target_uid)


async def adm_withdraw_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """탈퇴 처리"""
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    target_uid = int(query.data.split("_")[2])
    conn = db(); cur = conn.cursor()
    cur.execute("UPDATE user_licenses SET is_active=0 WHERE user_id=?", (target_uid,))
    cur.execute("UPDATE production_users SET is_active=0 WHERE telegram_id=?", (target_uid,))
    cur.execute("UPDATE distributors SET is_active=0 WHERE user_id=?", (target_uid,))
    cur.execute("DELETE FROM members WHERE user_id=?", (target_uid,))
    cur.execute("UPDATE users SET is_registered=0, expiredate=NULL, query=NULL WHERE id=?", (str(target_uid),))
    conn.commit(); conn.close()
    await query.answer("✅ 탈퇴 처리 완료", show_alert=True)
    try:
        await context.bot.send_message(
            chat_id=target_uid,
            text="⚠️ <b>계정이 관리자에 의해 탈퇴 처리되었습니다.</b>\n다시 이용하려면 /start 후 재가입해주세요.",
            parse_mode='HTML'
        )
    except Exception: pass
    # 목록으로 돌아가기 - edit_message_text로 직접 처리
    await _adm_users_list(query)


async def _adm_user_detail(query, target_uid: int):
    """유저 상세 페이지를 query 객체로 직접 렌더링"""
    conn = db(); cur = conn.cursor()
    cur.execute("SELECT user_id, username, real_name, joined_at FROM members WHERE user_id=?", (target_uid,))
    mrow = cur.fetchone()
    cur.execute("SELECT license_key, is_active FROM user_licenses WHERE user_id=?", (target_uid,))
    lrow = cur.fetchone()
    cur.execute("""SELECT p.name FROM production_users p
                   WHERE p.telegram_id=? AND p.is_active=1
                   ORDER BY p.updated_at DESC LIMIT 1""", (target_uid,))
    idrow = cur.fetchone()
    cur.execute("SELECT query FROM users WHERE id=?", (str(target_uid),))
    urow = cur.fetchone()
    cur.execute("SELECT referral_code FROM distributors WHERE user_id=? AND is_active=1", (target_uid,))
    drow = cur.fetchone()
    conn.close()

    if not mrow:
        await query.edit_message_text("❌ 유저를 찾을 수 없습니다.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="adm_users")]])); return

    m_uid, m_uname, m_real, m_joined = mrow
    lic_status = "✅ 보유" if (lrow and lrow[1]) else "❌ 없음"
    id_name = idrow[0] if idrow else "미제작"
    query_code = urow[0] if urow else None
    web_link = f"{DOMAIN}/{query_code}" if query_code else "없음"
    dist_status = f"✅ ({drow[0]})" if drow else "❌"

    text = (f"👤 <b>유저 상세</b>\n\n"
            f"이름: {m_real or '-'}\n"
            f"@{m_uname or '-'} (<code>{m_uid}</code>)\n"
            f"가입일: {m_joined[:10]}\n"
            f"라이센스: {lic_status}\n"
            f"민증명: {id_name}\n"
            f"민증 링크: {web_link}\n"
            f"총판: {dist_status}")

    buttons = []
    if lrow and lrow[1]:
        buttons.append([InlineKeyboardButton("🚫 라이센스 몰수", callback_data=f"adm_revoke_{m_uid}")])
    if drow:
        buttons.append([InlineKeyboardButton("🏪 총판 권한 회수", callback_data=f"adm_revoke_dist_{m_uid}")])
    buttons.append([InlineKeyboardButton("🗑 탈퇴 처리", callback_data=f"adm_withdraw_{m_uid}")])
    if query_code:
        buttons.append([InlineKeyboardButton("🔗 민증 링크 보기", url=web_link)])
    buttons.append([InlineKeyboardButton("🔙 뒤로", callback_data="adm_users")])

    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(buttons))


async def _adm_users_list(query):
    """사용자 목록 직접 렌더링"""
    conn = db(); cur = conn.cursor()
    cur.execute("""SELECT m.user_id, m.username, m.real_name, m.joined_at,
                          p.name, ul.is_active
                   FROM members m
                   LEFT JOIN production_users p ON p.telegram_id=m.user_id AND p.is_active=1
                   LEFT JOIN user_licenses ul ON ul.user_id=m.user_id AND ul.is_active=1
                   ORDER BY m.joined_at DESC LIMIT 30""")
    rows = cur.fetchall(); conn.close()
    if not rows:
        await query.edit_message_text("👥 가입자 없음.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="adm_back")]])); return
    text = f"👥 <b>사용자 조회</b> (총 {len(rows)}명)\n\n"
    buttons = []
    for i, (m_uid, m_uname, m_real, m_joined, m_idname, m_lic) in enumerate(rows, 1):
        lic_icon = "✅" if m_lic else "❌"
        text += (f"{i}. <b>{m_real or '-'}</b> (@{m_uname or '-'})\n"
                 f"   민증: {m_idname or '미제작'} | 라이센스: {lic_icon} | {m_joined[:10]}\n")
        buttons.append([InlineKeyboardButton(
            f"{i}. {m_real or m_uname or str(m_uid)}",
            callback_data=f"adm_user_{m_uid}"
        )])
    buttons.append([InlineKeyboardButton("🔙 뒤로", callback_data="adm_back")])
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(buttons))

async def adm_stock_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    conn = db(); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM license_store WHERE is_sold=0")
    stock = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM members")
    total_members = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM user_licenses WHERE is_active=1")
    total_licensed = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM distributors WHERE is_active=1")
    total_dists = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*),SUM(price) FROM purchase_history WHERE date(purchased_at)=date('now')")
    today = cur.fetchone()
    conn.close()
    text = (f"📊 <b>현황</b>\n\n"
            f"🎫 라이센스 재고: {stock}개\n"
            f"👥 전체 회원: {total_members}명\n"
            f"✅ 라이센스 보유: {total_licensed}명\n"
            f"🏪 총판 수: {total_dists}명\n\n"
            f"📈 오늘 판매: {today[0]}건 / {(today[1] or 0):,}원")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 재고 충전", callback_data="adm_refill")],
        [InlineKeyboardButton("🔙 뒤로", callback_data="adm_back")]
    ])
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=kb)

async def adm_refill_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("재고 충전 중...")
    refill_license_stock()
    await adm_stock_cb(update, context)

async def adm_dists_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    conn = db(); cur = conn.cursor()
    cur.execute("""SELECT d.user_id, d.username, d.referral_code, d.sell_price,
                          COUNT(m.id) as member_count
                   FROM distributors d
                   LEFT JOIN members m ON m.distributor_id=d.id
                   WHERE d.is_active=1 GROUP BY d.id""")
    rows = cur.fetchall(); conn.close()
    if not rows:
        await query.edit_message_text("🏪 총판 없음.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="adm_back")]])); return
    text = "🏪 <b>총판 목록</b>\n\n"
    for d_uid, d_uname, d_code, d_price, d_cnt in rows:
        text += f"• @{d_uname} | 코드: <code>{d_code}</code> | 회원 {d_cnt}명\n"
    await query.edit_message_text(text, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 뒤로", callback_data="adm_back")]]))

async def adm_back_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 대기 목록", callback_data="adm_pending"),
         InlineKeyboardButton("👥 사용자 조회", callback_data="adm_users")],
        [InlineKeyboardButton("📊 재고 현황", callback_data="adm_stock"),
         InlineKeyboardButton("🏪 총판 목록", callback_data="adm_dists")],
    ])
    await query.edit_message_text("👨‍💼 <b>관리자 메뉴</b>", parse_mode='HTML', reply_markup=kb)


# ===== 도움말 =====
async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(
        "📖 <b>서비스 이용 가이드</b>\n\n"
        "1️⃣ <b>서비스 가입</b>\n"
        "   추천인 코드 입력(선택) → 실명 입력\n\n"
        "2️⃣ <b>라이센스 구매</b>\n"
        f"   영구 이용권 {LICENSE_PRICE:,}원\n"
        "   입금 후 스크린샷 전송 → 관리자 승인\n\n"
        "3️⃣ <b>민증 제작</b>\n"
        "   6단계 정보 입력 → 웹 링크 발급\n\n"
        "4️⃣ <b>민증 수정</b>\n"
        "   언제든 수정 가능\n\n"
        "❓ 문의는 관리자에게 연락하세요.",
        parse_mode='HTML', reply_markup=main_kb(uid)
    )


# ===== 텍스트 버튼 핸들러 =====
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id

    # 채널 가입 확인 (도움말 제외)
    if text != "❓ 도움말":
        if not await require_channel(update, context):
            return

    handlers = {
        "📝 서비스 가입":   lambda: join_start(update, context),
        "🛒 라이센스 구매": lambda: show_shop(update, context),
        "📋 내 라이센스":   lambda: my_license(update, context),
        "🆕 민증 제작":     lambda: id_create_start(update, context),
        "📝 내 민증 보기":  lambda: show_my_id(update, context),
        "✏️ 민증 수정":     lambda: id_edit_start(update, context),
        "❓ 도움말":        lambda: show_help(update, context),
        "🏪 총판 메뉴":     lambda: dist_menu(update, context),
        "💼 총판 신청":     lambda: dist_apply_start(update, context),
        "👨‍💼 관리자 메뉴":  lambda: admin_menu(update, context),
    }
    if text in handlers:
        result = handlers[text]()
        if asyncio.iscoroutine(result):
            ret = await result
            # ConversationHandler.END가 아닌 상태면 무시
            return
    else:
        await update.message.reply_text("❓ 아래 버튼을 사용해주세요.", reply_markup=main_kb(uid))


# ===== 메인 함수 =====
def main():
    if not TOKEN:
        print("❌ TELEGRAM_TOKEN 없음"); return

    app = Application.builder().token(TOKEN).post_init(post_init).build()

    # --- 가입 ConversationHandler ---
    join_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📝 서비스 가입$"), join_start)],
        states={
            JOIN_REFERRAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, join_referral)],
            JOIN_NAME:     [MessageHandler(filters.TEXT & ~filters.COMMAND, join_name)],
        },
        fallbacks=[CommandHandler("cancel", join_cancel),
                   MessageHandler(filters.Regex("^(❌ 취소|/cancel)$"), join_cancel)],
        per_user=True, per_chat=True, allow_reentry=True
    )

    # --- 라이센스 구매 ConversationHandler ---
    license_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🛒 라이센스 구매$"), show_shop)],
        states={
            UPLOAD_PROOF: [
                MessageHandler(filters.PHOTO, receive_proof),
                CallbackQueryHandler(cancel_purchase, pattern="^cancel_purchase$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_purchase),
                   CallbackQueryHandler(cancel_purchase, pattern="^cancel_purchase$")],
        per_user=True, per_chat=True, allow_reentry=True
    )

    # --- 총판 신청 ConversationHandler ---
    dist_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💼 총판 신청$"), dist_apply_start)],
        states={
            UPLOAD_PROOF_DIST: [MessageHandler(filters.PHOTO, receive_proof_dist)],
        },
        fallbacks=[CommandHandler("cancel", join_cancel)],
        per_user=True, per_chat=True, allow_reentry=True
    )

    # --- 총판 계좌 설정 ConversationHandler ---
    dist_bank_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(dist_set_bank_cb, pattern="^dist_set_bank$")],
        states={
            DIST_BANK_NAME:   [MessageHandler(filters.TEXT & ~filters.COMMAND, dist_bank_name)],
            DIST_BANK_ACCT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, dist_bank_acct)],
            DIST_BANK_HOLDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, dist_bank_holder)],
        },
        fallbacks=[CommandHandler("cancel", join_cancel)],
        per_user=True, per_chat=True, allow_reentry=True
    )

    # --- 민증 제작 ConversationHandler ---
    id_create_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🆕 민증 제작$"), id_create_start)],
        states={
            ID_NAME:   [MessageHandler(filters.TEXT & ~filters.COMMAND, id_name)],
            ID_SSN:    [MessageHandler(filters.TEXT & ~filters.COMMAND, id_ssn)],
            ID_ADDR:   [MessageHandler(filters.TEXT & ~filters.COMMAND, id_addr)],
            ID_DATE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, id_date)],
            ID_REGION: [MessageHandler(filters.TEXT & ~filters.COMMAND, id_region)],
            ID_PHOTO:  [MessageHandler(filters.PHOTO, id_photo)],
        },
        fallbacks=[CommandHandler("cancel", id_cancel),
                   MessageHandler(filters.Regex("^❌ 취소$"), id_cancel)],
        per_user=True, per_chat=True, allow_reentry=True
    )

    # --- 민증 수정 ConversationHandler ---
    id_edit_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^✏️ 민증 수정$"), id_edit_start)],
        states={
            EDIT_FIELD: [CallbackQueryHandler(edit_field_cb, pattern="^ef_")],
            EDIT_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_value),
                MessageHandler(filters.PHOTO, edit_value),
            ],
        },
        fallbacks=[CommandHandler("cancel", id_cancel)],
        per_user=True, per_chat=True, allow_reentry=True
    )

    # --- 관리자 거절 사유 ConversationHandler ---
    reject_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(reject_payment, pattern="^rej_\\d+$")],
        states={
            REJECT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_reject_reason)],
        },
        fallbacks=[],
        per_user=True, per_chat=True, allow_reentry=True
    )

    # 핸들러 등록 순서 중요 (ConversationHandler 먼저)
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(join_conv)
    app.add_handler(license_conv)
    app.add_handler(dist_conv)
    app.add_handler(dist_bank_conv)
    app.add_handler(id_create_conv)
    app.add_handler(id_edit_conv)
    app.add_handler(reject_conv)

    # 콜백 핸들러 (ConversationHandler 밖)
    app.add_handler(CallbackQueryHandler(approve_payment,    pattern="^apv_\\d+$"))
    app.add_handler(CallbackQueryHandler(approve_distributor,pattern="^dapv_\\d+_\\d+$"))
    app.add_handler(CallbackQueryHandler(adm_pending_cb,     pattern="^adm_pending$"))
    app.add_handler(CallbackQueryHandler(adm_users_cb,       pattern="^adm_users$"))
    app.add_handler(CallbackQueryHandler(adm_user_detail_cb, pattern="^adm_user_\\d+$"))
    app.add_handler(CallbackQueryHandler(adm_revoke_license_cb, pattern="^adm_revoke_\\d+$"))
    app.add_handler(CallbackQueryHandler(adm_revoke_dist_cb, pattern="^adm_revoke_dist_\\d+$"))
    app.add_handler(CallbackQueryHandler(adm_withdraw_cb,    pattern="^adm_withdraw_\\d+$"))
    app.add_handler(CallbackQueryHandler(adm_stock_cb,       pattern="^adm_stock$"))
    app.add_handler(CallbackQueryHandler(adm_refill_cb,      pattern="^adm_refill$"))
    app.add_handler(CallbackQueryHandler(adm_dists_cb,       pattern="^adm_dists$"))
    app.add_handler(CallbackQueryHandler(adm_back_cb,        pattern="^adm_back$"))
    app.add_handler(CallbackQueryHandler(dist_members_cb,    pattern="^dist_members$"))
    app.add_handler(CallbackQueryHandler(dist_pending_cb,    pattern="^dist_pending$"))
    app.add_handler(CallbackQueryHandler(dist_code_cb,       pattern="^dist_code$"))
    app.add_handler(CallbackQueryHandler(dist_back_cb,       pattern="^dist_back$"))

    # 텍스트 핸들러 (마지막)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # 에러 핸들러
    async def error_handler(update, context):
        if context.error is None: return
        print(f"[ERROR] {type(context.error).__name__}: {context.error}")
        traceback.print_exc()
    app.add_error_handler(error_handler)

    print("✅ 봇 시작!")

    async def run_async():
        async with app:
            await app.start()
            await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            while True:
                await asyncio.sleep(3600)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_async())
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        try:
            loop.run_until_complete(app.updater.stop())
            loop.run_until_complete(app.stop())
            loop.run_until_complete(app.shutdown())
        except Exception: pass
        loop.close()

if __name__ == "__main__":
    main()
