"""
Quotation Management Service
============================
Handles quotation creation, line-item pricing and tax computations,
template management, lifecycle operations, and conversion readiness.
"""

from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from models import db
from models.user import User
from models.product import Product, ProductVariant
from models.plan import SubscriptionPlan
from models.quotation import Quotation, QuotationItem
from services.product_service import ProductService


class QuotationService:
    """Service handling Quotation generation, line calculations, templates, and lifecycle states."""

    @staticmethod
    def generate_quotation_number() -> str:
        """Generates a sequential, unique quotation number formatted as QT-YYYY-XXXX."""
        year = datetime.now(timezone.utc).year
        prefix = f"QT-{year}-"
        last_quote = Quotation.query.filter(Quotation.quotation_number.like(f"{prefix}%")).order_by(Quotation.id.desc()).first()
        if last_quote and last_quote.quotation_number:
            try:
                seq = int(last_quote.quotation_number.split("-")[-1]) + 1
            except ValueError:
                seq = 1
        else:
            seq = 1
        return f"{prefix}{seq:04d}"

    @classmethod
    def list_quotations(cls, customer_id: int | None = None, status_filter: str | None = None, is_template: bool = False):
        """Lists quotations with optional filtering by customer, status, or template flag."""
        query = Quotation.query.filter_by(is_template=is_template)

        if customer_id:
            query = query.filter_by(customer_id=customer_id)
        if status_filter:
            query = query.filter_by(status=status_filter)

        quotes = query.order_by(Quotation.created_at.desc()).all()

        # Update expired statuses lazily if validity passed and still in draft/sent
        today = date.today()
        changed = False
        for q in quotes:
            if not q.is_template and q.status in ["draft", "sent", "quotation"] and q.valid_until and today > q.valid_until:
                q.status = "expired"
                changed = True
        if changed:
            db.session.commit()

        return [q.to_dict(include_items=True) for q in quotes]

    @classmethod
    def get_quotation_by_id(cls, quotation_id: int):
        """Retrieves a quotation by ID and updates expiration if necessary."""
        q = db.session.get(Quotation, quotation_id)
        if not q:
            return None

        if not q.is_template and q.status in ["draft", "sent", "quotation"] and q.valid_until and date.today() > q.valid_until:
            q.status = "expired"
            db.session.commit()

        return q.to_dict(include_items=True)

    @classmethod
    def create_quotation(cls, data: dict, creator_id: int) -> tuple[dict | None, str | None]:
        """
        Creates a new quotation with line items and automatic pricing/tax calculations.
        """
        customer_id = data.get("customer_id")
        if not customer_id:
            return None, "Customer ID is required"

        customer = db.session.get(User, customer_id)
        if not customer or not customer.is_active:
            return None, "Selected customer is invalid or inactive"

        plan_id = data.get("plan_id")
        plan = None
        if plan_id:
            plan = db.session.get(SubscriptionPlan, plan_id)
            if not plan:
                return None, "Selected subscription plan does not exist"
            if not plan.is_available:
                return None, f"Plan '{plan.name}' is inactive or outside its availability window"

        # Validity date (default: 30 days)
        valid_until = None
        if data.get("valid_until"):
            try:
                valid_until = datetime.strptime(data["valid_until"], "%Y-%m-%d").date()
                if valid_until < date.today():
                    return None, "Quotation validity date cannot be in the past"
            except ValueError:
                return None, "Invalid validity date format (expected YYYY-MM-DD)"
        else:
            valid_until = date.today() + timedelta(days=30)

        items_data = data.get("items", [])
        if not items_data:
            return None, "At least one product line item is required"

        # Process and calculate line items
        line_items_to_add = []
        subtotal = Decimal("0.00")
        total_tax = Decimal("0.00")
        total_qty = 0

        for item_data in items_data:
            p_id = item_data.get("product_id")
            v_id = item_data.get("variant_id") or None
            try:
                qty = int(item_data.get("quantity", 1))
                if qty < 1:
                    return None, "Item quantity must be at least 1"
            except Exception:
                return None, "Invalid quantity for item"

            # Check effective price
            unit_price, tax_rate, err = ProductService.calculate_effective_price(p_id, v_id)
            if err:
                return None, err

            # Override unit price if custom unit_price allowed (e.g. negotiated price)
            if "unit_price" in item_data and item_data["unit_price"] is not None:
                try:
                    custom_up = Decimal(str(item_data["unit_price"]))
                    if custom_up < 0:
                        return None, "Unit price cannot be negative"
                    unit_price = custom_up
                except Exception:
                    return None, "Unit price must be a valid number"

            # Custom tax rate if provided
            if "tax_rate" in item_data and item_data["tax_rate"] is not None:
                try:
                    custom_tr = Decimal(str(item_data["tax_rate"]))
                    if custom_tr < 0:
                        return None, "Tax rate cannot be negative"
                    tax_rate = custom_tr
                except Exception:
                    return None, "Tax rate must be a valid number"

            line_base = unit_price * Decimal(str(qty))
            line_tax = (line_base * tax_rate / Decimal("100.00")).quantize(Decimal("0.01"))
            line_total = line_base + line_tax

            subtotal += line_base
            total_tax += line_tax
            total_qty += qty

            line_items_to_add.append({
                "product_id": p_id,
                "variant_id": v_id,
                "quantity": qty,
                "unit_price": unit_price,
                "tax_rate": tax_rate,
                "tax_amount": line_tax,
                "total_price": line_total,
            })

        # Validate minimum quantity from plan if applicable
        if plan and total_qty < plan.minimum_quantity:
            return None, f"Total quantity ({total_qty}) does not meet plan '{plan.name}' minimum required quantity ({plan.minimum_quantity})"

        total_amount = subtotal + total_tax
        is_template = bool(data.get("is_template", False))
        template_name = (data.get("template_name") or "").strip() or None

        quotation = Quotation(
            quotation_number=cls.generate_quotation_number(),
            customer_id=customer.id,
            creator_id=creator_id,
            plan_id=plan.id if plan else None,
            status="draft",
            valid_until=valid_until,
            subtotal=subtotal,
            tax_rate=Decimal("18.00"),
            tax_amount=total_tax,
            total_amount=total_amount,
            is_template=is_template,
            template_name=template_name,
            terms_conditions=(data.get("terms_conditions") or "").strip() or None,
            notes=(data.get("notes") or "").strip() or None,
        )
        db.session.add(quotation)
        db.session.flush()

        for item_dict in line_items_to_add:
            item = QuotationItem(
                quotation_id=quotation.id,
                product_id=item_dict["product_id"],
                variant_id=item_dict["variant_id"],
                quantity=item_dict["quantity"],
                unit_price=item_dict["unit_price"],
                tax_rate=item_dict["tax_rate"],
                tax_amount=item_dict["tax_amount"],
                total_price=item_dict["total_price"],
            )
            db.session.add(item)

        db.session.commit()
        return quotation.to_dict(include_items=True), None

    @classmethod
    def update_quotation(cls, quotation_id: int, data: dict, user_id: int, user_role: str) -> tuple[dict | None, str | None]:
        """
        Updates an existing draft quotation.
        Rule: Prevent editing finalized quotations (confirmed, rejected, expired).
        """
        quotation = db.session.get(Quotation, quotation_id)
        if not quotation:
            return None, "Quotation not found"

        # Prevent editing finalized quotations
        if quotation.status in ["confirmed", "rejected", "expired"]:
            return None, f"Cannot edit quotation in '{quotation.status}' status. Only draft quotations can be modified."

        # Permission check: customer can only edit their own draft quotation if authorized
        if user_role == "customer" and quotation.customer_id != user_id:
            return None, "Unauthorized access to quotation"

        if "valid_until" in data and data["valid_until"]:
            try:
                vu = datetime.strptime(data["valid_until"], "%Y-%m-%d").date()
                if vu < date.today():
                    return None, "Quotation validity date cannot be in the past"
                quotation.valid_until = vu
            except ValueError:
                return None, "Invalid validity date format (YYYY-MM-DD)"

        if "plan_id" in data:
            if data["plan_id"]:
                plan = SubscriptionPlan.query.get(data["plan_id"])
                if not plan or not plan.is_available:
                    return None, "Selected plan is inactive or unavailable"
                quotation.plan_id = plan.id
            else:
                quotation.plan_id = None

        if "terms_conditions" in data:
            quotation.terms_conditions = data["terms_conditions"].strip() or None

        if "notes" in data:
            quotation.notes = data["notes"].strip() or None

        # If items are updated, recalculate totals
        if "items" in data and data["items"]:
            QuotationItem.query.filter_by(quotation_id=quotation.id).delete()
            subtotal = Decimal("0.00")
            total_tax = Decimal("0.00")
            total_qty = 0

            for item_data in data["items"]:
                p_id = item_data.get("product_id")
                v_id = item_data.get("variant_id") or None
                qty = max(1, int(item_data.get("quantity", 1)))

                unit_price, tax_rate, err = ProductService.calculate_effective_price(p_id, v_id)
                if err:
                    db.session.rollback()
                    return None, err

                if "unit_price" in item_data and item_data["unit_price"] is not None:
                    unit_price = Decimal(str(item_data["unit_price"]))
                if "tax_rate" in item_data and item_data["tax_rate"] is not None:
                    tax_rate = Decimal(str(item_data["tax_rate"]))

                line_base = unit_price * Decimal(str(qty))
                line_tax = (line_base * tax_rate / Decimal("100.00")).quantize(Decimal("0.01"))
                line_total = line_base + line_tax

                subtotal += line_base
                total_tax += line_tax
                total_qty += qty

                item = QuotationItem(
                    quotation_id=quotation.id,
                    product_id=p_id,
                    variant_id=v_id,
                    quantity=qty,
                    unit_price=unit_price,
                    tax_rate=tax_rate,
                    tax_amount=line_tax,
                    total_price=line_total,
                )
                db.session.add(item)

            if quotation.plan and total_qty < quotation.plan.minimum_quantity:
                db.session.rollback()
                return None, f"Total quantity ({total_qty}) does not meet plan '{quotation.plan.name}' minimum required quantity ({quotation.plan.minimum_quantity})"

            quotation.subtotal = subtotal
            quotation.tax_amount = total_tax
            quotation.total_amount = subtotal + total_tax

        db.session.commit()
        return quotation.to_dict(include_items=True), None

    @classmethod
    def transition_status(cls, quotation_id: int, target_status: str, user_id: int, user_role: str) -> tuple[dict | None, str | None]:
        """
        Executes quotation status transitions:
        - 'sent': draft -> sent
        - 'confirmed': sent/draft/quotation -> confirmed
        - 'rejected': sent/draft/quotation -> rejected
        """
        quotation = db.session.get(Quotation, quotation_id)
        if not quotation:
            return None, "Quotation not found"

        # Check customer IDOR
        if user_role == "customer" and quotation.customer_id != user_id:
            return None, "Unauthorized access to quotation"

        # Check expiration
        if quotation.is_expired:
            quotation.status = "expired"
            db.session.commit()
            return None, "Quotation has expired and cannot be transitioned"

        if quotation.status in ["confirmed", "rejected", "expired"]:
            return None, f"Quotation is already '{quotation.status}' and cannot change status"

        if target_status == "sent":
            if quotation.status != "draft":
                return None, f"Only draft quotations can be marked as sent (currently: {quotation.status})"
            quotation.status = "sent"

        elif target_status in ["confirmed", "quotation"]:
            quotation.status = "confirmed"

        elif target_status == "rejected":
            quotation.status = "rejected"

        else:
            return None, f"Invalid target status: '{target_status}'"

        db.session.commit()
        return quotation.to_dict(include_items=True), None

    @classmethod
    def save_as_template(cls, quotation_id: int, template_name: str) -> tuple[dict | None, str | None]:
        """Clones an existing quotation into a reusable template."""
        source = db.session.get(Quotation, quotation_id)
        if not source:
            return None, "Source quotation not found"

        if not template_name or not template_name.strip():
            return None, "Template name is required"

        template = Quotation(
            quotation_number=cls.generate_quotation_number(),
            customer_id=source.customer_id,
            creator_id=source.creator_id,
            plan_id=source.plan_id,
            status="draft",
            valid_until=date.today() + timedelta(days=365),
            subtotal=source.subtotal,
            tax_rate=source.tax_rate,
            tax_amount=source.tax_amount,
            total_amount=source.total_amount,
            is_template=True,
            template_name=template_name.strip(),
            terms_conditions=source.terms_conditions,
            notes=source.notes,
        )
        db.session.add(template)
        db.session.flush()

        for it in source.items.all():
            item = QuotationItem(
                quotation_id=template.id,
                product_id=it.product_id,
                variant_id=it.variant_id,
                quantity=it.quantity,
                unit_price=it.unit_price,
                tax_rate=it.tax_rate,
                tax_amount=it.tax_amount,
                total_price=it.total_price,
            )
            db.session.add(item)

        db.session.commit()
        return template.to_dict(include_items=True), None

