"""Clean database - remove all test data, keep structure intact."""
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent.parent / "gato_contable.db"
BACKUP_DIR = Path(__file__).resolve().parent.parent.parent / "backups"

# Tables to clean (order matters for foreign keys)
TABLES_TO_CLEAN = [
    "system_audit_logs",
    "user_audit_logs",
    "electronic_invoices",
    "open_account_items",
    "open_accounts",
    "purchase_items",
    "purchases",
    "inventory_movements",
    "sale_items",
    "sales",
    "cash_register_sessions",
    "product_qr_codes",
    "expenses",
    "products",
    "suppliers",
    "users",
    "company_info",
]


def backup_database():
    """Create a backup before cleaning."""
    if not DB_PATH.exists():
        print("Database not found, nothing to backup.")
        return None

    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUP_DIR / f"gato_contable_backup_clean_{timestamp}.db"
    shutil.copy2(DB_PATH, backup_path)
    print(f"Backup created: {backup_path}")
    return backup_path


def clean_database():
    """Remove all data from tables."""
    if not DB_PATH.exists():
        print("Database not found!")
        return False

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # Disable foreign key checks temporarily
    cur.execute("PRAGMA foreign_keys = OFF")

    total_deleted = 0
    for table in TABLES_TO_CLEAN:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            if count > 0:
                cur.execute(f"DELETE FROM {table}")
                total_deleted += count
                print(f"  {table}: {count} rows deleted")
            else:
                print(f"  {table}: empty")
        except sqlite3.OperationalError as e:
            print(f"  {table}: error - {e}")

    # Reset autoincrement sequences
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'sqlite_sequence'")
    if cur.fetchone():
        cur.execute("DELETE FROM sqlite_sequence")

    # Re-enable foreign key checks
    cur.execute("PRAGMA foreign_keys = ON")

    conn.commit()
    conn.close()

    print(f"\nTotal rows deleted: {total_deleted}")
    print("Database cleaned successfully!")
    return True


def verify_clean():
    """Verify all tables are empty."""
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    print("\nVerification:")
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]

    all_empty = True
    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        status = "OK" if count == 0 else "NOT EMPTY"
        if count > 0:
            all_empty = False
        print(f"  {table}: {count} rows [{status}]")

    conn.close()
    return all_empty


if __name__ == "__main__":
    print("=" * 50)
    print("DATABASE CLEANUP")
    print("=" * 50)

    print("\n1. Creating backup...")
    backup_database()

    print("\n2. Cleaning data...")
    clean_database()

    print("\n3. Verifying...")
    if verify_clean():
        print("\nDatabase is clean and ready for real data!")
    else:
        print("\nWarning: Some tables still have data!")
