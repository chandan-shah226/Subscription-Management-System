"""
Quotation and Quotation Item Models
===================================
Defines Quotation and QuotationItem entities supporting templates and lifecycle states.
"""

from datetime import datetime, date, timezone
from decimal import Decimal
from models import db


class Quotation(db.Model):
    """Quotation entity representing proposals, pricing estimates, and reusable templates."""
    __tablename__ = "quotations"

    id = db.Column(db.Integer, primary_key=True)
    quotation_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    creator_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("subscription_plans.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Status lifecycle: draft -> quotation / sent -> confirmed / rejected / expired
    status = db.Column(db.String(20), nullable=False, default="draft")
    valid_until = db.Column(db.Date, nullable=False)
    
    subtotal = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    tax_rate = db.Column(db.Numeric(5, 2), nullable=False, default=Decimal("18.00"))
    tax_amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    total_amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    
    is_template = db.Column(db.Boolean, default=False, nullable=False)
    template_name = db.Column(db.String(120), nullable=True)
    terms_conditions = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    customer = db.relationship("User", foreign_keys=[customer_id], backref="customer_quotations")
    creator = db.relationship("User", foreign_keys=[creator_id], backref="created_quotations")
    plan = db.relationship("SubscriptionPlan", backref="quotations")
    items = db.relationship("QuotationItem", backref="quotation", cascade="all, delete-orphan", lazy="dynamic")
    subscription = db.relationship("Subscription", backref="quotation", uselist=False)

    @property
    def is_expired(self) -> bool:
        """Determines if the quotation is past its validity date."""
        return date.today() > self.valid_until if self.valid_until else False

    def to_dict(self, include_items: bool = True) -> dict:
        data = {
            "id": self.id,
            "quotation_number": self.quotation_number,
            "customer_id": self.customer_id,
            "customer_name": self.customer.full_name if self.customer else None,
            "customer_email": self.customer.email if self.customer else None,
            "creator_id": self.creator_id,
            "creator_name": self.creator.full_name if self.creator else None,
            "plan_id": self.plan_id,
            "plan_name": self.plan.name if self.plan else None,
            "status": self.status,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "is_expired": self.is_expired,
            "subtotal": float(self.subtotal),
            "tax_rate": float(self.tax_rate),
            "tax_amount": float(self.tax_amount),
            "total_amount": float(self.total_amount),
            "is_template": self.is_template,
            "template_name": self.template_name,
            "terms_conditions": self.terms_conditions,
            "notes": self.notes,
            "has_converted_subscription": self.subscription is not None,
            "subscription_id": self.subscription.id if self.subscription else None,
            "subscription_number": self.subscription.subscription_number if self.subscription else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_items:
            data["items"] = [item.to_dict() for item in self.items.all()]
        return data


class QuotationItem(db.Model):
    """Line item within a quotation preserving product, variant, and pricing snapshots."""
    __tablename__ = "quotation_items"

    id = db.Column(db.Integer, primary_key=True)
    quotation_id = db.Column(db.Integer, db.ForeignKey("quotations.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    variant_id = db.Column(db.Integer, db.ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True, index=True)
    
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)  # snapshot of base + variant price
    tax_rate = db.Column(db.Numeric(5, 2), nullable=False, default=Decimal("18.00"))
    tax_amount = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    total_price = db.Column(db.Numeric(12, 2), nullable=False)

    # Relationships
    product = db.relationship("Product")
    variant = db.relationship("ProductVariant")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "quotation_id": self.quotation_id,
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

