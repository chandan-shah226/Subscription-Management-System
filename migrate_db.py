"""
Safe Database Migration for Modules 4, 5, and 6
===============================================
Adds additive columns and new tables without deleting or corrupting existing data.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "instance", "subscription_system.db")

def migrate():
    print(f"Connecting to database at: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Check and add missing columns to 'invoices'
    cursor.execute("PRAGMA table_info(invoices)")
    inv_cols = [r[1] for r in cursor.fetchall()]

    if "discount_id" not in inv_cols:
        cursor.execute("ALTER TABLE invoices ADD COLUMN discount_id INTEGER REFERENCES discounts(id) ON DELETE SET NULL")
        print("Added 'discount_id' to invoices")

    if "discount_code" not in inv_cols:
        cursor.execute("ALTER TABLE invoices ADD COLUMN discount_code VARCHAR(50)")
        print("Added 'discount_code' to invoices")

    # 2. Check and add missing columns to 'payments'
    cursor.execute("PRAGMA table_info(payments)")
    pay_cols = [r[1] for r in cursor.fetchall()]

    if "currency" not in pay_cols:
        cursor.execute("ALTER TABLE payments ADD COLUMN currency VARCHAR(10) DEFAULT 'INR'")
        print("Added 'currency' to payments")

    if "payment_source" not in pay_cols:
        cursor.execute("ALTER TABLE payments ADD COLUMN payment_source VARCHAR(20) DEFAULT 'manual'")
        print("Added 'payment_source' to payments")

    if "status" not in pay_cols:
        cursor.execute("ALTER TABLE payments ADD COLUMN status VARCHAR(20) DEFAULT 'captured'")
        print("Added 'status' to payments")

    if "razorpay_order_id" not in pay_cols:
        cursor.execute("ALTER TABLE payments ADD COLUMN razorpay_order_id VARCHAR(100)")
        print("Added 'razorpay_order_id' to payments")

    if "razorpay_payment_id" not in pay_cols:
        cursor.execute("ALTER TABLE payments ADD COLUMN razorpay_payment_id VARCHAR(100)")
        print("Added 'razorpay_payment_id' to payments")

    if "razorpay_signature" not in pay_cols:
        cursor.execute("ALTER TABLE payments ADD COLUMN razorpay_signature VARCHAR(255)")
        print("Added 'razorpay_signature' to payments")

    # 3. Check and add missing columns to 'discounts'
    cursor.execute("PRAGMA table_info(discounts)")
    disc_cols = [r[1] for r in cursor.fetchall()]

    if "scope" not in disc_cols:
        cursor.execute("ALTER TABLE discounts ADD COLUMN scope VARCHAR(20) DEFAULT 'all'")
        print("Added 'scope' to discounts")

    if "created_by_id" not in disc_cols:
        cursor.execute("ALTER TABLE discounts ADD COLUMN created_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
        print("Added 'created_by_id' to discounts")

    if "created_at" not in disc_cols:
        cursor.execute("ALTER TABLE discounts ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
        print("Added 'created_at' to discounts")

    if "updated_at" not in disc_cols:
        cursor.execute("ALTER TABLE discounts ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP")
        print("Added 'updated_at' to discounts")

    # 4. Create new tables if absent
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS discount_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        discount_id INTEGER NOT NULL REFERENCES discounts(id) ON DELETE CASCADE,
        product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_discount_products_discount ON discount_products(discount_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_discount_products_product ON discount_products(product_id)")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS discount_redemptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        discount_id INTEGER NOT NULL REFERENCES discounts(id) ON DELETE RESTRICT,
        invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
        customer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
        amount_applied NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
        redeemed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_discount_redemptions_discount ON discount_redemptions(discount_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_discount_redemptions_invoice ON discount_redemptions(invoice_id)")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payment_webhook_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id VARCHAR(100) UNIQUE NOT NULL,
        event_type VARCHAR(50) NOT NULL,
        payload TEXT NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'processed',
        processed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_payment_webhook_events_event_id ON payment_webhook_events(event_id)")

    # 5. Add helpful indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_payments_razorpay_order ON payments(razorpay_order_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_payments_razorpay_payment ON payments(razorpay_payment_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_invoices_subscription_period ON invoices(subscription_id, billing_period_end)")

    conn.commit()
    conn.close()
    print("Migration applied successfully! All existing data preserved.")

if __name__ == "__main__":
    migrate()
