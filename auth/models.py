import os
import pyodbc
from flask_login import UserMixin

SQL_CONN_STR = os.getenv("AZURE_SQL_CONN_STR")

class User(UserMixin):
    def __init__(self, user_id, username, password_hash, email):
        self.id            = user_id
        self.username      = username
        self.password_hash = password_hash
        self.email         = email

    @staticmethod
    def get_by_id(uid):
        conn   = pyodbc.connect(SQL_CONN_STR)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, username, password_hash, email "
            "FROM Users WHERE user_id = ?",
            uid
        )
        row = cursor.fetchone()
        conn.close()
        return User(*row) if row else None

    @staticmethod
    def get_by_username(uname):
        conn   = pyodbc.connect(SQL_CONN_STR)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, username, password_hash, email "
            "FROM Users WHERE username = ?",
            uname
        )
        row = cursor.fetchone()
        conn.close()
        return User(*row) if row else None
