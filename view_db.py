"""
Quick Database Inspector for Subscription Management System
============================================================
Prints all tables, schemas, and live records in instance/subscription_system.db.
"""

import sqlite3
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "instance" / "subscription_system.db"

if not DB_PATH.exists():
    print(f"Database file not found at: {DB_PATH}")
    exit(1)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("=" * 70)
print("     DATABASE TABLES & RECORD COUNTS")
print("=" * 70)

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
tables = [t[0] for t in cursor.fetchall()]

for table in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {table};")
    count = cursor.fetchone()[0]
    print(f" - {table:<25} : {count} records")

print("\n" + "=" * 70)
print("     SAMPLE DATA IN MAIN TABLES")
print("=" * 70)

display_tables = ["users", "products", "product_variants", "plans", "quotations", "subscriptions"]

for table in display_tables:
    if table not in tables:
        continue
    print(f"\n--- [ Table: {table.upper()} ] ---")
    cursor.execute(f"PRAGMA table_info({table});")
    columns = [col[1] for col in cursor.fetchall()]
    print(" | ".join(columns[:6]))
    print("-" * 65)

    cursor.execute(f"SELECT * FROM {table} LIMIT 5;")
    rows = cursor.fetchall()
    if not rows:
        print("(No records found)")
    else:
        for r in rows:
            # Mask password hash if viewing users table for readability
            row_display = []
            for col_idx, val in enumerate(r[:6]):
                if table == "users" and columns[col_idx] == "password_hash":
                    row_display.append("[HASHED]")
                else:
                    row_display.append(str(val))
            print(" | ".join(row_display))

conn.close()
print("\n" + "=" * 70)
print("Database inspection complete.")
print("=" * 70)
