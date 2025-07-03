from dotenv import load_dotenv
load_dotenv()  # <-- this must be at the very top before you call os.getenv()

import os
import pyodbc

server = os.getenv("DB_SERVER")
database = os.getenv("DB_DATABASE")
username = os.getenv("DB_USER")
password = os.getenv("DB_PASSWORD")

# Connection string
connection_string = f'''
DRIVER={{ODBC Driver 17 for SQL Server}};
SERVER={server};
DATABASE={database};
UID={username};
PWD={password};
Encrypt=yes;
TrustServerCertificate=no;
Connection Timeout=90;
'''

#  Function to get a connection when needed
def get_connection():
    return pyodbc.connect(connection_string)

#  Optional: quick test if connection works
if __name__ == '__main__':
    try:
        conn = get_connection()
        print("Connection established")
        cursor = conn.cursor()
        cursor.execute("SELECT GETDATE();")
        row = cursor.fetchone()
        print("Current time from SQL Server:", row[0])
        conn.close()
    except Exception as e:
        print("Connection failed:", e)
