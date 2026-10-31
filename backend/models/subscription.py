"""
Subscription, Subscription Item, and Audit Log Models
=====================================================
Defines Subscription, SubscriptionItem, and SubscriptionAuditLog entities.
"""

from datetime import datetime, timezone
from decimal import Decimal
from models import db


class Subscription(db.Model):
    """Subscription entity governing active recurring services, billing schedules, and lifecycle states."""
    __tablename__ = "subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    subscription_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    quotation_id = db.Column(db.Integer, db.ForeignKey("quotations.id", ondelete="SET NULL"), nullable=True, index=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("subscription_plans.id", ondelete="RESTRICT"), nullable=False, index=True)

    # Lifecycle states: draft -> quotation -> confirmed -> active -> closed / paused / expired
    status = db.Column(db.String(20), nullable=False, default="draft")
    billing_frequency = db.Column(db.String(20), nullable=False, default="monthly")
    
    start_date = db.Column(db.Date, nullable=False)
    next_billing_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    auto_renew = db.Column(db.Boolean, default=True, nullable=False)

    subtotal = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    tax_amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    total_amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    plan_name = db.Column(db.String(120), nullable=True)
    product_name = db.Column(db.String(120), nullable=True)
    renews_on = db.Column(db.Date, nullable=True)

    paused_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    customer = db.relationship("User", foreign_keys=[customer_id], backref="customer_subscriptions")
    plan = db.relationship("SubscriptionPlan", backref="subscriptions")
    items = db.relationship("SubscriptionItem", backref="subscription", cascade="all, delete-orphan", lazy="dynamic")
    audit_logs = db.relationship(
        "SubscriptionAuditLog",
        backref="subscription",
        cascade="all, delete-orphan",
        order_by="SubscriptionAuditLog.timestamp.desc()",
        lazy="dynamic"
    )

    def to_dict(self, include_items: bool = True, include_logs: bool = False) -> dict:
        data = {
            "id": self.id,
            "subscription_number": self.subscription_number,
            "customer_id": self.customer_id,
            "customer_name": self.customer.full_name if self.customer else None,
            "customer_email": self.customer.email if self.customer else None,
            "quotation_id": self.quotation_id,
            "plan_id": self.plan_id,
            "plan_name": self.plan.name if self.plan else None,
            "status": self.status,
            "billing_frequency": self.billing_frequency,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "next_billing_date": self.next_billing_date.isoformat() if self.next_billing_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "auto_renew": self.auto_renew,
            "subtotal": float(self.subtotal),
            "tax_amount": float(self.tax_amount),
            "total_amount": float(self.total_amount),
            "paused_at": self.paused_at.isoformat() if self.paused_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "notes": self.notes,
            "allow_pause": self.plan.allow_pause if self.plan else True,
            "allow_renewal": self.plan.allow_renewal if self.plan else True,
            "allow_early_close": self.plan.allow_early_close if self.plan else True,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_items:
            data["items"] = [item.to_dict() for item in self.items.all()]
        if include_logs:
            data["audit_logs"] = [log.to_dict() for log in self.audit_logs.all()]
        return data


class SubscriptionItem(db.Model):
    """Agreed snapshot product and pricing line item for an active subscription."""
    __tablename__ = "subscription_items"

    id = db.Column(db.Integer, primary_key=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    variant_id = db.Column(db.Integer, db.ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True, index=True)

    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    tax_rate = db.Column(db.Numeric(5, 2), nullable=False, default=Decimal("18.00"))
    tax_amount = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    total_price = db.Column(db.Numeric(12, 2), nullable=False)

    # Relationships
    product = db.relationship("Product")
    variant = db.relationship("ProductVariant")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "subscription_id": self.subscription_id,
            "product_id": self.product_id,
            "product_name": self.product.name if self.product else None,
            "product_code": self.product.code if self.product else None,
            "variant_id": self.variant_id,
            "variant_name": self.variant.variant_name if self.variant else None,
            "sku": self.variant.sku if self.variant else None,
            "quantity": self.quantity,
            "unit_price": float(self.unit_price),
            "tax_rate": float(self.tax_rate),
            "tax_amount": float(self.tax_amount),
            "total_price": float(self.total_price),
        }


class SubscriptionAuditLog(db.Model):
    """Tracks every lifecycle mutation, status transition, and administrative action on subscriptions."""
    __tablename__ = "subscription_audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False, index=True)
    action = db.Column(db.String(50), nullable=False)  # created, activated, paused, resumed, renewed, closed, expired
    performed_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    details = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationship
    performed_by = db.relationship("User")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "subscription_id": self.subscription_id,
            "action": self.action,
            "performed_by_id": self.performed_by_id,
            "performed_by_name": self.performed_by.full_name if self.performed_by else None,
            "details": self.details,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }

