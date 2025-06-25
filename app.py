from flask import Flask, render_template, request
import os
from utils.predict import predict_image
from werkzeug.utils import secure_filename
from db import get_connection
from datetime import datetime
import mysql.connector 
from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash
from flask import session, redirect, url_for
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.secret_key =os.getenv('SECRET_KEY', 'default_secret_key')


os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ========================== ROUTES ===========================

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/predict', methods=['POST'])
def predict():
    # Validasi file
    if 'file' not in request.files:
        return 'No file uploaded.', 400

    file = request.files['file']
    if file.filename == '':
        return 'No selected file.', 400

    # Simpan file
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # Prediksi gambar
    predicted_class, accuracy = predict_image(filepath)  # accuracy = float

    accuracy = float(accuracy)

    # Simpan ke database
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Simpan gambar
    cursor.execute("""
        INSERT INTO gambar_citra (id_pengguna, nama_file, sumber_data, tanggal_upload)
        VALUES (%s, %s, %s, %s)
    """, (1, filename, 'user', datetime.now()))
    id_gambar = cursor.lastrowid

    # Cek atau tambah penyakit
    cursor.execute("SELECT id_penyakit FROM penyakit WHERE nama_penyakit = %s", (predicted_class,))
    penyakit_row = cursor.fetchone()

    if penyakit_row:
        id_penyakit = penyakit_row['id_penyakit']
    else:
        cursor.execute("INSERT INTO penyakit (nama_penyakit) VALUES (%s)", (predicted_class,))
        id_penyakit = cursor.lastrowid

    # Simpan hasil diagnosa
    cursor.execute("""
        INSERT INTO hasil_diagnosa (id_gambar, id_penyakit, tanggal_diagnosa, akurasi)
        VALUES (%s, %s, %s, %s)
    """, (id_gambar, id_penyakit, datetime.now(), accuracy))  # SIMPAN FLOAT

    conn.commit()
    conn.close()

    # Tampilkan di halaman HTML
    accuracy_formatted = f"{accuracy:.2f}%"
    return render_template('hasil.html',
                           image_path=filepath,
                           prediction=predicted_class,
                           accuracy=accuracy_formatted)


app.secret_key = 'neuroskin_secret_key' 

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM pengguna WHERE email = %s", (email,))
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id_pengguna']
            session['user_role'] = user['role']
            session['user_name'] = user['nama']

            # arahkan sesuai role
            if user['role'] == 'admin':
                return redirect('/admin_dashboard')
            else:
                return redirect('/dashboard')

        return render_template('login.html', error='Email atau password salah!')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()  
    return redirect('/login') 

@app.route('/detail/<int:id_diagnosa>')
def detail_diagnosa(id_diagnosa):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT hd.tanggal_diagnosa, p.nama_penyakit, hd.akurasi, gc.nama_file
        FROM hasil_diagnosa hd
        JOIN penyakit p ON hd.id_penyakit = p.id_penyakit
        JOIN gambar_citra gc ON hd.id_gambar = gc.id_gambar
        WHERE hd.id_diagnosa = %s AND gc.id_pengguna = %s
    """, (id_diagnosa, session['user_id']))

    detail = cursor.fetchone()
    cursor.close()
    conn.close()

    if not detail:
        return "Data tidak ditemukan", 404

    return render_template('detail_diagnosa.html', detail=detail)

@app.route('/admin_dashboard')
def admin_dashboard():
    if session.get('user_role') != 'admin':
        return redirect('/login')

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM pengguna")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT id_penyakit) FROM dataset")
    label_terpakai = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM dataset")
    total_dataset = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    return render_template('admin_dashboard.html',
                           user_name=session.get('user_name'),
                           total_users=total_users,
                           label_terpakai=label_terpakai,
                           total_dataset=total_dataset)


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Hitung total diagnosa user
    cursor.execute("""
        SELECT COUNT(*) AS total FROM hasil_diagnosa hd
        JOIN gambar_citra gc ON hd.id_gambar = gc.id_gambar
        WHERE gc.id_pengguna = %s
    """, (user_id,))
    total_result = cursor.fetchone()['total']

    # Cari akurasi tertinggi
    cursor.execute("""
        SELECT MAX(hd.akurasi) AS max_akurasi FROM hasil_diagnosa hd
        JOIN gambar_citra gc ON hd.id_gambar = gc.id_gambar
        WHERE gc.id_pengguna = %s
    """, (user_id,))
    max_akurasi = cursor.fetchone()['max_akurasi'] or 0

    conn.close()

    return render_template('dashboard.html',
                           user_name=session.get('user_name', 'User'),
                           total_diagnosa=total_result,
                           akurasi_tertinggi=max_akurasi)


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':
        file = request.files['file']
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # Proses prediksi real
            prediction, accuracy = predict_image(filepath)
            accuracy = float(accuracy)

            # Simpan ke database
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)

            # 1. Simpan gambar
            cursor.execute("""
                INSERT INTO gambar_citra (id_pengguna, nama_file, sumber_data, tanggal_upload)
                VALUES (%s, %s, %s, %s)
            """, (session['user_id'], filename, 'user', datetime.now()))
            id_gambar = cursor.lastrowid

            # 2. Cek penyakit
            cursor.execute("SELECT id_penyakit FROM penyakit WHERE nama_penyakit = %s", (prediction,))
            row = cursor.fetchone()

            if row:
                id_penyakit = row['id_penyakit']
            else:
                cursor.execute("INSERT INTO penyakit (nama_penyakit) VALUES (%s)", (prediction,))
                id_penyakit = cursor.lastrowid

            # 3. Simpan hasil diagnosa
            cursor.execute("""
                INSERT INTO hasil_diagnosa (id_gambar, id_penyakit, tanggal_diagnosa, akurasi)
                VALUES (%s, %s, %s, %s)
            """, (id_gambar, id_penyakit, datetime.now(), accuracy))

            conn.commit()
            conn.close()

            # Simpan ke session (biar bisa ditampilkan di /hasil)
            session['prediction'] = prediction
            session['accuracy'] = f"{accuracy:.2f}%"
            session['image_path'] = f'/static/uploads/{filename}'

            return redirect('/hasil')

    return render_template('upload.html')


@app.route('/hasil')
def hasil():
    if 'user_id' not in session:
        return redirect('/hasil.html')

    prediction = session.get('prediction')
    accuracy = session.get('accuracy')
    image_path = session.get('image_path')

    if not prediction or not accuracy or not image_path:
        # Kalau belum melakukan diagnosa, tampilkan halaman akses terbatas
        return render_template('akses_terbatas.html')

    return render_template(
        'hasil.html',
        user_name=session.get('user_name', 'User'),
        prediction=prediction,
        accuracy=accuracy,
        image_path=image_path
    )

@app.route('/riwayat')
def riwayat():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
    SELECT hd.id_diagnosa, hd.tanggal_diagnosa, p.nama_penyakit, hd.akurasi, gc.nama_file
    FROM hasil_diagnosa hd
    JOIN penyakit p ON hd.id_penyakit = p.id_penyakit
    JOIN gambar_citra gc ON hd.id_gambar = gc.id_gambar
    WHERE gc.id_pengguna = %s
    ORDER BY hd.tanggal_diagnosa DESC
""", (session['user_id'],))


    data = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("riwayat.html", data=data)
   
@app.route('/user_management')
def user_management():
    if session.get('user_role') != 'admin':
        return redirect('/login')  # hanya admin yang boleh akses

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id_pengguna, nama, email, role FROM pengguna")
    users = cursor.fetchall()
    conn.close()

    return render_template('user_management.html', users=users, user_name=session.get('user_name', 'Admin'))



@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if session.get('user_role') != 'admin':
        return redirect('/login')

    if request.method == 'POST':
        nama = request.form['nama']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        role = request.form['role']

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO pengguna (nama, email, password, role) VALUES (%s, %s, %s, %s)",
                       (nama, email, password, role))
        conn.commit()
        conn.close()

        return redirect('/user_management')

    return render_template('add_user.html')

@app.route('/edit_user/<int:id>', methods=['GET', 'POST'])
def edit_user(id):
    if session.get('user_role') != 'admin':
        return redirect('/login')

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        nama = request.form['nama']
        email = request.form['email']
        role = request.form['role']

        cursor.execute("""
            UPDATE pengguna SET nama=%s, email=%s, role=%s WHERE id_pengguna=%s
        """, (nama, email, role, id))
        conn.commit()

        cursor.execute("SELECT * FROM pengguna WHERE id_pengguna = %s", (id,))
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        return render_template('edit_user.html', user=user, success=True)

    # GET method
    cursor.execute("SELECT * FROM pengguna WHERE id_pengguna = %s", (id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template('edit_user.html', user=user)

@app.route('/hapus_user/<int:id>')
def delete_user(id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pengguna WHERE id_pengguna = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect('/user_management')


@app.route('/input_dataset', methods=['GET', 'POST'])
def input_dataset():
    if session.get('user_role') != 'admin':
        return redirect('/login')
    
    if request.method == 'POST':
        file = request.files['image']
        label = request.form['label'].strip().lower()
        source = request.form['source']

        if not file or not label or not source:
            return "Lengkapi semua data!"

        filename = secure_filename(file.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(path)

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # Cek apakah label penyakit sudah ada
        cursor.execute("SELECT id_penyakit FROM penyakit WHERE nama_penyakit = %s", (label,))
        result = cursor.fetchone()

        if result:
            id_penyakit = result['id_penyakit']
        else:
            # Kalau belum ada, tambahkan ke tabel penyakit
            cursor.execute("INSERT INTO penyakit (nama_penyakit) VALUES (%s)", (label,))
            id_penyakit = cursor.lastrowid

        # Simpan ke tabel dataset
        cursor.execute("""
            INSERT INTO dataset (nama_file, id_penyakit, sumber_data, tanggal_masuk)
            VALUES (%s, %s, %s, NOW())
        """, (filename, id_penyakit, source))
        
        conn.commit()
        conn.close()

        return redirect('/admin_dashboard')

    return render_template('input_dataset.html')

@app.route('/edit_profil_admin', methods=['GET', 'POST'])
def edit_profil_admin():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        nama = request.form['nama']
        email = request.form['email']
        password_baru = request.form['password_baru']
        konfirmasi = request.form['konfirmasi']

        if password_baru and password_baru != konfirmasi:
            return "Password dan konfirmasi tidak cocok!"

        if password_baru:
            hashed = generate_password_hash(password_baru)
            cursor.execute("""
                UPDATE pengguna SET nama=%s, email=%s, password=%s
                WHERE id_pengguna=%s
            """, (nama, email, hashed, user_id))
        else:
            cursor.execute("""
                UPDATE pengguna SET nama=%s, email=%s
                WHERE id_pengguna=%s
            """, (nama, email, user_id))

        conn.commit()
        cursor.close()
        conn.close()
        session['user_name'] = nama

        # ✅ render ulang halaman dengan pesan sukses
        return render_template('edit_profil_admin.html', user={'nama': nama, 'email': email}, success=True)

    cursor.execute("SELECT nama, email FROM pengguna WHERE id_pengguna = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template('edit_profil_admin.html', user=user, success=False) 

if __name__ == '__main__':
    app.run(debug=False)
