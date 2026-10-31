"""
Payment Service Layer (Module 6)
================================
Handles:
1. Unified payment recording (manual offline payments and Razorpay gateway captures).
2. Customer data boundary isolation (customers see only payments for their invoices).
3. Metric aggregations for the Payment Management dashboard.
4. Transactional reconciliation of invoice balances.
"""

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import or_, desc, asc

from models import db, Payment, Invoice, User


def quantize_money(amount):
    """Guarantees monetary values are strictly quantized to 2 decimal places."""
    if amount is None:
        return Decimal("0.00")
    if not isinstance(amount, Decimal):
        try:
            amount = Decimal(str(amount))
        except Exception:
            return Decimal("0.00")
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def record_manual_payment(invoice_id, data, user=None):
    """
    Records an offline/manual payment received by staff or admin.
    Updates amount_paid and transitions status to 'Paid' if outstanding becomes zero.
    """
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice:
        raise ValueError("Invoice not found")

    if invoice.status == "Cancelled":
        raise ValueError("Cannot record payment on a cancelled invoice")

    if invoice.status == "Draft":
        raise ValueError("Cannot record payment on a Draft invoice. Invoice must be Confirmed.")

    if invoice.status == "Paid" and (invoice.outstanding_amount or Decimal("0.00")) <= Decimal("0.00"):
        raise ValueError("Invoice is already fully paid")

    amount_raw = data.get("amount")
    if not amount_raw:
        raise ValueError("Payment amount is required")

    try:
        pay_amount = quantize_money(amount_raw)
    except Exception:
        raise ValueError("Invalid payment amount format")

    if pay_amount <= Decimal("0.00"):
        raise ValueError("Payment amount must be greater than zero")

    outstanding = invoice.outstanding_amount or Decimal("0.00")
    if pay_amount > outstanding:
        raise ValueError(f"Payment amount (₹{pay_amount:.2f}) cannot exceed outstanding amount (₹{outstanding:.2f})")

    pay_date_str = data.get("payment_date")
    pay_date = date.fromisoformat(pay_date_str) if pay_date_str else date.today()

    payment = Payment(
        invoice_id=invoice.id,
        amount=pay_amount,
        currency="INR",
        payment_method=data.get("payment_method", "Bank Transfer"),
        payment_source="manual",
        status="captured",
        payment_date=pay_date,
        reference_number=data.get("reference_number", "").strip(),
        notes=data.get("notes", "").strip(),
        created_by_id=user.id if user else None
    )
    db.session.add(payment)

    # Reconcile invoice balances
    invoice.amount_paid = quantize_money(Decimal(str(invoice.amount_paid or 0)) + pay_amount)
    invoice.outstanding_amount = quantize_money(max(Decimal("0.00"), Decimal(str(invoice.total_amount or 0)) - invoice.amount_paid))

    if invoice.outstanding_amount <= Decimal("0.00"):
        invoice.status = "Paid"

    invoice.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return payment, invoice


def list_payments(filters=None, current_user=None):
    """
    Retrieves filtered and paginated payment records.
    Enforces customer isolation (customers only see their own invoice payments).
    """
    filters = filters or {}
    query = Payment.query.join(Invoice, Payment.invoice_id == Invoice.id).join(User, Invoice.customer_id == User.id)

    # Role scoping
    if current_user and current_user.role == "customer":
        query = query.filter(Invoice.customer_id == current_user.id)
    elif filters.get("customer_id"):
        try:
            cid = int(filters["customer_id"])
            query = query.filter(Invoice.customer_id == cid)
        except (ValueError, TypeError):
            pass

    # Filter by specific invoice
    if filters.get("invoice_id"):
        try:
            inv_id = int(filters["invoice_id"])
            query = query.filter(Payment.invoice_id == inv_id)
        except (ValueError, TypeError):
            pass

    # Search filter
    search = (filters.get("search") or "").strip()
    if search:
        search_fmt = f"%{search}%"
        query = query.filter(
            or_(
                Payment.reference_number.ilike(search_fmt),
                Payment.razorpay_payment_id.ilike(search_fmt),
                Payment.razorpay_order_id.ilike(search_fmt),
                Invoice.invoice_number.ilike(search_fmt),
                User.first_name.ilike(search_fmt),
                User.last_name.ilike(search_fmt),
                User.email.ilike(search_fmt)
            )
        )

    # Method and source filters
    method = (filters.get("payment_method") or "").strip()
    if method and method.lower() != "all":
        query = query.filter(Payment.payment_method.ilike(method))

    source = (filters.get("payment_source") or "").strip()
    if source and source.lower() != "all":
        query = query.filter(Payment.payment_source == source.lower())

    status = (filters.get("status") or "").strip()
    if status and status.lower() != "all":
        query = query.filter(Payment.status == status.lower())

    # Date filters
    if filters.get("start_date"):
        try:
            s_date = date.fromisoformat(filters["start_date"])
            query = query.filter(Payment.payment_date >= s_date)
        except ValueError:
            pass

    if filters.get("end_date"):
        try:
            e_date = date.fromisoformat(filters["end_date"])
            query = query.filter(Payment.payment_date <= e_date)
        except ValueError:
            pass

    query = query.order_by(desc(Payment.payment_date), desc(Payment.id))

    try:
        page = max(1, int(filters.get("page", 1)))
        limit = min(100, max(1, int(filters.get("limit", filters.get("per_page", 20)))))
    except (ValueError, TypeError):
        page = 1
        limit = 20

    total_records = query.count()
    payments = query.offset((page - 1) * limit).limit(limit).all()
    total_pages = (total_records + limit - 1) // limit if total_records > 0 else 1

    return {
        "payments": [p.to_dict() for p in payments],
        "pagination": {
            "page": page,
            "limit": limit,
            "per_page": limit,
            "total": total_records,
            "total_records": total_records,
            "pages": total_pages,
            "total_pages": total_pages
        }
    }


def get_payment_statistics(customer_id=None):
    """Computes summary statistics for Payment Management dashboard."""
    query = Payment.query.join(Invoice, Payment.invoice_id == Invoice.id)
    if customer_id:
        query = query.filter(Invoice.customer_id == customer_id)

    payments = query.all()

    total_collected = Decimal("0.00")
    successful_count = 0
    pending_count = 0
    failed_count = 0

    for p in payments:
        if p.status == "captured":
            successful_count += 1
            total_collected += Decimal(str(p.amount or 0))
        elif p.status == "pending":
            pending_count += 1
        elif p.status == "failed":
            failed_count += 1

    # Compute outstanding receivables
    inv_query = Invoice.query.filter(Invoice.status == "Confirmed")
    if customer_id:
        inv_query = inv_query.filter(Invoice.customer_id == customer_id)
    invoices = inv_query.all()
    total_outstanding = sum([Decimal(str(inv.outstanding_amount or 0)) for inv in invoices])

    return {
        "total_payments": len(payments),
        "successful_payments": successful_count,
        "pending_payments": pending_count,
        "failed_payments": failed_count,
        "total_collected": float(quantize_money(total_collected)),
        "outstanding_receivables": float(quantize_money(total_outstanding))
    }
