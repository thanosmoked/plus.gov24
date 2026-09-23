import sqlite3

conn = sqlite3.connect('DB/database.db')
cur = conn.cursor()

print("=" * 50)
print("USERS 테이블:")
print("=" * 50)
cur.execute('SELECT id, query, expiredate, osname FROM users')
for row in cur.fetchall():
    print(f"ID: {row[0]}, Query: {row[1]}, Expire: {row[2]}, OSName: {row[3]}")

print("\n" + "=" * 50)
print("LICENSES 테이블:")
print("=" * 50)
cur.execute('SELECT license_key, user_id, expire_date FROM licenses')
for row in cur.fetchall():
    print(f"Key: {row[0]}, UserID: {row[1]}, Expire: {row[2]}")

print("\n" + "=" * 50)
print("PRODUCTION_USERS 테이블:")
print("=" * 50)
cur.execute('SELECT discord_id, name, ssn FROM production_users')
for row in cur.fetchall():
    print(f"DiscordID: {row[0]}, Name: {row[1]}, SSN: {row[2]}")

conn.close()
