import sys
import os

# Add the current directory to the sys path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.config import get_db_connection
from app.modules.auth import get_password_hash

def seed_admin(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if user already exists
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    existing_user = cursor.fetchone()
    
    if existing_user:
        print(f"[-] User '{username}' already exists.")
        # Optionally update password
        update = input(f"Do you want to update the password for '{username}'? (y/N): ")
        if update.lower() == 'y':
            hashed_pw = get_password_hash(password)
            cursor.execute(
                "UPDATE users SET hashed_password = ? WHERE username = ?",
                (hashed_pw, username)
            )
            conn.commit()
            print(f"[+] Password for '{username}' updated successfully.")
    else:
        hashed_pw = get_password_hash(password)
        cursor.execute(
            "INSERT INTO users (username, hashed_password, role) VALUES (?, ?, ?)",
            (username, hashed_pw, "admin")
        )
        conn.commit()
        print(f"[+] Admin user '{username}' created successfully!")
        
    conn.close()

if __name__ == "__main__":
    print("=== Admin Seeder ===")
    if len(sys.argv) == 3:
        target_user = sys.argv[1]
        target_pass = sys.argv[2]
    else:
        target_user = input("Enter admin username [default: admin]: ").strip() or "admin"
        target_pass = input("Enter admin password [default: admin123]: ").strip() or "admin123"
        
    seed_admin(target_user, target_pass)
    print("=== Done ===")
