import os
from dotenv import load_dotenv, find_dotenv
import pyodbc

# ——— DEBUG & ENV LOADING ———
print("📂 Current working directory:", os.getcwd())
env_path = find_dotenv()
print("🔍 .env found at:", env_path)
load_dotenv(env_path)

# ——— BUILD CONNECTION STRING ———
server   = os.getenv("DB_SERVER")
database = os.getenv("DB_DATABASE")
user     = os.getenv("DB_USER")
pwd      = os.getenv("DB_PASSWORD")

missing = [name for name,val in [
    ("DB_SERVER", server),
    ("DB_DATABASE", database),
    ("DB_USER", user),
    ("DB_PASSWORD", pwd),
] if not val]
if missing:
    raise RuntimeError(f"❌ Missing env vars: {', '.join(missing)}")

conn_str = (
    "Driver={ODBC Driver 17 for SQL Server};"
    f"Server=tcp:{server},1433;"
    f"Database={database};"
    f"Uid={user}@{server};"
    f"Pwd={pwd};"
    "Encrypt=yes;"
    "TrustServerCertificate=no;"
    "Connection Timeout=30;"
)
masked = conn_str.replace(pwd, "****")
print("🔍 conn_str:", masked)
print("   type:", type(conn_str))


# ——— T-SQL DDL STATEMENTS ———
# Each statement checks for existence via sys.tables then creates
ddl_statements = [
    """
    IF NOT EXISTS (
      SELECT 1
      FROM sys.tables
      WHERE name = 'Users'
    )
    BEGIN
      CREATE TABLE Users (
        user_id INT IDENTITY(1,1) PRIMARY KEY,
        username NVARCHAR(50) NOT NULL UNIQUE,
        password_hash NVARCHAR(255) NOT NULL,
        email NVARCHAR(100) UNIQUE NOT NULL,
        created_at DATETIME2 DEFAULT SYSUTCDATETIME()
      );
    END
    """,
    """
    IF NOT EXISTS (
      SELECT 1
      FROM sys.tables
      WHERE name = 'Files'
    )
    BEGIN
      CREATE TABLE Files (
        file_id INT IDENTITY(1,1) PRIMARY KEY,
        user_id INT NOT NULL
          CONSTRAINT FK_Files_Users REFERENCES Users(user_id),
        file_name NVARCHAR(255) NOT NULL,
        blob_url NVARCHAR(500) NOT NULL,
        encryption_iv VARBINARY(16),
        uploaded_at DATETIME2 DEFAULT SYSUTCDATETIME()
      );
    END
    """
]

def run_migration():
    try:
        with pyodbc.connect(conn_str) as conn:
            cursor = conn.cursor()
            for stmt in ddl_statements:
                cursor.execute(stmt)
            conn.commit()
        print("🎉 Tables created (or already exist) successfully!")
    except Exception as e:
        print("⚠️ Migration failed:", e)

if __name__ == "__main__":
    run_migration()
