"""
Discount Models (Module 5)
==========================
Defines:
1. Discount: Rule configuration with fixed/percentage types, min purchase, min quantity,
   usage limits, validity date boundaries, and product/subscription scope.
2. DiscountProduct: Explicit M2M mapping for product-scoped discount rules.
3. DiscountRedemption: Concurrency-safe audit trail for applied discounts per invoice.
"""

from datetime import datetime, date, timezone
from decimal import Decimal, ROUND_HALF_UP
from models import db


class Discount(db.Model):
    """Discount rule configuration created and managed by administrators."""
    __tablename__ = "discounts"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255), nullable=True)
    discount_type = db.Column(db.String(20), nullable=False)  # 'fixed' or 'percentage'
    value = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    min_purchase = db.Column(db.Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    min_quantity = db.Column(db.Integer, default=1, nullable=False)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    usage_limit = db.Column(db.Integer, nullable=True)  # Null means unlimited
    times_used = db.Column(db.Integer, default=0, nullable=False)
    
    # Scope: 'all' (entire invoice), 'subscription' (only recurring cycle), 'product' (specific products)
    scope = db.Column(db.String(20), default="all", nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    product_associations = db.relationship(
        "DiscountProduct",
        backref="discount",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    redemptions = db.relationship(
        "DiscountRedemption",
        backref="discount",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    @property
    def is_exhausted(self) -> bool:
        """Returns True if the usage limit has been reached."""
        if self.usage_limit is not None and self.times_used >= self.usage_limit:
            return True
        return False

    @property
    def is_expired(self) -> bool:
        """Returns True if the current date is past the end date."""
        if self.end_date and date.today() > self.end_date:
            return True
        return False

    def is_eligible(self, subtotal, quantity=1, product_ids=None, check_date=None):
        """
        Comprehensive server-side eligibility check:
        - Active status
        - Validity date range
        - Usage limit exhaustion
        - Minimum purchase amount
        - Minimum line item quantity
        - Product scope match
        """
        current_d = check_date or date.today()

        if not self.is_active:
            return False, "Discount is inactive"

        if self.start_date and current_d < self.start_date:
            return False, f"Discount period does not start until {self.start_date.isoformat()}"

        if self.end_date and current_d > self.end_date:
            return False, f"Discount expired on {self.end_date.isoformat()}"

        if self.usage_limit is not None and self.times_used >= self.usage_limit:
            return False, f"Discount usage limit of {self.usage_limit} redemptions reached"

        subtotal_dec = Decimal(str(subtotal or 0))
        if subtotal_dec < self.min_purchase:
            return False, f"Minimum purchase amount of ₹{self.min_purchase:.2f} required (current: ₹{subtotal_dec:.2f})"

        if int(quantity or 0) < int(self.min_quantity or 1):
            return False, f"Minimum quantity of {self.min_quantity} required"

        # Check product scope if applicable
        if self.scope == "product":
            allowed_prod_ids = {dp.product_id for dp in self.product_associations.all()}
            if not allowed_prod_ids:
                return False, "Discount has no assigned eligible products"
            if not product_ids or not set(product_ids).intersection(allowed_prod_ids):
                return False, "None of the billed items match the discount's eligible product list"

        return True, "Eligible"

    def calculate_discount_amount(self, subtotal, eligible_subtotal=None):
        """
        Computes accurate monetary discount in Decimal, bounded by applicable subtotal.
        """
        base_amount = Decimal(str(eligible_subtotal if eligible_subtotal is not None else subtotal or 0))
        if base_amount <= Decimal("0.00"):
            return Decimal("0.00")

        if self.discount_type == "percentage":
            pct = Decimal(str(self.value))
            pct = min(Decimal("100.00"), max(Decimal("0.00"), pct))
            discount = (base_amount * (pct / Decimal("100.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            discount = Decimal(str(self.value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        return min(discount, base_amount)

    def to_dict(self, include_products=True):
        data = {
            "id": self.id,
            "code": self.code,
            "description": self.description or "",
            "discount_type": self.discount_type,
            "value": float(self.value or 0.0),
            "min_purchase": float(self.min_purchase or 0.0),
            "min_quantity": self.min_quantity,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "usage_limit": self.usage_limit,
            "times_used": self.times_used,
            "scope": self.scope,
            "is_active": self.is_active,
            "is_exhausted": self.is_exhausted,
            "is_expired": self.is_expired,
            "created_by": self.created_by.full_name if self.created_by else "System",
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
        if include_products:
            data["product_ids"] = [dp.product_id for dp in self.product_associations.all()]
        return data


class DiscountProduct(db.Model):
    """Association table linking a Discount rule to specific Products."""
    __tablename__ = "discount_products"

    id = db.Column(db.Integer, primary_key=True)
    discount_id = db.Column(db.Integer, db.ForeignKey("discounts.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)

    product = db.relationship("Product", foreign_keys=[product_id])


class DiscountRedemption(db.Model):
    """Audit record preserving immutable application of a discount to an invoice."""
    __tablename__ = "discount_redemptions"

    id = db.Column(db.Integer, primary_key=True)
    discount_id = db.Column(db.Integer, db.ForeignKey("discounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    amount_applied = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    redeemed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    customer = db.relationship("User", foreign_keys=[customer_id])
    invoice = db.relationship("Invoice", foreign_keys=[invoice_id])

    def to_dict(self):
        return {
            "id": self.id,
            "discount_id": self.discount_id,
            "discount_code": self.discount.code if self.discount else None,
            "invoice_id": self.invoice_id,
            "invoice_number": self.invoice.invoice_number if self.invoice else None,
            "customer_id": self.customer_id,
            "customer_name": self.customer.full_name if self.customer else None,
            "amount_applied": float(self.amount_applied or 0.0),
            "redeemed_at": self.redeemed_at.isoformat() if self.redeemed_at else None
        }
