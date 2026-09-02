import sqlite3

conn = sqlite3.connect('DB/database.db')
cur = conn.cursor()

print("=" * 80)
print("PRODUCTION_USERS 테이블 상세 정보:")
print("=" * 80)
cur.execute('SELECT discord_id, name, ssn, address, issue_date, region, image_path, created_at FROM production_users')
for row in cur.fetchall():
    print(f"DiscordID: {row[0]}")
    print(f"  Name: {row[1]}")
    print(f"  SSN: {row[2]}")
    print(f"  Address: {row[3]}")
    print(f"  Issue Date: {row[4]}")
    print(f"  Region: {row[5]}")
    print(f"  Image Path: {row[6]}")
    print(f"  Created At: {row[7]}")
    print("-" * 80)

print("\n" + "=" * 80)
print("테스트: user_id 1310699306281336874로 조회")
print("=" * 80)
cur.execute("""SELECT name, ssn, address, issue_date, region, image_path, created_at
               FROM production_users
               WHERE discord_id = ?""", (1310699306281336874,))
row = cur.fetchone()
if row:
    print(f"✅ 찾음!")
    print(f"  Name: {row[0]}")
    print(f"  SSN: {row[1]}")
    print(f"  Address: {row[2]}")
    print(f"  Issue Date: {row[3]}")
    print(f"  Region: {row[4]}")
    print(f"  Image Path: {row[5]}")
else:
    print("❌ 못 찾음")

conn.close()
