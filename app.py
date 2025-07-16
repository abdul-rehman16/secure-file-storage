import os
from datetime import datetime

from flask import (
    Flask, render_template, request,
    redirect, url_for, flash
)
from flask_login import (
    LoginManager, login_user, login_required,
    logout_user, current_user
)
from passlib.hash import bcrypt
from dotenv import load_dotenv
import pyodbc
from azure.storage.blob import BlobServiceClient

from auth.models import User
from encryption.crypto_utils import encrypt_file, decrypt_file

# ─── Load environment & instantiate app ──────────────────────────────────────
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# ─── Flask-Login setup ───────────────────────────────────────────────────────
login_manager = LoginManager(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(int(user_id))

# ─── Azure + SQL configuration ───────────────────────────────────────────────
SQL_CONN_STR   = os.getenv("AZURE_SQL_CONN_STR")
BLOB_CONN_STR  = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")

blob_service     = BlobServiceClient.from_connection_string(BLOB_CONN_STR)
container_client = blob_service.get_container_client(CONTAINER_NAME)
try:
    container_client.create_container()
except Exception:
    pass  # container already exists

def insert_metadata(user_id, filename, blob_name):
    with pyodbc.connect(SQL_CONN_STR) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Files
              (user_id, file_name, blob_url, encryption_iv, uploaded_at)
            VALUES (?, ?, ?, NULL, ?)
        """, user_id, filename, blob_name, datetime.utcnow())
        conn.commit()

# ─── AUTHENTICATION ROUTES ───────────────────────────────────────────────────

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        uname = request.form['username']
        pw    = request.form['password']
        email = request.form['email']

        if User.get_by_username(uname):
            flash("Username taken, pick another.", "warning")
            return redirect(url_for('signup'))

        pw_hash = bcrypt.hash(pw)
        with pyodbc.connect(SQL_CONN_STR) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO Users (username, password_hash, email) VALUES (?,?,?)",
                uname, pw_hash, email
            )
            conn.commit()

        flash("Signup successful! Please log in.", "success")
        return redirect(url_for('login'))

    return render_template('signup.html')


@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        uname = request.form['username']
        pw    = request.form['password']

        user = User.get_by_username(uname)
        if not user or not bcrypt.verify(pw, user.password_hash):
            flash("Invalid credentials.", "danger")
            return redirect(url_for('login'))

        login_user(user)
        return redirect(url_for('dashboard'))

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You’ve been logged out.", "info")
    return redirect(url_for('login'))


# ─── DASHBOARD / UPLOAD / DOWNLOAD PAGES ─────────────────────────────────────

@app.route('/')
def home():
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    with pyodbc.connect(SQL_CONN_STR) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT file_id AS id,
                   file_name AS original_name,
                   blob_url AS blob_name,
                   uploaded_at
              FROM Files
             WHERE user_id = ?
          ORDER BY uploaded_at DESC
        """, current_user.id)
        rows = cursor.fetchall()

    files = [
        {'id': r[0], 'original_name': r[1], 'blob_name': r[2], 'uploaded_at': r[3]}
        for r in rows
    ]
    return render_template('dashboard.html', files=files)


@app.route('/upload', methods=['GET'])
@login_required
def upload_page():
    return render_template('upload.html')


@app.route('/upload', methods=['POST'])
@login_required
def upload():
    file = request.files.get('file')
    if file and file.filename:
        encrypted = encrypt_file(file.read())
        blob_name = f"{file.filename}.enc"
        container_client.get_blob_client(blob_name).upload_blob(encrypted, overwrite=True)
        insert_metadata(current_user.id, file.filename, blob_name)

    return redirect(url_for('dashboard'))


@app.route('/download_page/<blob_name>')
@login_required
def download_page(blob_name):
    with pyodbc.connect(SQL_CONN_STR) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT file_name, uploaded_at
              FROM Files
             WHERE user_id = ? AND blob_url = ?
        """, current_user.id, blob_name)
        row = cursor.fetchone()

    if not row:
        flash("File not found or you don’t have permission.", "danger")
        return redirect(url_for('dashboard'))

    original_name, uploaded_at = row
    return render_template(
        'download.html',
        blob_name=blob_name,
        original_name=original_name,
        uploaded_at=uploaded_at
    )


@app.route('/download/<blob_name>')
@login_required
def download(blob_name):
    encrypted = container_client.get_blob_client(blob_name).download_blob().readall()
    data      = decrypt_file(encrypted)
    return (
        data, 200,
        {
            'Content-Type': 'application/octet-stream',
            'Content-Disposition': f'attachment; filename="{blob_name[:-4]}"'
        }
    )


# ─── Run the app ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(debug=True)
