# database_schema.py
import sqlite3
import os
import random
import string
from datetime import datetime, timedelta
from config import db_path, AUTO_LICENSE_STOCK, images_path, proofs_path

def gen_key(n=16):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=n))

def gen_query(n=12):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=n))

def gen_referral(n=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=n))

def init_database():
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    os.makedirs(images_path, exist_ok=True)
    os.makedirs(proofs_path, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. admins
    cur.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        added_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    # 2. users - 가입 상태 포함
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT,
        real_name TEXT,
        expiredate TEXT,
        query TEXT,
        osname TEXT,
        is_registered INTEGER DEFAULT 0,
        referral_used TEXT,
        distributor_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT
    )""")

    # 3. production_users
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
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        is_active INTEGER DEFAULT 1
    )""")

    # 4. license_store - 영구권만
    cur.execute("""
    CREATE TABLE IF NOT EXISTS license_store (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        license_key TEXT UNIQUE NOT NULL,
        price INTEGER NOT NULL DEFAULT 5000,
        is_sold INTEGER DEFAULT 0,
        sold_to INTEGER,
        sold_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    # 5. payment_requests
    cur.execute("""
    CREATE TABLE IF NOT EXISTS payment_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT,
        price INTEGER NOT NULL DEFAULT 5000,
        payment_image_path TEXT,
        payment_type TEXT DEFAULT 'license',
        status TEXT DEFAULT 'pending',
        admin_response TEXT,
        admin_id INTEGER,
        license_key TEXT,
        distributor_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    # 6. purchase_history
    cur.execute("""
    CREATE TABLE IF NOT EXISTS purchase_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT,
        license_key TEXT NOT NULL,
        price INTEGER NOT NULL,
        payment_method TEXT DEFAULT 'bank_transfer',
        purchased_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    # 7. user_licenses - 영구권 (expire_date = 9999-12-31)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_licenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        license_key TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        activated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    # 8. distributors - 총판
    cur.execute("""
    CREATE TABLE IF NOT EXISTS distributors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        username TEXT,
        referral_code TEXT UNIQUE NOT NULL,
        bank_name TEXT,
        bank_account TEXT,
        bank_holder TEXT,
        sell_price INTEGER DEFAULT 3500,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    # 9. members - 가입한 사용자 (추천인 코드 사용)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        username TEXT,
        real_name TEXT,
        distributor_id INTEGER,
        referral_code TEXT,
        joined_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    conn.commit()
    _migrate(cur, conn)
    conn.close()
    print("✅ 데이터베이스 초기화 완료")

def _migrate(cur, conn):
    migrations = [
        ('users', [
            ('real_name', 'TEXT'),
            ('is_registered', 'INTEGER DEFAULT 0'),
            ('referral_used', 'TEXT'),
            ('distributor_id', 'INTEGER'),
            ('query', 'TEXT'),
            ('expiredate', 'TEXT'),
            ('osname', 'TEXT'),
            ('username', 'TEXT'),
            ('created_at', 'TEXT'),
            ('updated_at', 'TEXT'),
        ]),
        ('production_users', [
            ('telegram_id', 'INTEGER'),
            ('updated_at', 'TEXT'),
            ('is_active', 'INTEGER DEFAULT 1'),
            ('issue_date', 'TEXT'),
            ('region', 'TEXT'),
            ('image_path', 'TEXT'),
            ('ssn', 'TEXT'),
            ('address', 'TEXT'),
        ]),
        ('admins', [('username', 'TEXT'), ('added_at', 'TEXT')]),
        ('payment_requests', [
            ('payment_type', "TEXT DEFAULT 'license'"),
            ('distributor_id', 'INTEGER'),
        ]),
        ('distributors', [
            ('bank_name', 'TEXT'),
            ('bank_account', 'TEXT'),
            ('bank_holder', 'TEXT'),
        ]),
    ]
    for table, cols in migrations:
        for col_name, col_type in cols:
            try:
                cur.execute(f"SELECT {col_name} FROM {table} LIMIT 1")
            except sqlite3.OperationalError:
                try:
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
                    conn.commit()
                except Exception:
                    pass

def refill_license_stock():
    """영구 라이센스 재고 충전 (무제한 - 필요할 때만 생성)"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM license_store WHERE is_sold=0")
    current = cur.fetchone()[0]
    needed = max(0, AUTO_LICENSE_STOCK - current)
    if needed > 0:
        for _ in range(needed):
            cur.execute(
                "INSERT INTO license_store (license_key, price) VALUES (?, ?)",
                (gen_key(16), 5000)
            )
        conn.commit()
    conn.close()

def get_license_stock():
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM license_store WHERE is_sold=0")
    count = cur.fetchone()[0]
    conn.close()
    return count

def get_distributor(user_id: int):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM distributors WHERE user_id=? AND is_active=1", (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        cols = ['id','user_id','username','referral_code','bank_name','bank_account','bank_holder','sell_price','is_active','created_at']
        return dict(zip(cols, row))
    return None

def get_distributor_by_code(code: str):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM distributors WHERE referral_code=? AND is_active=1", (code.upper(),))
    row = cur.fetchone()
    conn.close()
    if row:
        cols = ['id','user_id','username','referral_code','bank_name','bank_account','bank_holder','sell_price','is_active','created_at']
        return dict(zip(cols, row))
    return None

def is_member(user_id: int) -> bool:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM members WHERE user_id=?", (user_id,))
    r = cur.fetchone()
    conn.close()
    return r is not None

def has_license(user_id: int) -> bool:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM user_licenses WHERE user_id=? AND is_active=1", (user_id,))
    r = cur.fetchone()
    conn.close()
    return r is not None

if __name__ == "__main__":
    init_database()
    refill_license_stock()
    print(f"재고: {get_license_stock()}개")
