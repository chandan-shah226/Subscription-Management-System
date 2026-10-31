"""
Discount Management Service
===========================
Handles discount rule administration, validation, eligibility checks, and usage limits.
"""

from datetime import date
from decimal import Decimal
from models import db
from models.discount import Discount


class DiscountService:
    """Service governing discount rules, eligibility validation, and rate calculations."""

    @classmethod
    def list_discounts(cls, active_only: bool = False):
        """Lists discounts with optional active status filter."""
        query = Discount.query
        if active_only:
            query = query.filter_by(is_active=True)
        discounts = query.order_by(Discount.id.desc()).all()
        return [d.to_dict() for d in discounts]

    @classmethod
    def get_discount_by_id(cls, discount_id: int):
        d = db.session.get(Discount, discount_id)
        return d.to_dict() if d else None

    @classmethod
    def create_discount(cls, data: dict) -> tuple[dict | None, str | None]:
        """Creates a new discount rule."""
        name = (data.get("name") or "").strip()
        code = (data.get("code") or "").strip().upper()

        if not name:
            return None, "Discount name is required"
        if not code:
            return None, "Discount code is required"

        existing = Discount.query.filter_by(code=code).first()
        if existing:
            return None, f"Discount code '{code}' already exists"

        discount_type = data.get("discount_type", "percentage").lower()
        if discount_type not in ["percentage", "fixed"]:
            return None, "Invalid discount type; must be 'percentage' or 'fixed'"

        try:
            value = Decimal(str(data.get("value", 0)))
            if value <= Decimal("0.00"):
                return None, "Discount value must be greater than zero"
            if discount_type == "percentage" and value > Decimal("100.00"):
                return None, "Percentage discount cannot exceed 100%"
        except Exception:
            return None, "Invalid discount value"

        min_quantity = data.get("min_quantity")
        if min_quantity is not None:
            min_quantity = int(min_quantity) if min_quantity != "" else None

        min_amount = None
        if data.get("min_amount"):
            min_amount = Decimal(str(data.get("min_amount")))

        start_date = None
        if data.get("start_date"):
            start_date = date.fromisoformat(data["start_date"])

        end_date = None
        if data.get("end_date"):
            end_date = date.fromisoformat(data["end_date"])

        if start_date and end_date and end_date < start_date:
            return None, "End date cannot precede start date"

        max_uses = None
        if data.get("max_uses"):
            max_uses = int(data["max_uses"])

        scope = data.get("scope", "subscription").lower()

        discount = Discount(
            name=name,
            code=code,
            discount_type=discount_type,
            value=value,
            min_quantity=min_quantity,
            min_amount=min_amount,
            start_date=start_date,
            end_date=end_date,
            max_uses=max_uses,
            scope=scope,
            product_id=data.get("product_id") or None,
            is_active=True
        )
        db.session.add(discount)
        db.session.commit()
        return discount.to_dict(), None

    @classmethod
    def toggle_status(cls, discount_id: int) -> tuple[dict | None, str | None]:
        d = db.session.get(Discount, discount_id)
        if not d:
            return None, "Discount not found"
        d.is_active = not d.is_active
        db.session.commit()
        return d.to_dict(), None

    @classmethod
    def validate_code(cls, code: str, amount: float = 0, quantity: int = 1) -> tuple[dict | None, str | None]:
        """Validates coupon code for quotation or invoice checkout."""
        if not code:
            return None, "Discount code required"
        d = Discount.query.filter_by(code=code.strip().upper()).first()
        if not d:
            return None, f"Discount code '{code}' does not exist"

        valid, err = d.is_valid_now(amount=Decimal(str(amount)), quantity=quantity)
        if not valid:
            return None, err

        discount_amount = d.calculate_discount(Decimal(str(amount)))
        res = d.to_dict()
        res["calculated_discount"] = float(discount_amount)
        return res, None
