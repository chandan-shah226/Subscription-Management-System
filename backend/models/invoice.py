"""
Invoice and Invoice Item Models
===============================
Defines entities for billing, automated invoice generation, and receivables.
"""

from datetime import datetime, date, timezone
from decimal import Decimal
from sqlalchemy.ext.hybrid import hybrid_property
from models import db


class Invoice(db.Model):
    """Invoice entity representing a billing record generated from subscriptions or directly."""
    __tablename__ = "invoices"

    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)

    invoice_date = db.Column(db.Date, nullable=False, default=date.today)
    due_date = db.Column(db.Date, nullable=False)
    
    # Statuses: draft -> confirmed -> paid (or cancelled)
    status = db.Column(db.String(20), nullable=False, default="draft", index=True)

    subtotal = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    tax_amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    discount_amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    total_amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))

    discount_code = db.Column(db.String(50), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    customer = db.relationship("User", foreign_keys=[customer_id], backref="customer_invoices")
    subscription = db.relationship("Subscription", backref="invoices")
    items = db.relationship("InvoiceItem", backref="invoice", cascade="all, delete-orphan", lazy="dynamic")
    payments = db.relationship("Payment", backref="invoice", cascade="all, delete-orphan", lazy="dynamic")

    @hybrid_property
    def number(self) -> str:
        return self.invoice_number

    @number.setter
    def number(self, value: str):
        self.invoice_number = value

    @number.expression
    def number(cls):
        return cls.invoice_number

    @property
    def paid_amount(self) -> float:
        total_paid = Decimal("0.00")
        for p in self.payments.all():
            if p.status == "successful":
                total_paid += Decimal(str(p.amount))
        return float(total_paid)

    @property
    def outstanding_balance(self) -> float:
        remaining = float(self.total_amount) - self.paid_amount
        return max(0.0, remaining)

    @property
    def is_overdue(self) -> bool:
        if self.status in ["paid", "cancelled"]:
            return False
        return self.due_date < date.today()

    def to_dict(self, include_items: bool = True, include_payments: bool = False) -> dict:
        data = {
            "id": self.id,
            "invoice_number": self.invoice_number,
            "number": self.invoice_number,
            "subscription_id": self.subscription_id,
            "subscription_number": self.subscription.subscription_number if self.subscription else None,
            "customer_id": self.customer_id,
            "customer_name": self.customer.full_name if self.customer else None,
            "customer_email": self.customer.email if self.customer else None,
            "invoice_date": self.invoice_date.isoformat() if self.invoice_date else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "status": "overdue" if self.is_overdue and self.status != "draft" else self.status,
            "raw_status": self.status,
            "is_overdue": self.is_overdue,
            "subtotal": float(self.subtotal),
            "tax_amount": float(self.tax_amount),
            "discount_amount": float(self.discount_amount),
            "total_amount": float(self.total_amount),
            "amount": float(self.amount or self.total_amount),
            "paid_amount": self.paid_amount,
            "outstanding_balance": self.outstanding_balance,
            "discount_code": self.discount_code,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_items:
            data["items"] = [item.to_dict() for item in self.items.all()]
        if include_payments:
            data["payments"] = [p.to_dict() for p in self.payments.all()]
        return data


class InvoiceItem(db.Model):
    """Line item on an invoice."""
    __tablename__ = "invoice_items"

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="RESTRICT"), nullable=True)
    variant_id = db.Column(db.Integer, db.ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True)

    description = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    tax_rate = db.Column(db.Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    total_price = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))

    # Relationships
    product = db.relationship("Product")
    variant = db.relationship("ProductVariant")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "invoice_id": self.invoice_id,
            "product_id": self.product_id,
            "product_name": self.product.name if self.product else self.description,
            "variant_id": self.variant_id,
            "variant_name": self.variant.variant_name if self.variant else None,
            "description": self.description,
            "quantity": self.quantity,
            "unit_price": float(self.unit_price),
            "tax_rate": float(self.tax_rate),
            "total_price": float(self.total_price),
        }
