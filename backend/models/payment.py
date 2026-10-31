"""
Payment Models (Module 6)
=========================
Defines:
1. Payment: Financial payment receipts against invoices, supporting both
   offline/manual entry and online Razorpay gateway captures with audit trail.
2. PaymentWebhookEvent: Deduplication and audit log for Razorpay webhook callbacks.
"""

from datetime import datetime, date, timezone
from decimal import Decimal
from sqlalchemy.ext.hybrid import hybrid_property
from models import db


class Payment(db.Model):
    """Payment record linked to a specific Invoice."""
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    currency = db.Column(db.String(10), nullable=False, default="INR")
    payment_method = db.Column(db.String(50), nullable=False)  # Bank Transfer, Credit Card, UPI, Razorpay, Cash, Cheque
    payment_source = db.Column(db.String(20), nullable=False, default="manual")  # 'manual' or 'razorpay'
    status = db.Column(db.String(20), nullable=False, default="captured", index=True)  # 'captured', 'pending', 'failed'
    payment_date = db.Column(db.Date, nullable=False, default=date.today)
    reference_number = db.Column(db.String(100), nullable=True)
    
    # Razorpay Gateway References
    razorpay_order_id = db.Column(db.String(100), nullable=True, index=True)
    razorpay_payment_id = db.Column(db.String(100), nullable=True, index=True)
    razorpay_signature = db.Column(db.String(255), nullable=True)

    notes = db.Column(db.Text, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    recorded_by = db.relationship("User", foreign_keys=[created_by_id])


    @hybrid_property
    def paid_on(self):
        return self.payment_date

    @paid_on.expression
    def paid_on(cls):
        return cls.payment_date

    @hybrid_property
    def reference(self):
        return self.reference_number

    @reference.expression
    def reference(cls):
        return cls.reference_number



    def to_dict(self):
        return {
            "id": self.id,
            "invoice_id": self.invoice_id,
            "invoice_number": self.invoice.invoice_number if self.invoice else None,
            "customer_name": self.invoice.customer.full_name if self.invoice and self.invoice.customer else "Unknown",
            "amount": float(self.amount or 0.0),
            "currency": self.currency,
            "payment_method": self.payment_method,
            "payment_source": self.payment_source,
            "status": self.status,
            "payment_date": self.payment_date.isoformat() if self.payment_date else None,
            "reference_number": self.reference_number or "",
            "razorpay_order_id": self.razorpay_order_id or "",
            "razorpay_payment_id": self.razorpay_payment_id or "",
            "notes": self.notes or "",
            "created_by": self.recorded_by.full_name if self.recorded_by else ("Razorpay Gateway" if self.payment_source == "razorpay" else "System"),
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class PaymentWebhookEvent(db.Model):
    """Event log for Razorpay webhooks to guarantee idempotency and auditability."""
    __tablename__ = "payment_webhook_events"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    event_type = db.Column(db.String(50), nullable=False)
    payload = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="processed")  # 'processed', 'skipped_duplicate', 'failed'
    processed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


    @hybrid_property
    def paid_on(self):
        return self.payment_date

    @paid_on.expression
    def paid_on(cls):
        return cls.payment_date

    @hybrid_property
    def reference(self):
        return self.reference_number

    @reference.expression
    def reference(cls):
        return cls.reference_number



    def to_dict(self):
        return {
            "id": self.id,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "status": self.status,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None
        }
