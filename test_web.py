#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""웹 서버 테스트"""

print("=" * 50)
print("웹 서버 테스트 시작...")
print("=" * 50)

try:
    print("1. config.py import 중...")
    from config import db_path, domain
    print(f"   ✅ DB 경로: {db_path}")
    print(f"   ✅ 도메인: {domain}")
except Exception as e:
    print(f"   ❌ config.py import 실패: {e}")
    import traceback
    traceback.print_exc()

try:
    print("\n2. web.py import 중...")
    from web import app
    print("   ✅ Flask app import 성공")
except Exception as e:
    print(f"   ❌ web.py import 실패: {e}")
    import traceback
    traceback.print_exc()

try:
    print("\n3. 데이터베이스 확인 중...")
    import sqlite3
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM users")
    user_count = cur.fetchone()[0]
    print(f"   ✅ users 테이블: {user_count}개 레코드")
    
    cur.execute("SELECT COUNT(*) FROM production_users")
    prod_count = cur.fetchone()[0]
    print(f"   ✅ production_users 테이블: {prod_count}개 레코드")
    
    if user_count > 0:
        cur.execute("SELECT id, query FROM users LIMIT 1")
        row = cur.fetchone()
        print(f"   📝 첫 번째 user: id={row[0]}, query={row[1]}")
        test_url = f"{domain}/{row[1]}"
        print(f"   🔗 테스트 URL: {test_url}")
    
    conn.close()
except Exception as e:
    print(f"   ❌ 데이터베이스 확인 실패: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 50)
print("테스트 완료!")
print("=" * 50)
