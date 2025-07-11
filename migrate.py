import os
from dotenv import load_dotenv, find_dotenv
import pyodbc

# ——— Load environment variables —————————————————————————————————————
env_path = find_dotenv()
load_dotenv(env_path)

# ——— Grab the same connection string your app uses ————————————————————
conn_str = os.getenv("AZURE_SQL_CONN_STR")
if not conn_str:
    raise RuntimeError("❌ Missing AZURE_SQL_CONN_STR in .env")

# ——— DDL statements to ensure tables exist —————————————————————————
ddl_statements = [
    # Create Users table
    """
    IF NOT EXISTS (
      SELECT * FROM sys.tables WHERE name = 'Users'
    )
    CREATE TABLE Users (
      user_id INT IDENTITY(1,1) PRIMARY KEY,
      username NVARCHAR(50) NOT NULL UNIQUE,
      password_hash NVARCHAR(255) NOT NULL,
      email NVARCHAR(100) NOT NULL UNIQUE,
      created_at DATETIME2 DEFAULT SYSUTCDATETIME()
    );
    """,

    # Create Files table
    """
    IF NOT EXISTS (
      SELECT * FROM sys.tables WHERE name = 'Files'
    )
    CREATE TABLE Files (
      file_id      INT IDENTITY(1,1) PRIMARY KEY,
      user_id      INT NOT NULL REFERENCES Users(user_id),
      file_name    NVARCHAR(255) NOT NULL,
      blob_url     NVARCHAR(500) NOT NULL,
      encryption_iv VARBINARY(16),
      uploaded_at  DATETIME2 DEFAULT SYSUTCDATETIME()
    );
    """
]

def run_migration():
    try:
        with pyodbc.connect(conn_str) as conn:
            cursor = conn.cursor()
            for stmt in ddl_statements:
                cursor.execute(stmt)
            conn.commit()
        print("🎉 Migration succeeded: tables are ready!")
    except Exception as e:
        print("⚠️ Migration failed:", e)

if __name__ == "__main__":
    run_migration()
