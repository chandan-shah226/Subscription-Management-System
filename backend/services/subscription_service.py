"""
Subscription Management Service
===============================
Handles subscription creation, quotation conversion, date and frequency calculations,
policy enforcement (pause, resume, renew, close), state transitions, and audit logging.
"""

from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from models import db
from models.user import User
from models.product import Product
from models.plan import SubscriptionPlan
from models.quotation import Quotation
from models.subscription import Subscription, SubscriptionItem, SubscriptionAuditLog
from services.product_service import ProductService


class SubscriptionService:
    """Service governing recurring subscription lifecycle, policy enforcement, and audit logs."""

    @staticmethod
    def generate_subscription_number() -> str:
        """Generates a sequential, unique subscription number formatted as SUB-YYYY-XXXX."""
        year = datetime.now(timezone.utc).year
        prefix = f"SUB-{year}-"
        last_sub = Subscription.query.filter(Subscription.subscription_number.like(f"{prefix}%")).order_by(Subscription.id.desc()).first()
        if last_sub and last_sub.subscription_number:
            try:
                seq = int(last_sub.subscription_number.split("-")[-1]) + 1
            except ValueError:
                seq = 1
        else:
            seq = 1
        return f"{prefix}{seq:04d}"

    @staticmethod
    def calculate_next_billing_date(start_from: date, frequency: str) -> date:
        """Calculates the next billing date based on the billing frequency."""
        freq = (frequency or "monthly").lower()
        if freq == "daily":
            return start_from + timedelta(days=1)
        elif freq == "weekly":
            return start_from + timedelta(weeks=1)
        elif freq == "yearly":
            try:
                return start_from.replace(year=start_from.year + 1)
            except ValueError:
                # Handle leap year Feb 29
                return start_from + timedelta(days=365)
        else:  # monthly default
            # Month addition
            month = start_from.month + 1
            year = start_from.year
            if month > 12:
                month = 1
                year += 1
            try:
                return start_from.replace(year=year, month=month)
            except ValueError:
                # If target day exceeds month's days (e.g. Jan 31 -> Feb 28)
                import calendar
                _, max_days = calendar.monthrange(year, month)
                return start_from.replace(year=year, month=month, day=max_days)

    @classmethod
    def list_subscriptions(cls, customer_id: int | None = None, status_filter: str | None = None):
        """Lists subscriptions with optional customer or status filtering."""
        query = Subscription.query

        if customer_id:
            query = query.filter_by(customer_id=customer_id)
        if status_filter:
            query = query.filter_by(status=status_filter)

        subs = query.order_by(Subscription.created_at.desc()).all()

        # Lazy expiration check if end_date has passed and status is active
        today = date.today()
        changed = False
        for s in subs:
            if s.status == "active" and s.end_date and today > s.end_date:
                s.status = "expired"
                changed = True
        if changed:
            db.session.commit()

        return [s.to_dict(include_items=True, include_logs=False) for s in subs]

    @classmethod
    def get_subscription_by_id(cls, subscription_id: int):
        """Retrieves subscription details with items and full audit trail."""
        sub = db.session.get(Subscription, subscription_id)
        if not sub:
            return None

        # Check expiration
        if sub.status == "active" and sub.end_date and date.today() > sub.end_date:
            sub.status = "expired"
            db.session.commit()

        return sub.to_dict(include_items=True, include_logs=True)

    @classmethod
    def convert_quotation_to_subscription(cls, quotation_id: int, user_id: int) -> tuple[dict | None, str | None]:
        """
        Converts a confirmed quotation into an active subscription using database transactions.
        Enforces rules:
        - Quotation must exist and be in 'confirmed' status.
        - Prevent duplicate conversion of the same quotation.
        - Prevent converting rejected or expired quotations.
        - Copy line items with preserved historical snapshot pricing.
        - Create audit log entry.
        """
        quotation = db.session.get(Quotation, quotation_id)
        if not quotation:
            return None, "Quotation not found"

        if quotation.is_template:
            return None, "Cannot convert a template into a subscription"

        # Prevent converting rejected or expired quotations
        if quotation.is_expired or quotation.status == "expired":
            return None, "Quotation has expired and cannot be converted into a subscription"

        if quotation.status == "rejected":
            return None, "Rejected quotations cannot be converted into subscriptions"

        if quotation.status not in ["confirmed", "quotation"]:
            return None, f"Only confirmed quotations can be converted (currently: '{quotation.status}')"

        # Prevent duplicate conversion
        existing_sub = Subscription.query.filter_by(quotation_id=quotation.id).first()
        if existing_sub:
            return None, f"This quotation has already been converted into subscription {existing_sub.subscription_number}"

        # Resolve plan
        plan = quotation.plan
        if not plan:
            return None, "Quotation must be associated with a valid subscription plan to convert"

        # Begin atomic transaction
        try:
            start_date = date.today()
            frequency = plan.billing_frequency
            next_billing_date = cls.calculate_next_billing_date(start_date, frequency)
            end_date = plan.end_date

            subscription = Subscription(
                subscription_number=cls.generate_subscription_number(),
                customer_id=quotation.customer_id,
                quotation_id=quotation.id,
                plan_id=plan.id,
                status="active",
                billing_frequency=frequency,
                start_date=start_date,
                next_billing_date=next_billing_date,
                end_date=end_date,
                auto_renew=plan.allow_renewal,
                subtotal=quotation.subtotal,
                tax_amount=quotation.tax_amount,
                total_amount=quotation.total_amount,
                notes=f"Converted from quotation {quotation.quotation_number}",
            )
            db.session.add(subscription)
            db.session.flush()

            # Copy line items snapshotting prices
            for q_item in quotation.items.all():
                sub_item = SubscriptionItem(
                    subscription_id=subscription.id,
                    product_id=q_item.product_id,
                    variant_id=q_item.variant_id,
                    quantity=q_item.quantity,
                    unit_price=q_item.unit_price,
                    tax_rate=q_item.tax_rate,
                    tax_amount=q_item.tax_amount,
                    total_price=q_item.total_price,
                )
                db.session.add(sub_item)

            # Record audit log
            audit = SubscriptionAuditLog(
                subscription_id=subscription.id,
                action="created",
                performed_by_id=user_id,
                details=f"Subscription created from quotation {quotation.quotation_number}. Activated automatically.",
            )
            db.session.add(audit)

            db.session.commit()
            return subscription.to_dict(include_items=True, include_logs=True), None

        except Exception as e:
            db.session.rollback()
            return None, f"Failed to convert quotation: {str(e)}"

    @classmethod
    def create_direct_subscription(cls, data: dict, user_id: int) -> tuple[dict | None, str | None]:
        """
        Creates a direct subscription with line items and plan policy rules.
        """
        customer_id = data.get("customer_id")
        if not customer_id:
            return None, "Customer ID is required"

        customer = User.query.get(customer_id)
        if not customer or not customer.is_active:
            return None, "Selected customer is invalid or inactive"

        plan_id = data.get("plan_id")
        if not plan_id:
            return None, "Subscription plan ID is required"

        plan = SubscriptionPlan.query.get(plan_id)
        if not plan or not plan.is_available:
            return None, "Selected plan is inactive or outside its availability window"

        items_data = data.get("items", [])
        if not items_data:
            return None, "At least one product line item is required"

        start_date = date.today()
        if data.get("start_date"):
            try:
                start_date = datetime.strptime(data["start_date"], "%Y-%m-%d").date()
            except ValueError:
                return None, "Invalid start date format (YYYY-MM-DD)"

        frequency = (data.get("billing_frequency") or plan.billing_frequency).lower()
        next_billing_date = cls.calculate_next_billing_date(start_date, frequency)
        end_date = plan.end_date

        subtotal = Decimal("0.00")
        total_tax = Decimal("0.00")
        total_qty = 0
        items_to_add = []

        for item_data in items_data:
            p_id = item_data.get("product_id")
            v_id = item_data.get("variant_id") or None
            qty = max(1, int(item_data.get("quantity", 1)))

            unit_price, tax_rate, err = ProductService.calculate_effective_price(p_id, v_id)
            if err:
                return None, err

            line_base = unit_price * Decimal(str(qty))
            line_tax = (line_base * tax_rate / Decimal("100.00")).quantize(Decimal("0.01"))
            line_total = line_base + line_tax

            subtotal += line_base
            total_tax += line_tax
            total_qty += qty

            items_to_add.append({
                "product_id": p_id,
                "variant_id": v_id,
                "quantity": qty,
                "unit_price": unit_price,
                "tax_rate": tax_rate,
                "tax_amount": line_tax,
                "total_price": line_total,
            })

        if total_qty < plan.minimum_quantity:
            return None, f"Total quantity ({total_qty}) does not meet plan '{plan.name}' minimum required quantity ({plan.minimum_quantity})"

        total_amount = subtotal + total_tax

        try:
            subscription = Subscription(
                subscription_number=cls.generate_subscription_number(),
                customer_id=customer.id,
                quotation_id=None,
                plan_id=plan.id,
                status="active",
                billing_frequency=frequency,
                start_date=start_date,
                next_billing_date=next_billing_date,
                end_date=end_date,
                auto_renew=plan.allow_renewal,
                subtotal=subtotal,
                tax_amount=total_tax,
                total_amount=total_amount,
                notes=(data.get("notes") or "").strip() or None,
            )
            db.session.add(subscription)
            db.session.flush()

            for item_dict in items_to_add:
                sub_item = SubscriptionItem(
                    subscription_id=subscription.id,
                    product_id=item_dict["product_id"],
                    variant_id=item_dict["variant_id"],
                    quantity=item_dict["quantity"],
                    unit_price=item_dict["unit_price"],
                    tax_rate=item_dict["tax_rate"],
                    tax_amount=item_dict["tax_amount"],
                    total_price=item_dict["total_price"],
                )
                db.session.add(sub_item)

            audit = SubscriptionAuditLog(
                subscription_id=subscription.id,
                action="created",
                performed_by_id=user_id,
                details="Direct subscription created and activated.",
            )
            db.session.add(audit)

            db.session.commit()
            return subscription.to_dict(include_items=True, include_logs=True), None

        except Exception as e:
            db.session.rollback()
            return None, f"Failed to create direct subscription: {str(e)}"

    @classmethod
    def pause_subscription(cls, subscription_id: int, user_id: int) -> tuple[dict | None, str | None]:
        """
        Pauses an active subscription.
        Rules:
        - Must be currently active.
        - Respect plan's allow_pause policy.
        - Record in audit log.
        """
        sub = db.session.get(Subscription, subscription_id)
        if not sub:
            return None, "Subscription not found"

        if sub.status != "active":
            return None, f"Only active subscriptions can be paused (current status: '{sub.status}')"

        if sub.plan and not sub.plan.allow_pause:
            return None, f"Subscription plan '{sub.plan.name}' policy does not permit pausing"

        sub.status = "paused"
        sub.paused_at = datetime.now(timezone.utc)

        audit = SubscriptionAuditLog(
            subscription_id=sub.id,
            action="paused",
            performed_by_id=user_id,
            details="Subscription was paused by user.",
        )
        db.session.add(audit)
        db.session.commit()

        return sub.to_dict(include_items=True, include_logs=True), None

    @classmethod
    def resume_subscription(cls, subscription_id: int, user_id: int) -> tuple[dict | None, str | None]:
        """
        Resumes a paused subscription.
        Rules:
        - Must be currently paused.
        - Prevent resuming a closed subscription.
        - Record in audit log.
        """
        sub = db.session.get(Subscription, subscription_id)
        if not sub:
            return None, "Subscription not found"

        if sub.status == "closed":
            return None, "Cannot resume a closed subscription"

        if sub.status != "paused":
            return None, f"Only paused subscriptions can be resumed (current status: '{sub.status}')"

        sub.status = "active"
        sub.paused_at = None

        audit = SubscriptionAuditLog(
            subscription_id=sub.id,
            action="resumed",
            performed_by_id=user_id,
            details="Subscription was resumed and is now active.",
        )
        db.session.add(audit)
        db.session.commit()

        return sub.to_dict(include_items=True, include_logs=True), None

    @classmethod
    def renew_subscription(cls, subscription_id: int, user_id: int) -> tuple[dict | None, str | None]:
        """
        Renews an active or expired subscription.
        Rules:
        - Respect plan's allow_renewal policy.
        - Advance next_billing_date based on frequency.
        - Reactivate if expired.
        - Record in audit log.
        """
        sub = db.session.get(Subscription, subscription_id)
        if not sub:
            return None, "Subscription not found"

        if sub.status == "closed":
            return None, "Cannot renew a closed subscription"

        if sub.status not in ["active", "expired"]:
            return None, f"Only active or expired subscriptions can be renewed (current status: '{sub.status}')"

        if sub.plan and not sub.plan.allow_renewal:
            return None, f"Subscription plan '{sub.plan.name}' policy does not permit renewal"

        base_date = max(date.today(), sub.next_billing_date)
        sub.next_billing_date = cls.calculate_next_billing_date(base_date, sub.billing_frequency)
        sub.status = "active"

        audit = SubscriptionAuditLog(
            subscription_id=sub.id,
            action="renewed",
            performed_by_id=user_id,
            details=f"Subscription renewed. Next billing date advanced to {sub.next_billing_date.isoformat()}.",
        )
        db.session.add(audit)
        db.session.commit()

        return sub.to_dict(include_items=True, include_logs=True), None

    @classmethod
    def close_subscription(cls, subscription_id: int, user_id: int) -> tuple[dict | None, str | None]:
        """
        Closes/terminates a subscription.
        Rules:
        - Prevent closing an already closed subscription.
        - If closed before end_date, check allow_early_close policy.
        - Set closed_at timestamp.
        - Record in audit log.
        """
        sub = db.session.get(Subscription, subscription_id)
        if not sub:
            return None, "Subscription not found"

        if sub.status == "closed":
            return None, "Subscription is already closed"

        # Check early-close policy
        if sub.end_date and date.today() < sub.end_date:
            if sub.plan and not sub.plan.allow_early_close:
                return None, f"Subscription plan '{sub.plan.name}' policy does not permit early closure before {sub.end_date.isoformat()}"

        sub.status = "closed"
        sub.closed_at = datetime.now(timezone.utc)

        audit = SubscriptionAuditLog(
            subscription_id=sub.id,
            action="closed",
            performed_by_id=user_id,
            details="Subscription was closed and terminated.",
        )
        db.session.add(audit)
        db.session.commit()

        return sub.to_dict(include_items=True, include_logs=True), None

