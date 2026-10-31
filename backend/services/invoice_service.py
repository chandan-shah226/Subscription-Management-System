"""
Invoice Business Logic & Services
=================================
Module 4: Invoicing and Recurring Billing Service Layer.
Implements:
1. Precise financial calculations (subtotal, line items, discounts, taxes, final total).
2. Unique, sequential invoice numbering (INV-YYYY-XXXX).
3. Status workflow validation (Draft -> Confirmed -> Paid / Cancelled).
4. Subscription recurring billing engine with strict duplicate prevention and period advancement.
5. Payment recording with outstanding balance synchronization.
6. Metric aggregations for dashboard summary cards.
"""

from datetime import date, datetime, timezone, timedelta
import calendar
from decimal import Decimal, ROUND_HALF_UP

from models import (
    db, Invoice, InvoiceItem, Payment, Subscription, SubscriptionItem,
    SubscriptionAuditLog, User, Discount, Product, SubscriptionPlan
)


def quantize_money(amount):
    """Ensures monetary values are strictly quantized to 2 decimal places."""
    if amount is None:
        return Decimal("0.00")
    if not isinstance(amount, Decimal):
        try:
            amount = Decimal(str(amount))
        except Exception:
            return Decimal("0.00")
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def generate_unique_invoice_number():
    """
    Generates a unique, sequential invoice number.
    Format: INV-YYYY-XXXX (e.g., INV-2026-0001)
    """
    current_year = date.today().year
    prefix = f"INV-{current_year}-"

    last_invoice = (
        Invoice.query.filter(Invoice.invoice_number.like(f"{prefix}%"))
        .order_by(Invoice.id.desc())
        .first()
    )

    if last_invoice and last_invoice.invoice_number:
        try:
            seq_part = last_invoice.invoice_number.split("-")[-1]
            next_seq = int(seq_part) + 1
        except (ValueError, IndexError):
            next_seq = Invoice.query.count() + 1
    else:
        next_seq = 1

    candidate = f"{prefix}{next_seq:04d}"

    while Invoice.query.filter_by(invoice_number=candidate).first() is not None:
        next_seq += 1
        candidate = f"{prefix}{next_seq:04d}"

    return candidate


def calculate_line_item(item_data, default_tax_rate=Decimal("0.00")):
    """
    Computes individual line item figures:
    - line_subtotal = quantity * unit_price
    - taxable_amount = max(0, line_subtotal - discount_amount)
    - tax_amount = taxable_amount * (tax_rate / 100)
    - line_total = taxable_amount + tax_amount
    """
    qty = quantize_money(item_data.get("quantity", 1))
    price = quantize_money(item_data.get("unit_price", 0))
    line_subtotal = quantize_money(qty * price)

    discount = quantize_money(item_data.get("discount_amount", 0))
    if discount > line_subtotal:
        discount = line_subtotal

    tax_rate = quantize_money(item_data.get("tax_rate", default_tax_rate))
    taxable_amount = quantize_money(line_subtotal - discount)
    tax_amount = quantize_money(taxable_amount * (tax_rate / Decimal("100.00")))
    line_total = quantize_money(taxable_amount + tax_amount)

    return {
        "description": item_data.get("description", "Invoice Item").strip(),
        "product_id": item_data.get("product_id"),
        "variant_id": item_data.get("variant_id"),
        "quantity": qty,
        "unit_price": price,
        "discount_amount": discount,
        "tax_rate": tax_rate,
        "tax_amount": tax_amount,
        "total_amount": line_total,
        "subtotal": line_subtotal
    }


def compute_invoice_totals(line_items_data, overall_discount=Decimal("0.00"), discount_code=None, discount_id=None):
    """
    Computes full invoice financials:
    1. Subtotal = sum of line subtotals
    2. Discount = sum of line discounts + eligible overall discount
    3. Tax = sum of line taxes
    4. Total Amount = max(0, Subtotal - Discount) + Tax
    """
    subtotal = Decimal("0.00")
    total_tax = Decimal("0.00")
    total_line_discounts = Decimal("0.00")
    processed_items = []

    for item in line_items_data:
        processed = calculate_line_item(item)
        processed_items.append(processed)
        subtotal += processed["subtotal"]
        total_tax += processed["tax_amount"]
        total_line_discounts += processed["discount_amount"]

    subtotal = quantize_money(subtotal)
    total_tax = quantize_money(total_tax)
    total_line_discounts = quantize_money(total_line_discounts)

    overall_disc = quantize_money(overall_discount)
    matched_discount = None

    if discount_id:
        matched_discount = db.session.get(Discount, discount_id)
    elif discount_code:
        matched_discount = Discount.query.filter_by(code=discount_code.strip().upper(), is_active=True).first()

    if matched_discount:
        is_valid, _ = matched_discount.is_eligible(subtotal)
        if is_valid:
            overall_disc = matched_discount.calculate_discount_amount(subtotal)

    total_discount = quantize_money(total_line_discounts + overall_disc)
    if total_discount > subtotal:
        total_discount = subtotal

    taxable_amount = quantize_money(max(Decimal("0.00"), subtotal - total_discount))
    total_amount = quantize_money(taxable_amount + total_tax)

    return {
        "subtotal": subtotal,
        "discount_id": matched_discount.id if matched_discount else None,
        "discount_code": matched_discount.code if matched_discount else discount_code,
        "discount_amount": total_discount,
        "tax_amount": total_tax,
        "total_amount": total_amount,
        "items": processed_items
    }


def calculate_next_billing_date(current_date, frequency):
    """
    Calculates next billing date based on frequency:
    daily, weekly, monthly, quarterly, yearly
    """
    freq = (frequency or "monthly").lower().strip()
    if freq == "daily":
        return current_date + timedelta(days=1)
    elif freq == "weekly":
        return current_date + timedelta(weeks=1)
    elif freq == "monthly":
        year = current_date.year + (current_date.month // 12)
        month = (current_date.month % 12) + 1
        day = min(current_date.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)
    elif freq == "quarterly":
        month = current_date.month + 3
        year = current_date.year + ((month - 1) // 12)
        month = ((month - 1) % 12) + 1
        day = min(current_date.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)
    elif freq == "yearly":
        try:
            return date(current_date.year + 1, current_date.month, current_date.day)
        except ValueError:
            return date(current_date.year + 1, current_date.month, 28)
    return current_date + timedelta(days=30)


def create_invoice(data, creator=None):
    """Creates a new Draft invoice with validated line items and computed financials."""
    customer_id = data.get("customer_id")
    if not customer_id:
        raise ValueError("Customer ID is required")

    customer = db.session.get(User, customer_id)
    if not customer:
        raise ValueError(f"Customer with ID {customer_id} does not exist")

    # Subscription owner validation
    sub_id = data.get("subscription_id")
    if sub_id:
        sub = db.session.get(Subscription, sub_id)
        if sub and sub.customer_id != customer_id:
            raise ValueError(f"Subscription {sub.subscription_number} does not belong to customer {customer_id}")

    inv_date_str = data.get("invoice_date")
    due_date_str = data.get("due_date")

    try:
        inv_date = date.fromisoformat(inv_date_str) if inv_date_str else date.today()
        due_date = date.fromisoformat(due_date_str) if due_date_str else inv_date + timedelta(days=15)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid date format: {str(e)}")

    if due_date < inv_date:
        raise ValueError("Due date cannot precede invoice date")

    items_data = data.get("items", [])
    if not items_data:
        raise ValueError("Must provide at least one line item")

    overall_discount = data.get("discount_amount", 0)
    discount_code = data.get("discount_code")
    discount_id = data.get("discount_id")
    financials = compute_invoice_totals(items_data, overall_discount, discount_code=discount_code, discount_id=discount_id)

    invoice_number = data.get("invoice_number") or generate_unique_invoice_number()

    invoice = Invoice(
        invoice_number=invoice_number,
        customer_id=customer_id,
        subscription_id=sub_id,
        billing_period_start=date.fromisoformat(data["billing_period_start"]) if data.get("billing_period_start") else None,
        billing_period_end=date.fromisoformat(data["billing_period_end"]) if data.get("billing_period_end") else None,
        invoice_date=inv_date,
        due_date=due_date,
        subtotal=financials["subtotal"],
        discount_id=financials["discount_id"],
        discount_code=financials["discount_code"],
        discount_amount=financials["discount_amount"],
        tax_amount=financials["tax_amount"],
        total_amount=financials["total_amount"],
        amount_paid=Decimal("0.00"),
        outstanding_amount=financials["total_amount"],
        status="Draft",
        notes=data.get("notes", "").strip()
    )

    db.session.add(invoice)
    db.session.flush()

    for item_info in financials["items"]:
        item = InvoiceItem(
            invoice_id=invoice.id,
            product_id=item_info["product_id"],
            variant_id=item_info.get("variant_id"),
            description=item_info["description"],
            quantity=item_info["quantity"],
            unit_price=item_info["unit_price"],
            discount_amount=item_info["discount_amount"],
            tax_rate=item_info["tax_rate"],
            tax_amount=item_info["tax_amount"],
            total_amount=item_info["total_amount"]
        )
        db.session.add(item)

    db.session.commit()
    return invoice


def update_invoice(invoice_id, data, user=None):
    """Updates an invoice. Only permitted when invoice is in 'Draft' status."""
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice:
        raise ValueError("Invoice not found")

    if invoice.status != "Draft":
        raise ValueError(f"Only Draft invoices may be modified. Current status is '{invoice.status}'")

    if "due_date" in data and data["due_date"]:
        try:
            new_due_date = date.fromisoformat(data["due_date"])
            if new_due_date < invoice.invoice_date:
                raise ValueError("Due date cannot precede invoice date")
            invoice.due_date = new_due_date
        except ValueError as e:
            raise ValueError(f"Invalid due_date: {str(e)}")

    if "notes" in data:
        invoice.notes = data["notes"].strip()

    if "items" in data and data["items"]:
        items_data = data["items"]
        overall_discount = data.get("discount_amount", invoice.discount_amount)
        discount_code = data.get("discount_code", invoice.discount_code)
        discount_id = data.get("discount_id", invoice.discount_id)
        financials = compute_invoice_totals(items_data, overall_discount, discount_code=discount_code, discount_id=discount_id)

        invoice.subtotal = financials["subtotal"]
        invoice.discount_id = financials["discount_id"]
        invoice.discount_code = financials["discount_code"]
        invoice.discount_amount = financials["discount_amount"]
        invoice.tax_amount = financials["tax_amount"]
        invoice.total_amount = financials["total_amount"]
        invoice.outstanding_amount = max(Decimal("0.00"), financials["total_amount"] - invoice.amount_paid)

        # Replace existing line items
        InvoiceItem.query.filter_by(invoice_id=invoice.id).delete()
        for item_info in financials["items"]:
            item = InvoiceItem(
                invoice_id=invoice.id,
                product_id=item_info["product_id"],
                variant_id=item_info.get("variant_id"),
                description=item_info["description"],
                quantity=item_info["quantity"],
                unit_price=item_info["unit_price"],
                discount_amount=item_info["discount_amount"],
                tax_rate=item_info["tax_rate"],
                tax_amount=item_info["tax_amount"],
                total_amount=item_info["total_amount"]
            )
            db.session.add(item)

    invoice.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return invoice


def confirm_invoice(invoice_id, user=None):
    """Transitions invoice from 'Draft' to 'Confirmed'."""
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice:
        raise ValueError("Invoice not found")

    if invoice.status != "Draft":
        raise ValueError(f"Cannot confirm an invoice with status '{invoice.status}'")

    if invoice.items.count() == 0:
        raise ValueError("Cannot confirm an invoice with no line items")

    # Record discount redemption if an active discount is applied
    if invoice.discount_id and invoice.discount_amount and invoice.discount_amount > Decimal("0.00"):
        from services.discount_service import record_discount_redemption
        record_discount_redemption(
            discount_id=invoice.discount_id,
            invoice_id=invoice.id,
            customer_id=invoice.customer_id,
            amount=invoice.discount_amount
        )

    invoice.status = "Confirmed"
    invoice.outstanding_amount = max(Decimal("0.00"), invoice.total_amount - invoice.amount_paid)
    invoice.updated_at = datetime.now(timezone.utc)

    db.session.commit()
    return invoice


def cancel_invoice(invoice_id, reason=None, user=None):
    """Cancels an invoice. Paid invoices cannot be cancelled without refund."""
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice:
        raise ValueError("Invoice not found")

    if invoice.status == "Paid" or (invoice.amount_paid and invoice.amount_paid > Decimal("0.00")):
        raise ValueError("Cannot cancel invoice after payments have been recorded")

    if invoice.status == "Cancelled":
        raise ValueError("Invoice is already cancelled")

    # Revert any discount redemption tied to this invoice
    from services.discount_service import revert_discount_redemption
    revert_discount_redemption(invoice.id)

    invoice.status = "Cancelled"
    invoice.outstanding_amount = Decimal("0.00")
    if reason:
        invoice.notes = f"{invoice.notes or ''}\n[Cancelled]: {reason}".strip()

    invoice.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return invoice


def record_payment(invoice_id, payment_data, user=None):
    """
    Records a payment against an invoice and updates outstanding amount.
    Transitions status to 'Paid' if outstanding becomes zero.
    """
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice:
        raise ValueError("Invoice not found")

    if invoice.status == "Cancelled":
        raise ValueError("Cannot record payment on a cancelled invoice")

    if invoice.status == "Draft":
        raise ValueError("Cannot record payment on a Draft invoice. Invoice must be Confirmed.")

    if invoice.status == "Paid" and invoice.outstanding_amount <= Decimal("0.00"):
        raise ValueError("Invoice is already fully paid")

    amount_raw = payment_data.get("amount")
    if not amount_raw:
        raise ValueError("Payment amount is required")

    try:
        pay_amount = quantize_money(amount_raw)
    except Exception:
        raise ValueError("Invalid payment amount format")

    if pay_amount <= Decimal("0.00"):
        raise ValueError("Payment amount must be greater than zero")

    if pay_amount > invoice.outstanding_amount:
        raise ValueError(f"Payment amount (₹{pay_amount}) cannot exceed outstanding amount (₹{invoice.outstanding_amount})")

    pay_date_str = payment_data.get("payment_date")
    pay_date = date.fromisoformat(pay_date_str) if pay_date_str else date.today()

    payment = Payment(
        invoice_id=invoice.id,
        amount=pay_amount,
        payment_method=payment_data.get("payment_method", "Bank Transfer"),
        payment_date=pay_date,
        reference_number=payment_data.get("reference_number", "").strip(),
        notes=payment_data.get("notes", "").strip(),
        created_by_id=user.id if user else None
    )
    db.session.add(payment)

    # Synchronize financial totals on invoice
    invoice.amount_paid = quantize_money(invoice.amount_paid + pay_amount)
    invoice.outstanding_amount = quantize_money(max(Decimal("0.00"), invoice.total_amount - invoice.amount_paid))

    if invoice.outstanding_amount <= Decimal("0.00"):
        invoice.status = "Paid"

    invoice.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return payment, invoice


def generate_subscription_invoices(target_date=None):
    """
    Subscription recurring billing engine:
    1. Finds active subscriptions where next_billing_date <= target_date.
    2. Strict duplicate prevention: checks for existing invoice for subscription and period.
    3. Builds line items from Subscription items or plan.
    4. Creates Draft/Confirmed invoice.
    5. Advances subscription.next_billing_date.
    6. Logs audit trail.
    """
    if target_date is None:
        target_date = date.today()
    elif isinstance(target_date, str):
        target_date = date.fromisoformat(target_date)

    due_subscriptions = Subscription.query.filter(
        db.or_(Subscription.status == "active", Subscription.status == "Active"),
        Subscription.next_billing_date != None,
        Subscription.next_billing_date <= target_date
    ).all()

    generated_invoices = []
    skipped_count = 0
    errors = []

    for sub in due_subscriptions:
        try:
            billing_period_start = sub.start_date
            billing_period_end = sub.next_billing_date

            # Duplicate Prevention: Check if invoice already exists for this sub & period
            existing = Invoice.query.filter(
                Invoice.subscription_id == sub.id,
                Invoice.billing_period_end == billing_period_end,
                Invoice.status != "Cancelled"
            ).first()

            if existing:
                skipped_count += 1
                continue

            # Build line items
            line_items_data = []
            sub_items = sub.items.all() if hasattr(sub.items, "all") else list(sub.items)
            if sub_items:
                for item in sub_items:
                    prod_name = item.product.name if item.product else "Subscription Item"
                    if getattr(item, "variant", None):
                        prod_name += f" ({item.variant.variant_name})"
                    line_items_data.append({
                        "product_id": item.product_id,
                        "variant_id": getattr(item, "variant_id", None),
                        "description": prod_name,
                        "quantity": item.quantity,
                        "unit_price": item.unit_price,
                        "tax_rate": getattr(item, "tax_rate", Decimal("18.00")),
                        "discount_amount": Decimal("0.00")
                    })
            elif sub.plan:
                line_items_data.append({
                    "product_id": None,
                    "variant_id": None,
                    "description": f"Subscription Plan: {sub.plan.name} ({sub.billing_frequency.capitalize()})",
                    "quantity": Decimal("1.00"),
                    "unit_price": getattr(sub.plan, "base_price", Decimal("0.00")),
                    "tax_rate": Decimal("18.00"),
                    "discount_amount": Decimal("0.00")
                })
            else:
                line_items_data.append({
                    "product_id": None,
                    "variant_id": None,
                    "description": f"Subscription {sub.subscription_number} recurring service",
                    "quantity": Decimal("1.00"),
                    "unit_price": Decimal("100.00"),
                    "tax_rate": Decimal("18.00"),
                    "discount_amount": Decimal("0.00")
                })

            # Calculate raw subtotal and find eligible discounts for subscription
            raw_subtotal = sum([item["quantity"] * item["unit_price"] for item in line_items_data])
            total_qty = sum([item["quantity"] for item in line_items_data])
            product_ids = [item["product_id"] for item in line_items_data if item.get("product_id")]

            from services.discount_service import select_best_discount
            best_discount, best_benefit = select_best_discount(
                subtotal=raw_subtotal,
                quantity=total_qty,
                product_ids=product_ids,
                check_date=billing_period_end,
                is_subscription=True
            )

            disc_code = best_discount.code if best_discount else None
            disc_id = best_discount.id if best_discount else None
            financials = compute_invoice_totals(line_items_data, discount_code=disc_code, discount_id=disc_id)

            inv_date = billing_period_end
            due_date = inv_date + timedelta(days=15)

            note_disc = f" (Includes automatic discount {best_discount.code})" if best_discount else ""
            invoice = Invoice(
                invoice_number=generate_unique_invoice_number(),
                customer_id=sub.customer_id,
                subscription_id=sub.id,
                billing_period_start=billing_period_start,
                billing_period_end=billing_period_end,
                invoice_date=inv_date,
                due_date=due_date,
                subtotal=financials["subtotal"],
                discount_id=financials["discount_id"],
                discount_code=financials["discount_code"],
                discount_amount=financials["discount_amount"],
                tax_amount=financials["tax_amount"],
                total_amount=financials["total_amount"],
                amount_paid=Decimal("0.00"),
                outstanding_amount=financials["total_amount"],
                status="Draft",
                notes=f"Automatically generated on billing day for Subscription {sub.subscription_number} ({sub.billing_frequency}).{note_disc}"
            )

            db.session.add(invoice)
            db.session.flush()

            for item_info in financials["items"]:
                item = InvoiceItem(
                    invoice_id=invoice.id,
                    product_id=item_info["product_id"],
                    variant_id=item_info.get("variant_id"),
                    description=item_info["description"],
                    quantity=item_info["quantity"],
                    unit_price=item_info["unit_price"],
                    discount_amount=item_info["discount_amount"],
                    tax_rate=item_info["tax_rate"],
                    tax_amount=item_info["tax_amount"],
                    total_amount=item_info["total_amount"]
                )
                db.session.add(item)

            # Advance subscription schedule
            sub.next_billing_date = calculate_next_billing_date(billing_period_end, sub.billing_frequency)
            sub.updated_at = datetime.now(timezone.utc)

            # Record audit log
            audit = SubscriptionAuditLog(
                subscription_id=sub.id,
                action="invoice_generated",
                performed_by_id=sub.customer_id,
                details=f"Recurring invoice {invoice.invoice_number} generated for period ending {billing_period_end}."
            )
            db.session.add(audit)

            db.session.commit()
            generated_invoices.append(invoice)

        except Exception as e:
            db.session.rollback()
            errors.append(f"Subscription {sub.subscription_number}: {str(e)}")

    return {
        "generated_count": len(generated_invoices),
        "skipped_count": skipped_count,
        "invoices": [inv.to_dict(include_items=False, include_payments=False) for inv in generated_invoices],
        "errors": errors
    }


def get_invoice_statistics(customer_id=None):
    """
    Computes real-time accurate statistics for Dashboard KPI summary cards.
    Supports both flat structure and nested structure for compatibility.
    """
    base_query = Invoice.query
    if customer_id:
        base_query = base_query.filter(Invoice.customer_id == customer_id)

    invoices = base_query.all()
    today = date.today()

    draft_count = 0
    draft_amount = 0.0
    confirmed_count = 0
    confirmed_amount = 0.0
    paid_count = 0
    paid_amount = 0.0
    overdue_count = 0
    overdue_amount = 0.0
    total_amount = 0.0
    total_outstanding = 0.0
    total_collected = 0.0

    for inv in invoices:
        tot = float(inv.total_amount or 0.0)
        out = float(inv.outstanding_amount or 0.0)
        paid = float(inv.amount_paid or 0.0)
        total_amount += tot
        total_outstanding += out
        total_collected += paid

        if inv.status == "Draft":
            draft_count += 1
            draft_amount += tot
        elif inv.status == "Confirmed":
            confirmed_count += 1
            confirmed_amount += tot
            if inv.due_date and inv.due_date < today and out > 0:
                overdue_count += 1
                overdue_amount += out
        elif inv.status == "Paid":
            paid_count += 1
            paid_amount += tot

    stats = {
        "total_count": len(invoices),
        "total_amount": round(total_amount, 2),
        "draft_count": draft_count,
        "draft_amount": round(draft_amount, 2),
        "confirmed_count": confirmed_count,
        "confirmed_amount": round(confirmed_amount, 2),
        "paid_count": paid_count,
        "paid_amount": round(paid_amount, 2),
        "overdue_count": overdue_count,
        "overdue_amount": round(overdue_amount, 2),
        "total_outstanding": round(total_outstanding, 2),
        "total_collected": round(total_collected, 2),
        # Nested format for tests
        "total_invoices": {"count": len(invoices), "amount": round(total_amount, 2)},
        "draft_invoices": {"count": draft_count, "amount": round(draft_amount, 2)},
        "confirmed_invoices": {"count": confirmed_count, "amount": round(confirmed_amount, 2)},
        "paid_invoices": {"count": paid_count, "amount": round(paid_amount, 2)},
        "overdue_invoices": {"count": overdue_count, "amount": round(overdue_amount, 2)}
    }

    return stats
