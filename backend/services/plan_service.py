"""
Subscription Plan Management Service
====================================
Handles subscription plan catalog, frequency configuration, date window validation,
minimum quantity constraints, and policy management.
"""

from datetime import datetime, date
from decimal import Decimal
from models import db
from models.plan import SubscriptionPlan, PlanProduct
from models.product import Product


VALID_FREQUENCIES = ["daily", "weekly", "monthly", "yearly"]


class PlanService:
    """Service handling Subscription Plan configuration and policy enforcement."""

    @staticmethod
    def list_plans(active_only: bool = False, available_only: bool = False, search: str | None = None):
        """Lists subscription plans with optional filtering."""
        query = SubscriptionPlan.query

        if active_only:
            query = query.filter_by(is_active=True)

        plans = query.order_by(SubscriptionPlan.name.asc()).all()

        if available_only:
            plans = [p for p in plans if p.is_available]

        if search:
            term = search.strip().lower()
            plans = [p for p in plans if term in p.name.lower() or term in p.code.lower()]

        return [p.to_dict(include_products=True) for p in plans]

    @staticmethod
    def get_plan_by_id(plan_id: int):
        """Retrieves a single subscription plan with default products."""
        plan = db.session.get(SubscriptionPlan, plan_id)
        return plan.to_dict(include_products=True) if plan else None

    @classmethod
    def create_plan(cls, data: dict) -> tuple[dict | None, str | None]:
        """Creates a subscription plan with validation."""
        name = (data.get("name") or "").strip()
        code = (data.get("code") or "").strip().upper()
        description = (data.get("description") or "").strip() or None
        frequency = (data.get("billing_frequency") or "monthly").strip().lower()

        if not name or not code:
            return None, "Plan name and unique code are required"

        if frequency not in VALID_FREQUENCIES:
            return None, f"Invalid billing frequency. Must be one of: {', '.join(VALID_FREQUENCIES)}"

        try:
            base_price = Decimal(str(data.get("base_price", 0)))
            if base_price < 0:
                return None, "Base price cannot be negative"
        except Exception:
            return None, "Base price must be a valid number"

        try:
            min_qty = int(data.get("minimum_quantity", 1))
            if min_qty < 1:
                return None, "Minimum quantity must be at least 1"
        except Exception:
            return None, "Minimum quantity must be a valid positive integer"

        # Validate date window
        start_date = None
        end_date = None
        if data.get("start_date"):
            try:
                start_date = datetime.strptime(data["start_date"], "%Y-%m-%d").date()
            except ValueError:
                return None, "Invalid start date format (expected YYYY-MM-DD)"

        if data.get("end_date"):
            try:
                end_date = datetime.strptime(data["end_date"], "%Y-%m-%d").date()
            except ValueError:
                return None, "Invalid end date format (expected YYYY-MM-DD)"

        if start_date and end_date and end_date < start_date:
            return None, "End date cannot precede start date"

        if SubscriptionPlan.query.filter_by(code=code).first():
            return None, f"Plan code '{code}' already exists"

        plan = SubscriptionPlan(
            name=name,
            code=code,
            description=description,
            base_price=base_price,
            billing_frequency=frequency,
            minimum_quantity=min_qty,
            start_date=start_date,
            end_date=end_date,
            allow_pause=bool(data.get("allow_pause", True)),
            allow_renewal=bool(data.get("allow_renewal", True)),
            allow_early_close=bool(data.get("allow_early_close", True)),
            auto_close_on_expiry=bool(data.get("auto_close_on_expiry", False)),
            is_active=bool(data.get("is_active", True)),
        )
        db.session.add(plan)
        db.session.flush()

        # Handle associated default products
        products_data = data.get("products", [])
        for p in products_data:
            p_id = p.get("product_id")
            if not p_id or not Product.query.get(p_id):
                continue
            plan_prod = PlanProduct(
                plan_id=plan.id,
                product_id=p_id,
                default_quantity=max(1, int(p.get("default_quantity", 1)))
            )
            db.session.add(plan_prod)

        db.session.commit()
        return plan.to_dict(include_products=True), None

    @classmethod
    def update_plan(cls, plan_id: int, data: dict) -> tuple[dict | None, str | None]:
        """Updates plan details without modifying historical subscriptions."""
        plan = db.session.get(SubscriptionPlan, plan_id)
        if not plan:
            return None, "Plan not found"

        if "name" in data and data["name"].strip():
            plan.name = data["name"].strip()

        if "code" in data:
            code = data["code"].strip().upper()
            if code != plan.code:
                if SubscriptionPlan.query.filter_by(code=code).first():
                    return None, f"Plan code '{code}' already exists"
                plan.code = code

        if "description" in data:
            plan.description = data["description"].strip() or None

        if "billing_frequency" in data:
            freq = data["billing_frequency"].strip().lower()
            if freq not in VALID_FREQUENCIES:
                return None, f"Invalid billing frequency. Must be one of: {', '.join(VALID_FREQUENCIES)}"
            plan.billing_frequency = freq

        if "base_price" in data:
            try:
                bp = Decimal(str(data["base_price"]))
                if bp < 0:
                    return None, "Base price cannot be negative"
                plan.base_price = bp
            except Exception:
                return None, "Base price must be a valid number"

        if "minimum_quantity" in data:
            try:
                mq = int(data["minimum_quantity"])
                if mq < 1:
                    return None, "Minimum quantity must be at least 1"
                plan.minimum_quantity = mq
            except Exception:
                return None, "Minimum quantity must be a valid positive integer"

        # Validate start and end dates
        start_date = plan.start_date
        end_date = plan.end_date

        if "start_date" in data:
            if data["start_date"]:
                try:
                    start_date = datetime.strptime(data["start_date"], "%Y-%m-%d").date()
                except ValueError:
                    return None, "Invalid start date format (YYYY-MM-DD)"
            else:
                start_date = None

        if "end_date" in data:
            if data["end_date"]:
                try:
                    end_date = datetime.strptime(data["end_date"], "%Y-%m-%d").date()
                except ValueError:
                    return None, "Invalid end date format (YYYY-MM-DD)"
            else:
                end_date = None

        if start_date and end_date and end_date < start_date:
            return None, "End date cannot precede start date"

        plan.start_date = start_date
        plan.end_date = end_date

        # Policies
        if "allow_pause" in data:
            plan.allow_pause = bool(data["allow_pause"])
        if "allow_renewal" in data:
            plan.allow_renewal = bool(data["allow_renewal"])
        if "allow_early_close" in data:
            plan.allow_early_close = bool(data["allow_early_close"])
        if "auto_close_on_expiry" in data:
            plan.auto_close_on_expiry = bool(data["auto_close_on_expiry"])
        if "is_active" in data:
            plan.is_active = bool(data["is_active"])

        # Update product associations if provided
        if "products" in data:
            PlanProduct.query.filter_by(plan_id=plan.id).delete()
            for p in data["products"]:
                p_id = p.get("product_id")
                if not p_id or not Product.query.get(p_id):
                    continue
                plan_prod = PlanProduct(
                    plan_id=plan.id,
                    product_id=p_id,
                    default_quantity=max(1, int(p.get("default_quantity", 1)))
                )
                db.session.add(plan_prod)

        db.session.commit()
        return plan.to_dict(include_products=True), None

    @classmethod
    def toggle_plan_active(cls, plan_id: int) -> tuple[dict | None, str | None]:
        """Toggles plan active status."""
        plan = db.session.get(SubscriptionPlan, plan_id)
        if not plan:
            return None, "Plan not found"
        plan.is_active = not plan.is_active
        db.session.commit()
        return plan.to_dict(include_products=True), None

