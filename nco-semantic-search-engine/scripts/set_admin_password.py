"""
Admin password management script.

Usage:
    python scripts/set_admin_password.py

Run from the project root. Prompts for the new password twice (no echo).
Updates the admin_users table in PostgreSQL — no restart required.
"""

import sys
import os
import getpass

# Ensure project root is on the path so imports resolve
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from werkzeug.security import generate_password_hash
from database import db_store

MIN_LENGTH = 8


def main():
    print("\n=== NCO Admin Password Manager ===\n")

    db_store.init_db()

    if not db_store.admin_user_exists():
        print("No admin account found. Creating one...")
        _create_account()
        return

    print("Admin account found.")
    print("Options:")
    print("  1. Change password")
    print("  2. Reset (delete and recreate with a new random password)")
    print("  3. Exit\n")

    choice = input("Enter choice [1/2/3]: ").strip()

    if choice == "1":
        _change_password()
    elif choice == "2":
        _reset_account()
    elif choice == "3":
        print("Exiting.")
    else:
        print("Invalid choice. Exiting.")
        sys.exit(1)


def _prompt_new_password() -> str:
    while True:
        pw = getpass.getpass("New password: ")
        if len(pw) < MIN_LENGTH:
            print(f"Password must be at least {MIN_LENGTH} characters. Try again.")
            continue
        confirm = getpass.getpass("Confirm password: ")
        if pw != confirm:
            print("Passwords do not match. Try again.\n")
            continue
        return pw


def _change_password():
    import secrets as _secrets

    print("\nEnter the new admin password.")
    new_pw = _prompt_new_password()
    new_hash = generate_password_hash(new_pw)

    with db_store.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE admin_users SET password_hash = %s WHERE username = 'admin'",
                (new_hash,),
            )

    print("\nPassword updated successfully.")
    print("The new password is active immediately — no restart needed.\n")


def _reset_account():
    import secrets as _secrets

    confirm = input("\nThis will delete the existing admin account and create a new one.\nType YES to confirm: ").strip()
    if confirm != "YES":
        print("Cancelled.")
        return

    with db_store.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM admin_users WHERE username = 'admin'")

    raw_password = _secrets.token_urlsafe(16)
    db_store.create_admin_user("admin", generate_password_hash(raw_password))

    print("\n" + "=" * 62)
    print("  ADMIN ACCOUNT RESET")
    print("  Username : admin")
    print(f"  Password : {raw_password}")
    print("  Save this password — it will NOT be shown again.")
    print("=" * 62 + "\n")


if __name__ == "__main__":
    main()
