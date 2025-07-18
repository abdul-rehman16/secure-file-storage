# auth/routes.py
import os
from datetime import datetime
from flask import (
    Blueprint, render_template, redirect,
    url_for, request, flash, current_app
)
from flask_login import (
    login_user, login_required,
    logout_user, current_user
)
from passlib.hash import bcrypt
import pyodbc
from azure.storage.blob import BlobServiceClient

from auth.models import User
from encryption.crypto_utils import encrypt_file, decrypt_file

bp = Blueprint('auth', __name__, template_folder='../templates')

def get_db_conn():
    return pyodbc.connect(current_app.config['AZURE_SQL_CONN_STR'])

def get_blob_container():
    blob_service = BlobServiceClient.from_connection_string(
        current_app.config['AZURE_STORAGE_CONNECTION_STRING']
    )
    return blob_service.get_container_client(
        current_app.config['AZURE_STORAGE_CONTAINER_NAME']
    )

@bp.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        uname = request.form['username']
        pw    = request.form['password']
        email = request.form['email']

        if User.get_by_username(uname):
            flash("Username taken, please pick another.", "warning")
            return redirect(url_for('auth.signup'))

        pw_hash = bcrypt.hash(pw)
        conn = get_db_conn()
        cur  = conn.cursor()
        cur.execute(
            "INSERT INTO Users (username, password_hash, email) VALUES (?,?,?)",
            uname, pw_hash, email
        )
        conn.commit()
        conn.close()

        flash("Signup successful! Please log in.", "success")
        return redirect(url_for('auth.login'))

    return render_template('signup.html')


@bp.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        uname = request.form['username']
        pw    = request.form['password']

        user = User.get_by_username(uname)
        if not user or not bcrypt.verify(pw, user.password_hash):
            flash("Invalid credentials.", "danger")
            return redirect(url_for('auth.login'))

        login_user(user)
        return redirect(url_for('auth.index'))

    return render_template('login.html')


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You’ve been logged out.", "info")
    return redirect(url_for('auth.login'))


@bp.route('/')
@login_required
def index():
    conn = get_db_conn()
    cur  = conn.cursor()
    cur.execute("""
        SELECT file_id, file_name, blob_url, uploaded_at
        FROM Files
        WHERE user_id = ?
        ORDER BY uploaded_at DESC
    """, current_user.id)
    rows = cur.fetchall()
    conn.close()

    files = [
        {
            'id':             r[0],
            'original_name':  r[1],
            'blob_name':      r[2],
            'uploaded_at':    r[3]
        }
        for r in rows
    ]
    return render_template('index.html', files=files)


@bp.route('/upload', methods=['POST'])
@login_required
def upload():
    file = request.files.get('file')
    if not file or not file.filename:
        return redirect(url_for('auth.index'))

    # encrypt + upload blob
    enc_data  = encrypt_file(file.read())
    blob_name = f"{file.filename}.enc"
    blob_cli  = get_blob_container().get_blob_client(blob_name)
    blob_cli.upload_blob(enc_data, overwrite=True)

    # record metadata
    conn = get_db_conn()
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO Files
          (user_id, file_name, blob_url, encryption_iv, uploaded_at)
        VALUES (?, ?, ?, NULL, ?)
    """, current_user.id, file.filename, blob_name, datetime.utcnow())
    conn.commit()
    conn.close()

    return redirect(url_for('auth.index'))


@bp.route('/download/<blob_name>')
@login_required
def download(blob_name):
    blob_cli = get_blob_container().get_blob_client(blob_name)
    encrypted = blob_cli.download_blob().readall()
    data      = decrypt_file(encrypted)

    return (
        data, 200,
        {
            'Content-Type': 'application/octet-stream',
            'Content-Disposition': f'attachment; filename="{blob_name[:-4]}"'
        }
    )