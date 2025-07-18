import os
from datetime import datetime

from email_validator import validate_email, EmailNotValidError
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
from flask_cors import CORS, cross_origin

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
        cursor.execute(
            """
            INSERT INTO Files
              (user_id, file_name, blob_url, encryption_iv, uploaded_at)
            VALUES (?, ?, ?, NULL, ?)
            """,
            user_id, filename, blob_name, datetime.utcnow()
        )
        conn.commit()

# ─── AUTHENTICATION ROUTES ───────────────────────────────────────────────────

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        uname     = request.form.get('username', '').strip()
        raw_email = request.form.get('email', '').strip()
        pw        = request.form.get('password', '')

        # 1) Validate email
        try:
            v = validate_email(raw_email, check_deliverability=True)
            email = v.email
        except EmailNotValidError as e:
            flash(f"Invalid email address: {e}", "warning")
            return redirect(url_for('signup'))

        # 2) Unique username
        if User.get_by_username(uname):
            flash("Username taken, pick another.", "warning")
            return redirect(url_for('signup'))

        # 3) Hash & insert
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
        return redirect(url_for('index'))

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You’ve been logged out.", "info")
    return redirect(url_for('login'))


# ─── DASHBOARD (INDEX) w/ inline profile edit ────────────────────────────────

@app.route('/', methods=['GET','POST'])
@login_required
def index():
    # Handle inline “Save Changes” form submission
    if request.method == 'POST':
        new_username = request.form.get('username','').strip()
        new_password = request.form.get('password','')

        updates = []
        params  = []

        # Username change?
        if new_username and new_username != current_user.username:
            if User.get_by_username(new_username):
                flash("Username already taken.", "warning")
                return redirect(url_for('index'))
            updates.append("username = ?")
            params.append(new_username)

        # Password change?
        if new_password:
            pw_hash = bcrypt.hash(new_password)
            updates.append("password_hash = ?")
            params.append(pw_hash)

        if updates:
            params.append(current_user.id)
            stmt = f"UPDATE Users SET {', '.join(updates)} WHERE user_id = ?"
            with pyodbc.connect(SQL_CONN_STR) as conn:
                cur = conn.cursor()
                cur.execute(stmt, *params)
                conn.commit()
            flash("Profile updated!", "success")
            if new_username:
                current_user.username = new_username
        else:
            flash("No changes made.", "info")

        return redirect(url_for('index'))

    # GET: fetch user's files
    with pyodbc.connect(SQL_CONN_STR) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT
              file_id       AS id,
              file_name     AS original_name,
              blob_url      AS blob_name,
              uploaded_at
            FROM Files
            WHERE user_id = ?
            ORDER BY uploaded_at DESC
        """, current_user.id)
        rows = cur.fetchall()

    files = [
        {'id': r[0], 'original_name': r[1], 'blob_name': r[2], 'uploaded_at': r[3]}
        for r in rows
    ]
    return render_template(
        'index.html',
        files=files,
        current_username=current_user.username
    )


# ─── UPLOAD (GET & POST) ─────────────────────────────────────────────────────

@app.route('/upload', methods=['GET','POST'])
@cross_origin(origins="*")
@login_required
def upload():
    if request.method == 'POST':
        file = request.files.get('file')
        if file and file.filename:
            encrypted = encrypt_file(file.read())
            blob_name = f"{file.filename}.enc"
            container_client.get_blob_client(blob_name).upload_blob(encrypted, overwrite=True)
            insert_metadata(current_user.id, file.filename, blob_name)
        return redirect(url_for('index'))

    return render_template('upload.html')


# ─── DOWNLOAD STREAM ─────────────────────────────────────────────────────────

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
@app.route('/delete/<int:file_id>', methods=['POST'])
@login_required
def delete_file(file_id):
    # 1) Look up the blob name and ownership
    with pyodbc.connect(SQL_CONN_STR) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT blob_url FROM Files WHERE file_id = ? AND user_id = ?",
            file_id, current_user.id
        )
        row = cur.fetchone()
        if not row:
            flash("File not found or unauthorized.", "danger")
            return redirect(url_for('index'))
        blob_name = row[0]

        # 2) Delete metadata
        cur.execute(
            "DELETE FROM Files WHERE file_id = ?",
            file_id
        )
        conn.commit()

    # 3) Delete from Azure Blob
    try:
        container_client.get_blob_client(blob_name).delete_blob()
    except Exception as e:
        # if blob was missing, we’ve already removed DB entry
        flash(f"Metadata removed but blob delete failed: {e}", "warning")
    else:
        flash("File deleted successfully.", "success")

    return redirect(url_for('index'))



if __name__ == '__main__':
    app.run(debug=True)
