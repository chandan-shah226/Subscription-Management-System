"""
Subscription Plan Models
========================
Defines SubscriptionPlan and PlanProduct association entities.
"""

from datetime import datetime, date, timezone
from decimal import Decimal
from models import db


class SubscriptionPlan(db.Model):
    """Subscription plan entity defining recurring billing terms, pricing, and lifecycle policies."""
    __tablename__ = "subscription_plans"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    base_price = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    billing_frequency = db.Column(db.String(20), nullable=False, default="monthly")  # daily, weekly, monthly, yearly
    minimum_quantity = db.Column(db.Integer, nullable=False, default=1)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    
    # Lifecycle policies
    allow_pause = db.Column(db.Boolean, default=True, nullable=False)
    allow_renewal = db.Column(db.Boolean, default=True, nullable=False)
    allow_early_close = db.Column(db.Boolean, default=True, nullable=False)
    auto_close_on_expiry = db.Column(db.Boolean, default=False, nullable=False)
    
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    plan_products = db.relationship("PlanProduct", backref="plan", cascade="all, delete-orphan", lazy="dynamic")

    @property
    def is_available(self) -> bool:
        """Checks whether the plan is active and within the availability date window."""
        if not self.is_active:
            return False
        today = date.today()
        if self.start_date and today < self.start_date:
            return False
        if self.end_date and today > self.end_date:
            return False
        return True

    def to_dict(self, include_products: bool = True) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "description": self.description,
            "base_price": float(self.base_price),
            "billing_frequency": self.billing_frequency,
            "minimum_quantity": self.minimum_quantity,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "allow_pause": self.allow_pause,
            "allow_renewal": self.allow_renewal,
            "allow_early_close": self.allow_early_close,
            "auto_close_on_expiry": self.auto_close_on_expiry,
            "is_active": self.is_active,
            "is_available": self.is_available,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_products:
            data["products"] = [pp.to_dict() for pp in self.plan_products.all()]
        return data


class PlanProduct(db.Model):
    """Associates products with subscription plans with default quantities."""
    __tablename__ = "plan_products"

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("subscription_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    default_quantity = db.Column(db.Integer, nullable=False, default=1)

    # Relationship
    product = db.relationship("Product")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "product_id": self.product_id,
            "product_name": self.product.name if self.product else None,
            "product_code": self.product.code if self.product else None,
            "default_quantity": self.default_quantity,
        }

