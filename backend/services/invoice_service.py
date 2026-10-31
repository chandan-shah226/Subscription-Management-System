"""
Invoice Management Service
==========================
Handles automated invoice generation from recurring subscriptions, manual invoicing,
tax calculation, status lifecycles, and duplicate billing prevention.
"""

from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from models import db
from models.user import User
from models.product import Product
from models.subscription import Subscription, SubscriptionItem
from models.invoice import Invoice, InvoiceItem
from models.discount import Discount


class InvoiceService:
    """Service governing invoicing workflows, recurring billing day automation, and lifecycle states."""

    @staticmethod
    def generate_invoice_number() -> str:
        """Generates sequential, unique invoice numbers formatted as INV-YYYY-XXXX."""
        year = datetime.now(timezone.utc).year
        prefix = f"INV-{year}-"
        last_inv = Invoice.query.filter(Invoice.invoice_number.like(f"{prefix}%")).order_by(Invoice.id.desc()).first()
        if last_inv and last_inv.invoice_number:
            try:
                seq = int(last_inv.invoice_number.split("-")[-1]) + 1
            except ValueError:
                seq = 1
        else:
            seq = 1
        return f"{prefix}{seq:04d}"

    @classmethod
    def list_invoices(cls, customer_id: int | None = None, status_filter: str | None = None, search: str | None = None):
        """Lists invoices with optional customer, status, or search filters."""
        query = Invoice.query

        if customer_id:
            query = query.filter_by(customer_id=customer_id)

        today = date.today()
        if status_filter:
            sf = status_filter.lower()
            if sf == "overdue":
                query = query.filter(Invoice.status != "paid", Invoice.status != "cancelled", Invoice.due_date < today)
            else:
                query = query.filter_by(status=sf)

        if search:
            like = f"%{search.strip()}%"
            query = query.filter(
                (Invoice.invoice_number.ilike(like)) |
                (Invoice.customer.has(User.first_name.ilike(like))) |
                (Invoice.customer.has(User.last_name.ilike(like))) |
                (Invoice.customer.has(User.email.ilike(like)))
            )

        invoices = query.order_by(Invoice.id.desc()).all()
        return [inv.to_dict(include_items=True, include_payments=True) for inv in invoices]

    @classmethod
    def get_invoice_by_id(cls, invoice_id: int):
        """Retrieves single invoice with line items and payment transactions."""
        inv = db.session.get(Invoice, invoice_id)
        if not inv:
            return None
        return inv.to_dict(include_items=True, include_payments=True)

    @classmethod
    def create_invoice_from_subscription(cls, subscription_id: int, due_days: int = 15, discount_code: str | None = None) -> tuple[dict | None, str | None]:
        """
        Automates billing day generation: creates an invoice from an active subscription.
        Guarantees that nothing is billed twice for the same billing date.
        """
        sub = db.session.get(Subscription, subscription_id)
        if not sub:
            return None, "Subscription not found"

        if sub.status != "active":
            return None, f"Cannot generate invoice: subscription is in '{sub.status}' status (must be active)"

        today = date.today()

        # Prevent duplicate billing: check if an invoice was already created for this subscription on the same billing date
        existing = Invoice.query.filter(
            Invoice.subscription_id == sub.id,
            Invoice.status != "cancelled",
            Invoice.invoice_date == today
        ).first()
        if existing:
            return None, f"Duplicate billing prevented: Invoice {existing.invoice_number} already generated today for this subscription"

        subtotal = Decimal("0.00")
        tax_total = Decimal("0.00")
        items_to_create = []

        sub_items = sub.items.all()
        if not sub_items:
            # Fallback if subscription only has plan base price
            unit_price = Decimal(str(sub.total_amount))
            tax_rate = Decimal("18.00")
            item_tax = round(unit_price * (tax_rate / Decimal("100.00")), 2)
            subtotal = unit_price
            tax_total = item_tax
            items_to_create.append({
                "description": f"Subscription: {sub.plan.name if sub.plan else 'Plan'}",
                "quantity": 1,
                "unit_price": unit_price,
                "tax_rate": tax_rate,
                "total_price": unit_price + item_tax
            })
        else:
            for item in sub_items:
                qty = item.quantity
                unit_p = Decimal(str(item.unit_price))
                tax_r = Decimal(str(item.tax_rate))
                line_sub = unit_p * qty
                line_tax = round(line_sub * (tax_r / Decimal("100.00")), 2)
                subtotal += line_sub
                tax_total += line_tax
                desc = item.product.name if item.product else f"Service Item #{item.id}"
                if item.variant:
                    desc += f" ({item.variant.variant_name})"
                items_to_create.append({
                    "product_id": item.product_id,
                    "variant_id": item.variant_id,
                    "description": desc,
                    "quantity": qty,
                    "unit_price": unit_p,
                    "tax_rate": tax_r,
                    "total_price": line_sub + line_tax
                })

        # Apply Discount if provided
        discount_amount = Decimal("0.00")
        applied_code = None
        if discount_code:
            disc = Discount.query.filter_by(code=discount_code.strip().upper(), is_active=True).first()
            if disc:
                valid, msg = disc.is_valid_now(amount=subtotal)
                if valid:
                    discount_amount = disc.calculate_discount(subtotal)
                    applied_code = disc.code
                    disc.used_count += 1

        gross_total = subtotal + tax_total
        total_amount = max(Decimal("0.00"), gross_total - discount_amount)

        due_date = today + timedelta(days=due_days)

        invoice = Invoice(
            invoice_number=cls.generate_invoice_number(),
            subscription_id=sub.id,
            customer_id=sub.customer_id,
            invoice_date=today,
            due_date=due_date,
            status="confirmed",  # Recurring billing automatically confirms and readies invoice
            subtotal=subtotal,
            tax_amount=tax_total,
            discount_amount=discount_amount,
            total_amount=total_amount,
            amount=total_amount,
            discount_code=applied_code,
            notes=f"Automated recurring billing generated for {sub.subscription_number} ({sub.billing_frequency.capitalize()})"
        )
        db.session.add(invoice)
        db.session.flush()

        for it in items_to_create:
            inv_item = InvoiceItem(
                invoice_id=invoice.id,
                product_id=it.get("product_id"),
                variant_id=it.get("variant_id"),
                description=it["description"],
                quantity=it["quantity"],
                unit_price=it["unit_price"],
                tax_rate=it["tax_rate"],
                total_price=it["total_price"]
            )
            db.session.add(inv_item)

        # Advance subscription next_billing_date
        from services.subscription_service import SubscriptionService
        sub.next_billing_date = SubscriptionService.calculate_next_billing_date(sub.next_billing_date, sub.billing_frequency)
        sub.renews_on = sub.next_billing_date

        db.session.commit()
        return invoice.to_dict(include_items=True), None

    @classmethod
    def generate_all_due_invoices(cls) -> tuple[list[dict], int]:
        """Billing Day automated cron: generates invoices for all active subscriptions due today."""
        today = date.today()
        due_subs = Subscription.query.filter(
            Subscription.status == "active",
            Subscription.next_billing_date <= today
        ).all()

        generated = []
        for s in due_subs:
            inv_dict, err = cls.create_invoice_from_subscription(s.id)
            if inv_dict:
                generated.append(inv_dict)

        return generated, len(due_subs)

    @classmethod
    def confirm_invoice(cls, invoice_id: int) -> tuple[dict | None, str | None]:
        """Transitions a draft invoice to confirmed."""
        inv = db.session.get(Invoice, invoice_id)
        if not inv:
            return None, "Invoice not found"
        if inv.status != "draft":
            return None, f"Cannot confirm invoice in '{inv.status}' status"
        inv.status = "confirmed"
        db.session.commit()
        return inv.to_dict(include_items=True), None

    @classmethod
    def cancel_invoice(cls, invoice_id: int) -> tuple[dict | None, str | None]:
        """Cancels an invoice if not already paid."""
        inv = db.session.get(Invoice, invoice_id)
        if not inv:
            return None, "Invoice not found"
        if inv.status == "paid":
            return None, "Cannot cancel an already paid invoice"
        inv.status = "cancelled"
        db.session.commit()
        return inv.to_dict(include_items=True), None
