"""
Payment Model
=============
Defines the payment entity for recording incoming transactions against invoices.
"""

from datetime import datetime, date, timezone
from decimal import Decimal
from sqlalchemy.ext.hybrid import hybrid_property
from models import db


class Payment(db.Model):
    """Payment record associated with an invoice and customer."""
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    payment_reference = db.Column(db.String(50), unique=True, nullable=False, index=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)

    amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    method = db.Column(db.String(30), nullable=False, default="card")  # card, bank_transfer, cash, upi
    status = db.Column(db.String(20), nullable=False, default="successful", index=True)  # successful, pending, failed
    paid_on = db.Column(db.Date, nullable=False, default=date.today, index=True)
    note = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    customer = db.relationship("User", foreign_keys=[customer_id], backref="customer_payments")

    @hybrid_property
    def reference(self) -> str:
        return self.payment_reference

    @reference.setter
    def reference(self, value: str):
        self.payment_reference = value

    @reference.expression
    def reference(cls):
        return cls.payment_reference

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "payment_reference": self.payment_reference,
            "reference": self.payment_reference,
            "invoice_id": self.invoice_id,
            "invoice_number": self.invoice.invoice_number if self.invoice else None,
            "customer_id": self.customer_id,
            "customer_name": self.customer.full_name if self.customer else None,
            "customer_email": self.customer.email if self.customer else None,
            "amount": float(self.amount),
            "method": self.method,
            "status": self.status,
            "paid_on": self.paid_on.isoformat() if self.paid_on else None,
            "note": self.note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
