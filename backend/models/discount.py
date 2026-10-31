"""
Discount Model
==============
Defines promotional and seat-based discount rules created by Administrators.
"""

from datetime import datetime, date, timezone
from decimal import Decimal
from models import db


class Discount(db.Model):
    """Discount rule governing promotional coupons and seat-volume price breaks."""
    __tablename__ = "discounts"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    discount_type = db.Column(db.String(20), nullable=False, default="percentage")  # percentage, fixed
    value = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))

    min_quantity = db.Column(db.Integer, nullable=True)
    min_amount = db.Column(db.Numeric(12, 2), nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)

    max_uses = db.Column(db.Integer, nullable=True)
    used_count = db.Column(db.Integer, nullable=False, default=0)

    scope = db.Column(db.String(20), nullable=False, default="subscription")  # subscription, product
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="SET NULL"), nullable=True)

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationship
    product = db.relationship("Product")

    def is_valid_now(self, amount: Decimal = None, quantity: int = None) -> tuple[bool, str]:
        """Checks if the discount is active, within date bounds, and meets volume thresholds."""
        today = date.today()
        if not self.is_active:
            return False, "Discount is inactive"
        if self.start_date and today < self.start_date:
            return False, f"Discount begins on {self.start_date}"
        if self.end_date and today > self.end_date:
            return False, f"Discount expired on {self.end_date}"
        if self.max_uses and self.used_count >= self.max_uses:
            return False, "Discount usage limit reached"
        if self.min_quantity and quantity is not None and quantity < self.min_quantity:
            return False, f"Requires minimum quantity of {self.min_quantity}"
        if self.min_amount and amount is not None and amount < self.min_amount:
            return False, f"Requires minimum purchase of ${float(self.min_amount):.2f}"
        return True, ""

    def calculate_discount(self, gross_amount: Decimal) -> Decimal:
        """Calculates discount amount in dollars given gross amount."""
        if self.discount_type == "percentage":
            return round(gross_amount * (self.value / Decimal("100.00")), 2)
        else:
            return min(gross_amount, self.value)

    def to_dict(self) -> dict:
        today = date.today()
        is_expired = bool(self.end_date and today > self.end_date)
        is_exhausted = bool(self.max_uses and self.used_count >= self.max_uses)

        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "discount_type": self.discount_type,
            "value": float(self.value),
            "min_quantity": self.min_quantity,
            "min_amount": float(self.min_amount) if self.min_amount else None,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "max_uses": self.max_uses,
            "used_count": self.used_count,
            "scope": self.scope,
            "product_id": self.product_id,
            "product_name": self.product.name if self.product else None,
            "is_active": self.is_active and not is_expired and not is_exhausted,
            "status_label": "Expired" if is_expired else "Exhausted" if is_exhausted else "Active" if self.is_active else "Inactive",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
