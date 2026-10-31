"""
Invoice Model & Line Items
==========================
Module 4: Invoicing and Recurring Billing.
Lifecycle: Draft -> Confirmed -> Paid (with Cancelled state).
Contains financial line items, customer & subscription references,
fixed-precision amounts, tax/discount tracking, and outstanding balance tracking.
"""

from datetime import datetime, date, timezone
from decimal import Decimal
from sqlalchemy.ext.hybrid import hybrid_property
from models import db


class Invoice(db.Model):
    """Invoice entity representing financial claims and billing records."""
    __tablename__ = "invoices"

    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True, index=True)

    # Billing period representation for recurring invoices
    billing_period_start = db.Column(db.Date, nullable=True)
    billing_period_end = db.Column(db.Date, nullable=True)

    # Dates
    invoice_date = db.Column(db.Date, nullable=False, default=date.today)
    due_date = db.Column(db.Date, nullable=False)

    # Financial figures (Decimal precision)
    subtotal = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    discount_id = db.Column(db.Integer, db.ForeignKey("discounts.id", ondelete="SET NULL"), nullable=True, index=True)
    discount_code = db.Column(db.String(50), nullable=True)
    discount_amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    tax_amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    total_amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    amount_paid = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    outstanding_amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))

    # Status: Draft -> Confirmed -> Paid (or Cancelled)
    status = db.Column(db.String(20), nullable=False, default="Draft", index=True)
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    customer = db.relationship("User", foreign_keys=[customer_id], backref=db.backref("customer_invoices", lazy="dynamic"))
    subscription = db.relationship("Subscription", foreign_keys=[subscription_id], backref=db.backref("subscription_invoices", lazy="dynamic"))
    discount = db.relationship("Discount", foreign_keys=[discount_id])
    items = db.relationship("InvoiceItem", backref="invoice", cascade="all, delete-orphan", lazy="dynamic")
    payments = db.relationship("Payment", backref="invoice", cascade="all, delete-orphan", lazy="dynamic")

    @property
    def is_overdue(self):
        """Returns True if the invoice is Confirmed, has outstanding balance, and is past due."""
        if self.status == "Confirmed" and float(self.outstanding_amount or 0) > 0:
            if self.due_date and self.due_date < date.today():
                return True
        return False


    @hybrid_property
    def amount(self):
        return self.total_amount

    @amount.expression
    def amount(cls):
        return cls.total_amount

    def to_dict(self, include_items=True, include_payments=True):
        """Serializes invoice object with optional nested line items and payments."""
        return {
            "id": self.id,
            "invoice_number": self.invoice_number,
            "customer_id": self.customer_id,
            "customer_name": self.customer.full_name if self.customer else "Unknown",
            "customer_email": self.customer.email if self.customer else "",
            "customer_phone": getattr(self.customer, "phone", "") or "",
            "subscription_id": self.subscription_id,
            "subscription_number": self.subscription.subscription_number if self.subscription else None,
            "billing_period_start": self.billing_period_start.isoformat() if self.billing_period_start else None,
            "billing_period_end": self.billing_period_end.isoformat() if self.billing_period_end else None,
            "invoice_date": self.invoice_date.isoformat() if self.invoice_date else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "subtotal": float(self.subtotal or 0.0),
            "discount_id": self.discount_id,
            "discount_code": self.discount_code or (self.discount.code if self.discount else ""),
            "discount_amount": float(self.discount_amount or 0.0),
            "tax_amount": float(self.tax_amount or 0.0),
            "total_amount": float(self.total_amount or 0.0),
            "amount_paid": float(self.amount_paid or 0.0),
            "outstanding_amount": float(self.outstanding_amount or 0.0),
            "status": self.status,
            "is_overdue": self.is_overdue,
            "notes": self.notes or "",
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "items": [item.to_dict() for item in self.items.all()] if include_items else [],
            "payments": [payment.to_dict() for payment in self.payments.all()] if include_payments else []
        }


class InvoiceItem(db.Model):
    """Line item for an invoice representing billed products or services."""
    __tablename__ = "invoice_items"

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="RESTRICT"), nullable=True, index=True)
    variant_id = db.Column(db.Integer, db.ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True, index=True)
    description = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("1.00"))
    unit_price = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    discount_amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    tax_rate = db.Column(db.Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    tax_amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    total_amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))

    product = db.relationship("Product", foreign_keys=[product_id])
    variant = db.relationship("ProductVariant", foreign_keys=[variant_id])


    @hybrid_property
    def amount(self):
        return self.total_amount

    @amount.expression
    def amount(cls):
        return cls.total_amount

    def to_dict(self):
        return {
            "id": self.id,
            "invoice_id": self.invoice_id,
            "product_id": self.product_id,
            "variant_id": self.variant_id,
            "product_name": self.product.name if self.product else None,
            "variant_name": self.variant.variant_name if self.variant else None,
            "description": self.description,
            "quantity": float(self.quantity or 0.0),
            "unit_price": float(self.unit_price or 0.0),
            "discount_amount": float(self.discount_amount or 0.0),
            "tax_rate": float(self.tax_rate or 0.0),
            "tax_amount": float(self.tax_amount or 0.0),
            "total_amount": float(self.total_amount or 0.0)
        }
