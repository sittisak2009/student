import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3

app = Flask(__name__)
app.secret_key = 'school_system_secure_key_2026'

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # ตารางผู้ใช้งาน (ทั้งนักเรียนและครู)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE,
            fullname TEXT NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            weight REAL DEFAULT 0,
            height REAL DEFAULT 0,
            phone TEXT DEFAULT '',
            profile_image TEXT DEFAULT 'default.png',
            status TEXT DEFAULT 'รอตรวจสอบข้อมูล'
        )
    ''')
    # ตารางประกาศข่าวสาร
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            date TEXT NOT NULL
        )
    ''')
    
    # สร้างบัญชีคุณครูเริ่มต้น (รหัสครู: teacher123 / รหัสผ่าน: 1234)
    cursor.execute("SELECT * FROM users WHERE role = 'teacher'")
    if not cursor.fetchone():
        hashed_pw = generate_password_hash('1234')
        cursor.execute("INSERT INTO users (student_id, fullname, password, role, status) VALUES (?, ?, ?, ?, ?)",
                       ('teacher123', 'อาจารย์ผู้ดูแลระบบ', hashed_pw, 'teacher', 'อนุมัติแล้ว'))
    
    conn.commit()
    cursor.close()
    conn.close()

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE,
            password TEXT,
            fullname TEXT,
            role TEXT,
            status TEXT
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
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            date TEXT,
            status TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE,
            score INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute("SELECT * FROM users WHERE role = 'teacher'")
    if not cursor.fetchone():
        hashed_pw = generate_password_hash('1234')
        cursor.execute('''
            INSERT INTO users (student_id, password, fullname, role, status)
            VALUES (?, ?, ?, ?, ?)
        ''', ('teacher123', hashed_pw, 'อาจารย์ผู้ดูแลระบบ', 'teacher', 'อนุมัติแล้ว'))
        
    conn.commit()
    cursor.close()
    conn.close()
    
init_db()

# หน้าแรก: เลือกระบบนักเรียน หรือ ครู
@app.route('/')
def index():
    return render_template('index.html')

# --- ฝั่งนักเรียน ---
@app.route('/student/register', methods=['GET', 'POST'])
def student_register():
    if request.method == 'POST':
        student_id = request.form['student_id']
        fullname = request.form['fullname']
        password = generate_password_hash(request.form['password'])

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO users (student_id, fullname, password, role, status)
                VALUES (?, ?, ?, 'student', 'รอตรวจสอบข้อมูล')
            ''', (student_id, fullname, password))
            conn.commit()
            cursor.close()
            conn.close()
            flash('ลงทะเบียนสำเร็จ! กรุณาเข้าสู่ระบบ', 'success')
            return redirect(url_for('student_login'))
        except:
            cursor.close()
            conn.close()
            flash('รหัสนักเรียนนี้ถูกใช้งานในระบบแล้ว', 'danger')

    return render_template('student_register.html')

@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        student_id = request.form['student_id']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE student_id = ? AND role = 'student'", (student_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['student_id'] = user['student_id']
            session['fullname'] = user['fullname']
            session['role'] = 'student'
            return redirect(url_for('student_dashboard'))
        
        flash('รหัสนักเรียนหรือรหัสผ่านไม่ถูกต้อง', 'danger')
    return render_template('student_login.html')

@app.route('/student/dashboard', methods=['GET', 'POST'])
def student_dashboard():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('student_login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        weight = float(request.form['weight'])
        height = float(request.form['height'])
        phone = request.form['phone']
        
        file = request.files.get('profile_image')
        filename = request.form.get('old_image', 'default.png')
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        cursor.execute('''
            UPDATE users SET weight = ?, height = ?, phone = ?, profile_image = ?, status = 'รอตรวจสอบข้อมูล'
            WHERE id = ?
        ''', (weight, height, phone, filename, session['user_id']))
        conn.commit()
        flash('บันทึกข้อมูลเรียบร้อย! รอคุณครูตรวจสอบ', 'success')

    cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user = cursor.fetchone()
    
    # ดึงประกาศข่าวสารมาแสดงให้นักเรียนเห็น
    cursor.execute("SELECT * FROM announcements ORDER BY id DESC")
    announcements = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('student_dashboard.html', user=user, announcements=announcements)

@app.route('/student/card')
def student_card():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('student_login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('student_card.html', user=user)

# --- หน้าสแกนตรวจสอบบัตรนักเรียน (สาธารณะ) ---
@app.route('/verify/<student_id>')
def verify_student(student_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE student_id = ? AND role = 'student'", (student_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('verify.html', user=user)

# --- ฝั่งคุณครู ---
@app.route('/teacher/login', methods=['GET', 'POST'])
def teacher_login():
    if request.method == 'POST':
        teacher_id = request.form['teacher_id']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE student_id = ? AND role = 'teacher'", (teacher_id,))
        teacher = cursor.fetchone()
        cursor.close()
        conn.close()

        if teacher and check_password_hash(teacher['password'], password):
            session['user_id'] = teacher['id']
            session['fullname'] = teacher['fullname']
            session['role'] = 'teacher'
            return redirect(url_for('teacher_dashboard'))
        
        flash('รหัสประจำตัวครูหรือรหัสผ่านไม่ถูกต้อง', 'danger')
    return render_template('teacher_login.html')

@app.route('/teacher/dashboard', methods=['GET', 'POST'])
def teacher_dashboard():
    if 'user_id' not in session or session.get('role') != 'teacher':
        return redirect(url_for('teacher_login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        if 'update_status' in request.form:
            user_id = request.form['user_id']
            new_status = request.form['status']
            cursor.execute("UPDATE users SET status = ? WHERE id = ?", (new_status, user_id))
            conn.commit()
            flash('อัปเดตสถานะนักเรียนเรียบร้อย', 'success')
        elif 'add_announcement' in request.form:
            title = request.form['title']
            content = request.form['content']
            cursor.execute("INSERT INTO announcements (title, content, date) VALUES (?, ?, datetime('now', '+7 hours'))", (title, content))
            conn.commit()
            flash('โพสต์ประกาศข่าวสารสำเร็จ', 'success')

    cursor.execute("SELECT * FROM users WHERE role = 'student'")
    students = cursor.fetchall()
    
    cursor.execute("SELECT * FROM announcements ORDER BY id DESC")
    announcements = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('teacher_dashboard.html', students=students, announcements=announcements)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/teacher/delete_student/<int:user_id>', methods=['POST'])
def delete_student(user_id):
    if 'user_id' not in session or session.get('role') != 'teacher':
        return redirect(url_for('teacher_login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ? AND role = 'student'", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()
    
    flash('ลบบัญชีนักเรียนออกจากระบบเรียบร้อยแล้ว', 'success')
    return redirect(url_for('teacher_dashboard'))
# --- ระบบเช็คชื่อและสะสมแต้ม ---
@app.route('/teacher/attendance', methods=['GET', 'POST'])
def teacher_attendance():
    if 'user_id' not in session or session.get('role') != 'teacher':
        return redirect(url_for('teacher_login'))
    
    conn = get_db_connection()
    if request.method == 'POST':
        date = request.form['date']
        # บันทึกสถานะเช็คชื่อของนักเรียนแต่ละคน
        for key, value in request.form.items():
            if key.startswith('status_'):
                s_id = key.split('_')[1]
                # ลบของเก่าวันนั้นก่อนกันซ้ำ
                conn.execute("DELETE FROM attendance WHERE student_id = ? AND date = ?", (s_id, date))
                conn.execute("INSERT INTO attendance (student_id, date, status) VALUES (?, ?, ?)", (s_id, date, value))
        conn.commit()
        flash('บันทึกผลการเช็คชื่อเรียบร้อยแล้ว', 'success')
        return redirect(url_for('teacher_attendance'))
        
    students = conn.execute("SELECT * FROM users WHERE role = 'student'").fetchall()
    conn.close()
    return render_template('teacher_attendance.html', students=students)

@app.route('/teacher/points', methods=['GET', 'POST'])
def teacher_points():
    if 'user_id' not in session or session.get('role') != 'teacher':
        return redirect(url_for('teacher_login'))
        
    conn = get_db_connection()
    if request.method == 'POST':
        student_id = request.form['student_id']
        add_score = int(request.form['score'])
        
        # เช็คว่ามีแต้มเดิมยัง
        p = conn.execute("SELECT * FROM points WHERE student_id = ?", (student_id,)).fetchone()
        if p:
            new_score = p['score'] + add_score
            conn.execute("UPDATE points SET score = ? WHERE student_id = ?", (new_score, student_id))
        else:
            conn.execute("INSERT INTO points (student_id, score) VALUES (?, ?)", (student_id, add_score))
        conn.commit()
        flash('อัปเดตแต้มสะสมเรียบร้อย', 'success')
        return redirect(url_for('teacher_points'))
        
    students = conn.execute("SELECT u.*, COALESCE(p.score, 0) as score FROM users u LEFT JOIN points p ON u.student_id = p.student_id WHERE u.role = 'student'").fetchall()
    conn.close()
    return render_template('teacher_points.html', students=students)
    
if __name__ == '__main__':
    app.run(debug=True)
    
