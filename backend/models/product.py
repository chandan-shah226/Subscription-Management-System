"""
Product and Product Variant Models
==================================
Defines Product and ProductVariant entities.
"""

from datetime import datetime, timezone
from decimal import Decimal
from models import db


class Product(db.Model):
    """Core product entity representing services or physical items."""
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    product_type = db.Column(db.String(30), nullable=False, default="service")  # service, physical
    sales_price = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    cost_price = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    tax_rate = db.Column(db.Numeric(5, 2), nullable=False, default=Decimal("18.00"))  # percentage, e.g. 18.00%
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    variants = db.relationship("ProductVariant", backref="product", cascade="all, delete-orphan", lazy="dynamic")

    def to_dict(self, include_variants: bool = True) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "description": self.description,
            "product_type": self.product_type,
            "sales_price": float(self.sales_price),
            "cost_price": float(self.cost_price),
            "tax_rate": float(self.tax_rate),
            "notes": self.notes,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_variants:
            data["variants"] = [v.to_dict() for v in self.variants.all()]
        return data


class ProductVariant(db.Model):
    """Product variant providing custom attributes, SKU, and additional price modifiers."""
    __tablename__ = "product_variants"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_name = db.Column(db.String(100), nullable=False)
    sku = db.Column(db.String(60), unique=True, nullable=False, index=True)
    additional_price = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "product_id": self.product_id,
            "variant_name": self.variant_name,
            "sku": self.sku,
            "additional_price": float(self.additional_price),
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

