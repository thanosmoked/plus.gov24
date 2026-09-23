import sqlite3
import datetime
import os
import io
import functools
import hashlib
import uuid

from flask import (Flask, render_template, send_file, send_from_directory,
                   Response, request, session, redirect, url_for, jsonify,
                   make_response)
from config import db_path

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", os.urandom(24).hex())

# ------------------------------------------------------------------ #
#  헬퍼
# ------------------------------------------------------------------ #
def _abs(path: str) -> str:
    """상대경로 → 절대경로"""
    return path if os.path.isabs(path) else os.path.join(os.path.dirname(__file__), path)


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def _get_conn():
    return sqlite3.connect(_abs(db_path))


# ------------------------------------------------------------------ #
#  인증 데코레이터
# ------------------------------------------------------------------ #
def login_required(f):
    """일반 유저 로그인 필요"""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('web_user'):
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """관리자 로그인 필요 (/admin/login 세션)"""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin1234")


# ------------------------------------------------------------------ #
#  회원가입 / 로그인 / 로그아웃
# ------------------------------------------------------------------ #
@app.route('/register', methods=['GET', 'POST'])
def register():
    if session.get('web_user'):
        return redirect(url_for('home'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        password2 = request.form.get('password2', '').strip()

        if not username or not password:
            error = '아이디와 비밀번호를 입력해주세요.'
        elif len(username) < 3:
            error = '아이디는 3자 이상이어야 합니다.'
        elif len(password) < 4:
            error = '비밀번호는 4자 이상이어야 합니다.'
        elif password != password2:
            error = '비밀번호가 일치하지 않습니다.'
        else:
            from database_schema import init_database, gen_query
            init_database()
            conn = _get_conn()
            cur = conn.cursor()

            # 중복 아이디 체크
            cur.execute("SELECT id FROM web_accounts WHERE username=?", (username,))
            if cur.fetchone():
                error = '이미 사용 중인 아이디입니다.'
                conn.close()
            else:
                # device_id + users 행 생성
                device_id = "web_" + str(uuid.uuid4()).replace("-", "")[:20]
                query_code = gen_query(12)
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                cur.execute(
                    "INSERT INTO users (id, username, query, expiredate, osname) VALUES (?,?,?,?,?)",
                    (device_id, username, query_code, "9999-12-31", "web")
                )
                # 기본 더미 민증 생성
                cur.execute("""
                    INSERT INTO production_users
                    (telegram_id, name, ssn, address, issue_date, region,
                     image_path, created_at, updated_at, is_active)
                    VALUES (?,?,?,?,?,?,?,?,?,1)
                """, (device_id, username, "000101-1000000",
                      "서울특별시 종로구 청와대로 1",
                      "2025.01.01", "서울특별시장", "", now, now))
                # web_accounts 행 생성
                cur.execute(
                    "INSERT INTO web_accounts (username, password_hash, device_id) VALUES (?,?,?)",
                    (username, _hash(password), device_id)
                )
                conn.commit()
                conn.close()

                session['web_user'] = username
                session['web_device_id'] = device_id
                return redirect(url_for('home'))

    return render_template('register.html', error=error)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('web_user'):
        return redirect(url_for('home'))

    error = None
    next_url = request.args.get('next', url_for('home'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            error = '아이디와 비밀번호를 입력해주세요.'
        else:
            conn = _get_conn()
            cur = conn.cursor()
            cur.execute(
                "SELECT device_id FROM web_accounts WHERE username=? AND password_hash=?",
                (username, _hash(password))
            )
            row = cur.fetchone()
            conn.close()

            if not row:
                error = '아이디 또는 비밀번호가 올바르지 않습니다.'
            else:
                session['web_user'] = username
                session['web_device_id'] = row[0]
                return redirect(next_url)

    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.pop('web_user', None)
    session.pop('web_device_id', None)
    return redirect(url_for('login'))


# ------------------------------------------------------------------ #
#  관리자 로그인 / 로그아웃
# ------------------------------------------------------------------ #
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        pw = request.form.get('password', '')
        if pw == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('mygov'))
        error = '비밀번호가 올바르지 않습니다.'
    return render_template('admin_login.html', error=error)


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))


# ------------------------------------------------------------------ #
#  QR 코드
# ------------------------------------------------------------------ #
@app.route('/qr/<path:data>')
def generate_qr(data):
    try:
        import qrcode
        qr = qrcode.QRCode(version=1,
                           error_correction=qrcode.constants.ERROR_CORRECT_M,
                           box_size=8, border=2)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        resp = send_file(buf, mimetype='image/png')
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
        return resp
    except Exception as e:
        print(f"QR 생성 오류: {e}")
        return Response('QR Error', status=500)


# ------------------------------------------------------------------ #
#  이미지 서빙
# ------------------------------------------------------------------ #
@app.route('/img/<filename>')
@app.route('/DB/saved_images/<filename>')
@login_required
def serve_image(filename):
    from config import images_path
    try:
        img_dir = _abs(images_path)
        full_path = os.path.join(img_dir, filename)
        if not os.path.exists(full_path):
            return "Image not found", 404

        # 요청한 유저가 이 이미지를 소유하는지 확인
        device_id = session.get('web_device_id', '')
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM production_users WHERE telegram_id=? AND image_path LIKE ? AND is_active=1",
            (device_id, f"%{filename}")
        )
        owns = cur.fetchone()
        conn.close()

        # 관리자이거나 본인 이미지일 때만 허용
        if not owns and not session.get('admin_logged_in'):
            return "Forbidden", 403

        return send_from_directory(img_dir, filename)
    except Exception as e:
        print(f"이미지 서빙 오류: {e}")
        return "Error", 500


# ------------------------------------------------------------------ #
#  홈 (로그인 필수)
# ------------------------------------------------------------------ #
@app.route('/')
@login_required
def home():
    from database_schema import init_database
    init_database()
    return render_template("index.html")


# ------------------------------------------------------------------ #
#  MyGOV: 내 민증 조회 (로그인 유저 자신의 데이터만)
# ------------------------------------------------------------------ #
@app.route('/mygov')
@login_required
def mygov():
    try:
        device_id = session.get('web_device_id', '')
        abs_db_path = _abs(db_path)

        if not os.path.exists(abs_db_path):
            return render_template("error.html", title="오류", dese="데이터베이스를 찾을 수 없습니다.")

        conn = _get_conn()
        cur = conn.cursor()
        # 자신의 device_id에 해당하는 민증만 조회
        cur.execute("""
            SELECT p.id, p.name, p.ssn, p.address, p.issue_date, p.region,
                   p.image_path, u.query
            FROM production_users p
            JOIN users u ON u.id = p.telegram_id
            WHERE p.is_active = 1 AND u.id = ?
            ORDER BY p.updated_at DESC
        """, (device_id,))
        rows = cur.fetchall()
        conn.close()

        records = []
        for r in rows:
            pid, name, ssn, address, issue_date, region, image_path, query = r
            img_url = ""
            if image_path:
                img_url = "/img/" + os.path.basename(image_path.replace("\\", "/"))
            records.append({
                "id": pid, "name": name, "ssn": ssn,
                "address": address, "issue_date": issue_date,
                "region": region, "img_url": img_url, "query": query or ""
            })
        return render_template("mygov.html", records=records)
    except Exception as e:
        import traceback; traceback.print_exc()
        return render_template("error.html", title="오류", dese=str(e))


# ------------------------------------------------------------------ #
#  MyGOV: 민증 수정 (로그인 유저 본인만)
# ------------------------------------------------------------------ #
@app.route('/mygov/update', methods=['POST'])
@login_required
def mygov_update():
    try:
        pid        = request.form.get('id', '').strip()
        name       = request.form.get('name', '').strip()
        ssn        = request.form.get('ssn', '').strip()
        address    = request.form.get('address', '').strip()
        issue_date = request.form.get('issue_date', '').strip()
        region     = request.form.get('region', '').strip()

        if not pid:
            return render_template("error.html", title="오류", dese="잘못된 요청입니다.")

        device_id = session.get('web_device_id', '')
        conn = _get_conn()
        cur = conn.cursor()

        # 본인 소유 레코드인지 검증
        cur.execute("""
            SELECT p.id FROM production_users p
            JOIN users u ON u.id = p.telegram_id
            WHERE p.id=? AND u.id=? AND p.is_active=1
        """, (pid, device_id))
        if not cur.fetchone():
            conn.close()
            return render_template("error.html", title="권한 없음", dese="본인의 민증만 수정할 수 있습니다.")

        # 이미지 업로드
        from config import images_path as img_dir
        new_image_path = None
        if 'image' in request.files:
            f = request.files['image']
            if f and f.filename:
                ext = os.path.splitext(f.filename)[1].lower()
                if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
                    ext = '.jpg'
                fname = str(uuid.uuid4()) + ext
                abs_img_dir = _abs(img_dir)
                os.makedirs(abs_img_dir, exist_ok=True)
                save_path = os.path.join(abs_img_dir, fname)
                f.save(save_path)
                new_image_path = save_path

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if new_image_path:
            cur.execute("""
                UPDATE production_users
                SET name=?, ssn=?, address=?, issue_date=?, region=?,
                    image_path=?, updated_at=?
                WHERE id=?
            """, (name, ssn, address, issue_date, region, new_image_path, now, pid))
        else:
            cur.execute("""
                UPDATE production_users
                SET name=?, ssn=?, address=?, issue_date=?, region=?, updated_at=?
                WHERE id=?
            """, (name, ssn, address, issue_date, region, now, pid))

        conn.commit()
        conn.close()
        return redirect('/mygov?saved=1')
    except Exception as e:
        import traceback; traceback.print_exc()
        return render_template("error.html", title="수정 실패", dese=str(e))


# ------------------------------------------------------------------ #
#  모바일 확인 서비스: 민증 key 반환 (로그인 필수, 본인 key만)
# ------------------------------------------------------------------ #
@app.route('/mobile-id-key')
@login_required
def mobile_id_key():
    try:
        device_id = session.get('web_device_id', '')
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("SELECT query FROM users WHERE id=?", (device_id,))
        row = cur.fetchone()
        conn.close()
        if not row or not row[0]:
            return jsonify({'error': 'no_id'}), 404
        return jsonify({'key': row[0]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ------------------------------------------------------------------ #
#  관리자 전용: 전체 민증 목록
# ------------------------------------------------------------------ #
@app.route('/admin/mygov')
@admin_required
def admin_mygov():
    try:
        abs_db_path = _abs(db_path)
        if not os.path.exists(abs_db_path):
            return render_template("error.html", title="오류", dese="데이터베이스를 찾을 수 없습니다.")
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT p.id, p.name, p.ssn, p.address, p.issue_date, p.region,
                   p.image_path, u.query
            FROM production_users p
            JOIN users u ON u.id = p.telegram_id
            WHERE p.is_active = 1
            ORDER BY p.updated_at DESC
        """)
        rows = cur.fetchall()
        conn.close()
        records = []
        for r in rows:
            pid, name, ssn, address, issue_date, region, image_path, query = r
            img_url = ""
            if image_path:
                img_url = "/img/" + os.path.basename(image_path.replace("\\", "/"))
            records.append({
                "id": pid, "name": name, "ssn": ssn,
                "address": address, "issue_date": issue_date,
                "region": region, "img_url": img_url, "query": query or ""
            })
        return render_template("mygov.html", records=records, is_admin=True)
    except Exception as e:
        import traceback; traceback.print_exc()
        return render_template("error.html", title="오류", dese=str(e))


# ------------------------------------------------------------------ #
#  Favicon
# ------------------------------------------------------------------ #
@app.route('/favicon.ico')
def favicon():
    try:
        return send_from_directory(os.path.join(app.root_path, 'static', 'css'),
                                   'mobile_icon.ico', mimetype='image/vnd.microsoft.icon')
    except Exception:
        return '', 204


# ------------------------------------------------------------------ #
#  유효기간 체크
# ------------------------------------------------------------------ #
def is_expired(time_str: str) -> bool:
    try:
        return datetime.datetime.strptime(time_str, "%Y-%m-%d") < datetime.datetime.now()
    except Exception:
        return False


# ------------------------------------------------------------------ #
#  PASS 진위확인 (공개 — key를 아는 사람만 접근)
# ------------------------------------------------------------------ #
@app.route('/pass/<key>')
def pass_verify(key):
    try:
        abs_db_path = _abs(db_path)
        if not os.path.exists(abs_db_path):
            return render_template("error.html", title="시스템 오류", dese="데이터베이스 파일을 찾을 수 없습니다.")

        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, expiredate FROM users WHERE query=?", (key,))
        user_row = cur.fetchone()

        if not user_row:
            conn.close()
            return render_template("error.html", title="접속 실패", dese="존재하지 않는 링크입니다.")

        user_id, expire_date = user_row
        if expire_date and is_expired(expire_date):
            conn.close()
            return render_template("error.html", title="접속 실패", dese="라이센스 유효기간이 만료되었습니다.")

        cur.execute("""
            SELECT name, ssn FROM production_users
            WHERE telegram_id=? AND is_active=1
            ORDER BY updated_at DESC LIMIT 1
        """, (user_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            return render_template("error.html", title="접속 실패", dese="제작된 민증이 없습니다.")

        name, ssn = row
        try:
            tmp = ssn.replace("-", "")
            if len(tmp) >= 6:
                year2 = int(tmp[0:2])
                century = "20" if year2 <= 23 else "19"
                birthdate = f"{century}{tmp[0:2]}.{tmp[2:4]}.{tmp[4:6]}"
            else:
                birthdate = ssn
        except Exception:
            birthdate = ssn

        return render_template("pass.html", name=name, birthdate=birthdate)

    except Exception as e:
        import traceback; traceback.print_exc()
        return render_template("error.html", title="시스템 오류", dese="예기치 못한 오류가 발생했습니다.")


# ------------------------------------------------------------------ #
#  민증 조회 — query key 기반 (로그인 필수 + 본인 key만)
# ------------------------------------------------------------------ #
@app.route('/<key>')
@login_required
def index(key):
    try:
        device_id = session.get('web_device_id', '')
        abs_db_path = _abs(db_path)

        if not os.path.exists(abs_db_path):
            return render_template("error.html", title="시스템 오류",
                                   dese="데이터베이스 파일을 찾을 수 없습니다.")

        conn = _get_conn()
        cur = conn.cursor()

        # 1. query로 유저 찾기
        cur.execute("SELECT id, expiredate FROM users WHERE query=?", (key,))
        user_row = cur.fetchone()

        if not user_row:
            conn.close()
            return render_template("error.html", title="접속 실패", dese="존재하지 않는 링크입니다.")

        user_id, expire_date = user_row

        # 2. 본인 key인지 확인 (관리자는 예외)
        if user_id != device_id and not session.get('admin_logged_in'):
            conn.close()
            return render_template("error.html", title="접근 거부",
                                   dese="본인의 민증만 조회할 수 있습니다.")

        # 3. 만료 체크
        if expire_date and is_expired(expire_date) and not str(user_id).startswith("web_"):
            conn.close()
            return render_template("error.html", title="접속 실패",
                                   dese="라이센스 유효기간이 만료되었습니다.")

        # 4. 민증 정보
        cur.execute("""
            SELECT name, ssn, address, issue_date, region, image_path, created_at
            FROM production_users
            WHERE telegram_id=? AND is_active=1
            ORDER BY updated_at DESC LIMIT 1
        """, (user_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            return render_template("error.html", title="접속 실패",
                                   dese="제작된 민증이 없습니다. 먼저 민증을 제작해주세요.")

        name, ssn, address, issue_date, region, image_path, created_at = row

        # 5. 생년월일 포맷
        try:
            tmp = ssn.split("-")[0]
            date_fmt = f"{tmp[0:2]}.{tmp[2:4]}.{tmp[4:6]}" if len(tmp) >= 6 else issue_date
        except Exception:
            date_fmt = issue_date

        # 6. 이미지 URL
        image_url = ""
        if image_path:
            image_url = "/img/" + os.path.basename(image_path.replace("\\", "/"))

        # 7. PASS URL
        from config import domain
        pass_url = f"{domain}/pass/{key}"

        return render_template("sex.html",
                               name=name, num=ssn, date=date_fmt,
                               juso=address, make=issue_date,
                               jiname=region, imgurl=image_url,
                               pass_url=pass_url)

    except Exception as e:
        import traceback; traceback.print_exc()
        return render_template("error.html", title="시스템 오류",
                               dese="예기치 못한 오류가 발생했습니다.")


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    print(f"\n{'='*60}")
    print(f"🌐 웹 서버 시작: http://localhost:{port}")
    print(f"{'='*60}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
