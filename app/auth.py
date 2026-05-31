import os
import sqlite3
import shutil
import bcrypt

USERS_DB_PATH = "/app/data/users.db"

def init_users_db():
    os.makedirs(os.path.dirname(USERS_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(USERS_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def register_user(username: str, email: str, password: str) -> tuple:
    init_users_db()
    conn = sqlite3.connect(USERS_DB_PATH)
    try:
        hashed = hash_password(password)
        cursor = conn.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, hashed)
        )
        user_id = cursor.lastrowid
        conn.commit()

        # Create user directories
        user_dir = os.path.join("/app/data/users", str(user_id))
        uploads_dir = os.path.join(user_dir, "uploads")
        generated_dir = os.path.join(user_dir, "generated")
        os.makedirs(user_dir, exist_ok=True)
        os.makedirs(uploads_dir, exist_ok=True)
        os.makedirs(generated_dir, exist_ok=True)

        # Migrate existing global data if present (only once, for first user)
        old_db = "/app/data/jobmatcher.db"
        new_db = os.path.join(user_dir, "jobmatcher.db")
        if os.path.exists(old_db):
            shutil.copy2(old_db, new_db)
            old_uploads = "/app/data/uploads"
            old_generated = "/app/data/generated"
            if os.path.exists(old_uploads):
                for f in os.listdir(old_uploads):
                    src = os.path.join(old_uploads, f)
                    dst = os.path.join(uploads_dir, f)
                    if os.path.isfile(src):
                        shutil.copy2(src, dst)
            if os.path.exists(old_generated):
                for f in os.listdir(old_generated):
                    src = os.path.join(old_generated, f)
                    dst = os.path.join(generated_dir, f)
                    if os.path.isfile(src):
                        shutil.copy2(src, dst)
            # Move old global DB so it doesn't get copied again for next user
            shutil.move(old_db, old_db + ".migrated")
        else:
            # Initialize empty DB for new user
            from app.db.database import Database
            Database(new_db)

        return True, user_id
    except sqlite3.IntegrityError:
        return False, None
    finally:
        conn.close()

def login_user(username_or_email: str, password: str) -> tuple:
    init_users_db()
    conn = sqlite3.connect(USERS_DB_PATH)
    conn.row_factory = sqlite3.Row
    user = conn.execute(
        "SELECT * FROM users WHERE username = ? OR email = ?",
        (username_or_email, username_or_email)
    ).fetchone()
    conn.close()

    if user and verify_password(password, user["password_hash"]):
        return True, dict(user)
    return False, None

def get_user_paths(user_id: int) -> dict:
    user_dir = os.path.join("/app/data/users", str(user_id))
    return {
        "user_dir": user_dir,
        "db_path": os.path.join(user_dir, "jobmatcher.db"),
        "uploads_dir": os.path.join(user_dir, "uploads"),
        "generated_dir": os.path.join(user_dir, "generated")
    }

def delete_user(user_id: int) -> bool:
    """Permanently delete a user and all their data."""
    try:
        # Remove user data directory
        paths = get_user_paths(user_id)
        if os.path.exists(paths["user_dir"]):
            shutil.rmtree(paths["user_dir"])

        # Remove from users database
        init_users_db()
        conn = sqlite3.connect(USERS_DB_PATH)
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error deleting user {user_id}: {e}")
        return False
