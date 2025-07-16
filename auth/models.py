import os
import pyodbc
from dotenv import load_dotenv
from flask_login import UserMixin

# Load environment variables from .env
load_dotenv()

# Your Azure SQL connection string from .env
SQL_CONN_STR = os.getenv("AZURE_SQL_CONN_STR")

class User(UserMixin):
    """
    User model for authentication. Implements Flask-Login's UserMixin and
    provides methods to look up users in the database.
    """
    def __init__(self, user_id, username, password_hash, email):
        self.id = user_id
        self.username = username
        self.password_hash = password_hash
        self.email = email

    @staticmethod
    def get_by_id(user_id):
        """
        Fetch a user by their unique ID.
        """
        conn = pyodbc.connect(SQL_CONN_STR)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, username, password_hash, email"
            " FROM Users WHERE user_id = ?", user_id
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return User(*row)
        return None

    @staticmethod
    def get_by_username(username):
        """
        Fetch a user by their username.
        """
        conn = pyodbc.connect(SQL_CONN_STR)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, username, password_hash, email"
            " FROM Users WHERE username = ?", username
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return User(*row)
        return None
