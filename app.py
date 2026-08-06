import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import psycopg
from psycopg.rows import dict_row
import sqlite3

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'super_secret_school_system_key_2026')

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ฟังก์ชันเชื่อมต่อฐานข้อมูล (รองรับทั้ง PostgreSQL บน Cloud และ SQLite ในเครื่อง)
def get_db_connection():
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        conn = psycopg.connect(database_url, sslmode='require')
        return conn
    else:
        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        # PostgreSQL Syntax
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                fullname TEXT NOT NULL,
                student_id TEXT UNIQUE,
                major TEXT,
                height REAL,
                weight REAL,
                role TEXT NOT NULL,
                status TEXT DEFAULT 'รอตรวจสอบ',
                profile_image TEXT DEFAULT 'default.png'
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS allowed_students (
                id SERIAL PRIMARY KEY,
                student_id TEXT UNIQUE NOT NULL,
                fullname TEXT NOT NULL,
                major TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS announcements (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weight_history (
                id SERIAL PRIMARY KEY,
                student_id TEXT NOT NULL,
                weight REAL NOT NULL,
                height REAL NOT NULL,
                bmi REAL NOT NULL,
                record_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    else:
        # SQLite Syntax
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                fullname TEXT NOT NULL,
                student_id TEXT UNIQUE,
                major TEXT,
                height REAL,
                weight REAL,
                role TEXT NOT NULL,
                status TEXT DEFAULT 'รอตรวจสอบ',
                profile_image TEXT DEFAULT 'default.png'
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS allowed_students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT UNIQUE NOT NULL,
                fullname TEXT NOT NULL,
                major TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                date TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weight_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                weight REAL NOT NULL,
                height REAL NOT NULL,
                bmi REAL NOT NULL,
                record_date TEXT NOT NULL
            )
        ''')
    
    # สร้างบัญชีคุณครูเริ่มต้น (ถ้ายังไม่มี)
    if database_url:
        cursor.execute("SELECT * FROM users WHERE role = 'teacher'")
    else:
        cursor.execute("SELECT * FROM users WHERE role = 'teacher'")
    teacher = cursor.fetchone()
    
    if not teacher:
        hashed_pw = generate_password_hash('teacher1234')
        if database_url:
            cursor.execute("INSERT INTO users (username, password, fullname, role, status) VALUES (%s, %s, %s, %s, %s)",
                           ('teacher_admin', hashed_pw, 'อาจารย์ผู้ดูแลระบบ', 'teacher', 'อนุมัติแล้ว'))
        else:
            cursor.execute("INSERT INTO users (username, password, fullname, role, status) VALUES (?, ?, ?, ?, ?)",
                           ('teacher_admin', hashed_pw, 'อาจารย์ผู้ดูแลระบบ', 'teacher', 'อนุมัติแล้ว'))

    conn.commit()
    cursor.close()
    conn.close()

init_db()

@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') == 'teacher':
            return redirect(url_for('teacher_dashboard'))
        return redirect(url_for('profile'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()
        if os.environ.get('DATABASE_URL'):
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        else:
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            # ดึงรหัสผ่าน (ตำแหน่ง index ขึ้นอยู่กับประเภท DB แต่ใช้ดึงตามคอลัมน์ได้ถ้าแปลง row)
            stored_password = user[2]
            if check_password_hash(stored_password, password):
                session['user_id'] = user[0]
                session['username'] = user[1]
                session['fullname'] = user[3]
                session['role'] = user[8]
                session['student_id'] = user[4]
                flash('เข้าสู่ระบบสำเร็จ ยินดีต้อนรับครับ!', 'success')
                if user[8] == 'teacher':
                    return redirect(url_for('teacher_dashboard'))
                else:
                    return redirect(url_for('profile'))
        
        flash('ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        student_id = request.form['student_id']
        fullname = request.form['fullname']
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        height = float(request.form.get('height', 0))
        weight = float(request.form.get('weight', 0))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # ตรวจสอบว่าตรงกับรายชื่อที่ครูอนุญาตไว้หรือไม่
        if os.environ.get('DATABASE_URL'):
            cursor.execute("SELECT * FROM allowed_students WHERE student_id = %s AND fullname = %s", (student_id, fullname))
        else:
            cursor.execute("SELECT * FROM allowed_students WHERE student_id = ? AND fullname = ?", (student_id, fullname))
        allowed = cursor.fetchone()
        
        if not allowed:
            cursor.close()
            conn.close()
            flash('ไม่พบรหัสนักเรียนหรือชื่อ-นามสกุลนี้ในรายชื่อที่ได้รับอนุมัติจากทางโรงเรียน กรุณาติดต่อคุณครู', 'danger')
            return redirect(url_for('register'))
        
        major = allowed[3] # ดึงห้อง/แผนกจากตาราง allowed

        file = request.files.get('profile_image')
        filename = 'default.png'
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        try:
            if os.environ.get('DATABASE_URL'):
                cursor.execute('''
                    INSERT INTO users (username, password, fullname, student_id, major, height, weight, role, status, profile_image)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'student', 'รอตรวจสอบ', %s)
                ''', (username, password, fullname, student_id, major, height, weight, filename))
            else:
                cursor.execute('''
                    INSERT INTO users (username, password, fullname, student_id, major, height, weight, role, status, profile_image)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'student', 'รอตรวจสอบ', ?)
                ''', (username, password, fullname, student_id, major, height, weight, filename))
            
            conn.commit()
            cursor.close()
            conn.close()
            flash('ลงทะเบียนสำเร็จ! สามารถเข้าสู่ระบบเพื่อรอคุณครูอนุมัติข้อมูลได้เลย', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            cursor.close()
            conn.close()
            flash('ชื่อผู้ใช้นี้ (Username) หรือรหัสนักเรียนนี้ถูกใช้งานในระบบแล้ว', 'danger')

    return render_template('register.html')

@app.route('/profile')
def profile():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    if os.environ.get('DATABASE_URL'):
        cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
    else:
        cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user = cursor.fetchone()
    
    # ดึงประวัติสุขภาพย้อนหลังเพื่อทำกราฟ
    if os.environ.get('DATABASE_URL'):
        cursor.execute("SELECT weight, height, bmi, record_date FROM weight_history WHERE student_id = %s ORDER BY record_date ASC", (user[4],))
    else:
        cursor.execute("SELECT weight, height, bmi, record_date FROM weight_history WHERE student_id = ? ORDER BY record_date ASC", (user[4],))
    history = cursor.fetchall()
    
    cursor.close()
    conn.close()

    # คำนวณ BMI ปัจจุบัน
    bmi = 0
    bmi_status = "ปกติ"
    if user[6] and user[7] and user[6] > 0:
        h_m = user[6] / 100
        bmi = round(user[7] / (h_m * h_m), 2)
        if bmi < 18.5:
            bmi_status = "น้ำหนักน้อย / ผอม"
        elif 18.5 <= bmi <= 22.9:
            bmi_status = "ปกติ (สมส่วน)"
        elif 23.0 <= bmi <= 24.9:
            bmi_status = "ท้วม / เริ่มอ้วน"
        else:
            bmi_status = "อ้วน"

    return render_template('student_profile.html', user=user, bmi=bmi, bmi_status=bmi_status, history=history)

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        height = float(request.form['height'])
        weight = float(request.form['weight'])
        
        # คำนวณ BMI บันทึกประวัติ
        h_m = height / 100
        bmi = round(weight / (h_m * h_m), 2)
        
        file = request.files.get('profile_image')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            if os.environ.get('DATABASE_URL'):
                cursor.execute('UPDATE users SET height = %s, weight = %s, profile_image = %s, status = %s WHERE id = %s',
                               (height, weight, filename, 'รอตรวจสอบ', session['user_id']))
            else:
                cursor.execute('UPDATE users SET height = ?, weight = ?, profile_image = ?, status = ? WHERE id = ?',
                               (height, weight, filename, 'รอตรวจสอบ', session['user_id']))
        else:
            if os.environ.get('DATABASE_URL'):
                cursor.execute('UPDATE users SET height = %s, weight = %s, status = %s WHERE id = %s',
                               (height, weight, 'รอตรวจสอบ', session['user_id']))
            else:
                cursor.execute('UPDATE users SET height = ?, weight = ?, status = ? WHERE id = ?',
                               (height, weight, 'รอตรวจสอบ', session['user_id']))
        
        # บันทึกประวัติน้ำหนักส่วนสูงลงตาราง history
        student_id = session.get('student_id')
        if os.environ.get('DATABASE_URL'):
            cursor.execute('INSERT INTO weight_history (student_id, weight, height, bmi) VALUES (%s, %s, %s, %s)',
                           (student_id, weight, height, bmi))
        else:
            cursor.execute('INSERT INTO weight_history (student_id, weight, height, bmi, record_date) VALUES (?, ?, ?, ?, datetime("now", "+7 hours"))',
                           (student_id, weight, height, bmi))

        conn.commit()
        cursor.close()
        conn.close()
        flash('อัปเดตข้อมูลและน้ำหนักส่วนสูงเรียบร้อย! สถานะเปลี่ยนเป็นรอครูตรวจสอบ', 'success')
        return redirect(url_for('profile'))

    if os.environ.get('DATABASE_URL'):
        cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
    else:
        cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('edit_profile.html', user=user)

@app.route('/card')
def student_card():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    if os.environ.get('DATABASE_URL'):
        cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
    else:
        cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template('student_card.html', user=user)

@app.route('/news')
def news():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM announcements ORDER BY id DESC")
    announcements = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('news.html', announcements=announcements)

@app.route('/verify/<student_id>')
def verify(student_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    if os.environ.get('DATABASE_URL'):
        cursor.execute("SELECT * FROM users WHERE student_id = %s", (student_id,))
    else:
        cursor.execute("SELECT * FROM users WHERE student_id = ?", (student_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user:
        return render_template('verify.html', user=None)

    return render_template('verify.html', user=user)

@app.route('/teacher', methods=['GET', 'POST'])
def teacher_dashboard():
    if 'user_id' not in session or session.get('role') != 'teacher':
        flash('สำหรับคุณครูผู้ดูแลระบบเท่านั้น', 'danger')
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        if 'add_announcement' in request.form:
            title = request.form['title']
            content = request.form['content']
            if os.environ.get('DATABASE_URL'):
                cursor.execute("INSERT INTO announcements (title, content) VALUES (%s, %s)", (title, content))
            else:
                cursor.execute("INSERT INTO announcements (title, content, date) VALUES (?, ?, datetime('now', '+7 hours'))", (title, content))
            conn.commit()
            flash('เพิ่มประกาศข่าวสารสำเร็จ', 'success')

        elif 'add_allowed_student' in request.form:
            student_id = request.form['student_id']
            fullname = request.form['fullname']
            major = request.form['major']
            try:
                if os.environ.get('DATABASE_URL'):
                    cursor.execute("INSERT INTO allowed_students (student_id, fullname, major) VALUES (%s, %s, %s)", (student_id, fullname, major))
                else:
                    cursor.execute("INSERT INTO allowed_students (student_id, fullname, major) VALUES (?, ?, ?)", (student_id, fullname, major))
                conn.commit()
                flash('เพิ่มรายชื่อนักเรียนล่วงหน้าสำเร็จ', 'success')
            except:
                flash('รหัสนักเรียนนี้มีในระบบที่อนุญาตแล้ว', 'danger')

        elif 'update_status' in request.form:
            user_id = request.form['user_id']
            new_status = request.form['status']
            if os.environ.get('DATABASE_URL'):
                cursor.execute("UPDATE users SET status = %s WHERE id = %s", (new_status, user_id))
            else:
                cursor.execute("UPDATE users SET status = ? WHERE id = ?", (new_status, user_id))
            conn.commit()
            flash('อัปเดตสถานะข้อมูลนักเรียนเรียบร้อย', 'success')

    # ดึงข้อมูลนักเรียนทั้งหมดและรายชื่อที่อนุญาต
    cursor.execute("SELECT * FROM users WHERE role = 'student'")
    students = cursor.fetchall()
    cursor.execute("SELECT * FROM allowed_students")
    allowed_list = cursor.fetchall()
    
    # สถิติจำนวน
    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'student'")
    total_students = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'student' AND status = 'อนุมัติแล้ว'")
    approved_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'student' AND status = 'รอตรวจสอบ'")
    pending_count = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    return render_template('teacher_dashboard.html', 
                           students=students, 
                           allowed_list=allowed_list,
                           total_students=total_students,
                           approved_count=approved_count,
                           pending_count=pending_count)

@app.route('/logout')
def logout():
    session.clear()
    flash('ออกจากระบบเรียบร้อย', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
