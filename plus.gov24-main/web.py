from flask import Flask, render_template, send_from_directory
import sqlite3
import datetime
import os
import io
from flask import Flask, render_template, send_file, send_from_directory, Response
from config import db_path

app = Flask(__name__)

# ========== QR 코드 생성 라우트 ========== #
@app.route('/qr/<path:data>')
def generate_qr(data):
    """서버에서 직접 QR 코드 이미지 생성"""
    try:
        import qrcode
        from PIL import Image

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)

        response = send_file(buf, mimetype='image/png')
        # 캐시 완전 비활성화
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        print(f"QR 생성 오류: {e}")
        return Response('QR Error', status=500)

# ========== 이미지 제공 라우트 ========== #
@app.route('/img/<filename>')
@app.route('/DB/saved_images/<filename>')
def serve_image(filename):
    """저장된 이미지 파일 제공 - /data 및 로컬 DB/ 모두 지원"""
    from flask import send_from_directory
    from config import images_path
    try:
        # images_path는 config에서 /data/saved_images 또는 DB/saved_images
        img_dir = images_path if os.path.isabs(images_path) else os.path.join(os.path.dirname(__file__), images_path)
        full_path = os.path.join(img_dir, filename)
        if not os.path.exists(full_path):
            return "Image not found", 404
        return send_from_directory(img_dir, filename)
    except Exception as e:
        print(f"이미지 서빙 오류: {e}")
        return "Error", 500

# ========== 루트 경로 ========== #
@app.route('/')
def home():
    return """
    <html>
    <head>
        <title>민증 제작 서비스</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: Arial; text-align: center; padding: 50px;">
        <h1>✅ 서버 작동 중</h1>
        <p>민증 제작 서비스 웹 서버입니다.</p>
        <p>URL 형식: /[쿼리코드]</p>
    </body>
    </html>
    """

# ========== Favicon 라우트 ========== #
@app.route('/favicon.ico')
def favicon():
    try:
        return send_from_directory(os.path.join(app.root_path, 'static', 'css'),
                                   'mobile_icon.ico', mimetype='image/vnd.microsoft.icon')
    except:
        return '', 204

# ========== 유효기간 체크 ========== #
def is_expired(time_str: str) -> bool:
    """만료 여부 체크"""
    try:
        server_time = datetime.datetime.now()
        expire_time = datetime.datetime.strptime(time_str, "%Y-%m-%d")
        return expire_time < server_time
    except:
        return False


# ========== 라우트: PASS 진위확인 결과 페이지 ========== #
@app.route('/pass/<key>')
def pass_verify(key):
    try:
        abs_db_path = db_path if os.path.isabs(db_path) else os.path.join(os.path.dirname(__file__), db_path)

        if not os.path.exists(abs_db_path):
            return render_template("error.html", title="시스템 오류", dese="데이터베이스 파일을 찾을 수 없습니다.")

        conn = sqlite3.connect(abs_db_path)
        cur = conn.cursor()

        # users 테이블에서 query로 유저 찾기
        cur.execute("SELECT id, expiredate FROM users WHERE query = ?", (key,))
        user_row = cur.fetchone()

        if not user_row:
            conn.close()
            return render_template("error.html", title="접속 실패", dese="존재하지 않는 링크입니다.")

        user_id = user_row[0]
        expire_date = user_row[1]

        if expire_date and is_expired(expire_date):
            conn.close()
            return render_template("error.html", title="접속 실패", dese="라이센스 유효기간이 만료되었습니다.")

        # 민증 정보 가져오기
        cur.execute("""
            SELECT name, ssn FROM production_users
            WHERE telegram_id = ? AND is_active = 1
            ORDER BY updated_at DESC LIMIT 1
        """, (user_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            return render_template("error.html", title="접속 실패", dese="제작된 민증이 없습니다.")

        name, ssn = row

        # 주민번호 앞자리로 생년월일 포맷 (예: 2007.10.15)
        try:
            tmp = ssn.replace("-", "")
            if len(tmp) >= 6:
                # 앞 2자리로 세기 판별 (00~23 → 2000년대, 나머지 → 1900년대)
                year2 = int(tmp[0:2])
                century = "20" if year2 <= 23 else "19"
                birthdate = f"{century}{tmp[0:2]}.{tmp[2:4]}.{tmp[4:6]}"
            else:
                birthdate = ssn
        except Exception:
            birthdate = ssn

        return render_template("pass.html", name=name, birthdate=birthdate)

    except Exception as e:
        print(f"❌ PASS 페이지 오류: {e}")
        import traceback
        traceback.print_exc()
        return render_template("error.html", title="시스템 오류", dese="예기치 못한 오류가 발생했습니다.")


# ========== 라우트: query 기반 민증 조회 ========== #
@app.route('/<key>')
def index(key):
    try:
        print(f"\n=== 민증 접속 시도: {key} ===")
        
        # DB 경로를 절대 경로로 변환
        abs_db_path = db_path if os.path.isabs(db_path) else os.path.join(os.path.dirname(__file__), db_path)
        print(f"DB 경로: {abs_db_path}")
        
        if not os.path.exists(abs_db_path):
            print(f"❌ DB 파일 없음: {abs_db_path}")
            return render_template("error.html", 
                                 title="시스템 오류", 
                                 dese="데이터베이스 파일을 찾을 수 없습니다.")
        
        conn = sqlite3.connect(abs_db_path)
        cur = conn.cursor()

        # 1. users 테이블에서 query로 유저 찾기
        print(f"1. users 테이블에서 query='{key}' 검색 중...")
        cur.execute("SELECT id, expiredate FROM users WHERE query = ?", (key,))
        user_row = cur.fetchone()
        
        if not user_row:
            conn.close()
            print("   ❌ 해당 query를 찾을 수 없음")
            return render_template("error.html", 
                                 title="접속 실패", 
                                 dese="존재하지 않는 링크입니다.")
        
        user_id = user_row[0]
        expire_date = user_row[1]
        print(f"   ✅ 찾음! user_id={user_id}, expire={expire_date}")
        
        # 2. 만료 체크
        if expire_date and is_expired(expire_date):
            conn.close()
            print("   ❌ 라이센스 만료됨")
            return render_template("error.html", 
                                 title="접속 실패", 
                                 dese="라이센스 유효기간이 만료되었습니다.")
        
        # 3. production_users에서 민증 정보 가져오기 (telegram_id 사용!)
        print(f"2. production_users에서 telegram_id={user_id} 검색 중...")
        cur.execute("""
            SELECT name, ssn, address, issue_date, region, image_path, created_at
            FROM production_users
            WHERE telegram_id = ? AND is_active = 1
            ORDER BY updated_at DESC LIMIT 1
        """, (user_id,))
        row = cur.fetchone()
        
        if not row:
            conn.close()
            print("   ❌ 민증 정보 없음")
            return render_template("error.html", 
                                 title="접속 실패", 
                                 dese="제작된 민증이 없습니다. 먼저 민증을 제작해주세요.")
        
        conn.close()
        
        # 4. 데이터 언팩
        name, ssn, address, issue_date, region, image_path, created_at = row
        print(f"3. ✅ 민증 정보 로드 성공!")
        print(f"   이름: {name}, 주소: {address}")
        print(f"   이미지 원본 경로: {image_path}")

        # 5. 주민번호 앞자리로 생년월일 포맷
        try:
            tmp = ssn.split("-")[0]
            if len(tmp) >= 6:
                date_fmt = f"{tmp[0:2]}.{tmp[2:4]}.{tmp[4:6]}"
            else:
                date_fmt = issue_date
        except:
            date_fmt = issue_date

        # 6. 이미지 경로를 웹 URL로 변환
        image_url = ""
        if image_path:
            filename = os.path.basename(image_path.replace("\\", "/"))
            image_url = f"/img/{filename}"

        # 7. PASS 확인 URL 생성
        from config import domain
        pass_url = f"{domain}/pass/{key}"

        # 8. 템플릿 렌더링
        print(f"4. ✅ 템플릿 렌더링 시작")
        return render_template("sex.html",
                             name=name,
                             num=ssn,
                             date=date_fmt,
                             juso=address,
                             make=issue_date,
                             jiname=region,
                             imgurl=image_url,
                             pass_url=pass_url)

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return render_template("error.html", 
                             title="시스템 오류", 
                             dese="예기치 못한 오류가 발생했습니다. 관리자에게 문의하세요.")


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    print(f"\n{'='*60}")
    print(f"🌐 웹 서버 시작: http://localhost:{port}")
    print(f"{'='*60}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
