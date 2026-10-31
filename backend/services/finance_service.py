"""Finance reporting queries for Modules 7 and 8.

All financial aggregation happens in the database. The API never sends raw
subscription, invoice or payment dumps to the browser.
"""

from __future__ import annotations

import calendar
import threading
import time
from datetime import date
from decimal import Decimal, InvalidOperation
from math import ceil
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from models import db, Customer, Invoice, Payment, Subscription

SUCCESSFUL = "successful"
INVOICE_STATUSES = {"draft", "confirmed", "paid"}
PAYMENT_STATUSES = {"successful", "pending", "failed"}


class ApiError(Exception):
    """Raised for invalid API input; rendered as JSON by the error handler."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------
def parse_date(value: str | None, field_name: str) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ApiError(f"Invalid '{field_name}': expected YYYY-MM-DD.") from exc


def parse_amount(value: str | None, field_name: str) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ApiError(f"Invalid '{field_name}': expected a number.") from exc
    if amount < 0:
        raise ApiError(f"Invalid '{field_name}': must not be negative.")
    return amount


def validate_range(from_date: date | None, to_date: date | None) -> None:
    if from_date and to_date and from_date > to_date:
        raise ApiError("'from' must be on or before 'to'.")


# ---------------------------------------------------------------------------
# Tiny in-process TTL cache for read-only aggregates
# ---------------------------------------------------------------------------
_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = threading.Lock()


def cached(key: str, ttl_seconds: int, producer):
    if ttl_seconds <= 0:
        return producer()

    now = time.monotonic()
    with _cache_lock:
        entry = _cache.get(key)
        if entry and entry[0] > now:
            return entry[1]

    value = producer()
    with _cache_lock:
        _cache[key] = (now + ttl_seconds, value)
    return value


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


# ---------------------------------------------------------------------------
# Shared SQL expressions
# ---------------------------------------------------------------------------
def _paid_subquery():
    """Total successful payments per invoice (partial payments supported)."""
    return (
        db.session.query(
            Payment.invoice_id.label("invoice_id"),
            func.coalesce(func.sum(Payment.amount), 0).label("paid_amount"),
        )
        .filter(Payment.status == SUCCESSFUL)
        .group_by(Payment.invoice_id)
        .subquery()
    )


# ---------------------------------------------------------------------------
# KPI summary
# ---------------------------------------------------------------------------
def summary(from_date: date | None = None, to_date: date | None = None) -> dict[str, Any]:
    """Return the four finance KPI values.

    Date range semantics (documented in the README):
    * revenue_received  -> successful payments with paid_on in [from, to]
    * active_subscriptions / outstanding_amount / overdue_invoice_count
      -> current values as of today (balance-style metrics)
    """
    today = date.today()

    active_subscriptions = (
        db.session.query(func.count(Subscription.id))
        .filter(Subscription.status == "active")
        .scalar()
        or 0
    )

    revenue_query = db.session.query(
        func.coalesce(func.sum(Payment.amount), 0)
    ).filter(Payment.status == SUCCESSFUL)
    if from_date:
        revenue_query = revenue_query.filter(Payment.paid_on >= from_date)
    if to_date:
        revenue_query = revenue_query.filter(Payment.paid_on <= to_date)
    revenue_received = revenue_query.scalar() or 0

    paid = _paid_subquery()
    remaining = Invoice.amount - func.coalesce(paid.c.paid_amount, 0)

    outstanding_amount = (
        db.session.query(func.coalesce(func.sum(remaining), 0))
        .select_from(Invoice)
        .outerjoin(paid, paid.c.invoice_id == Invoice.id)
        .filter(Invoice.status != "draft", remaining > 0)
        .scalar()
        or 0
    )

    overdue_invoice_count = (
        db.session.query(func.count(Invoice.id))
        .select_from(Invoice)
        .outerjoin(paid, paid.c.invoice_id == Invoice.id)
        .filter(Invoice.status != "draft", Invoice.due_date < today, remaining > 0)
        .scalar()
        or 0
    )

    return {
        "active_subscriptions": int(active_subscriptions),
        "revenue_received": float(revenue_received),
        "outstanding_amount": float(outstanding_amount),
        "overdue_invoice_count": int(overdue_invoice_count),
        "currency": "INR",
        "as_of": today.isoformat(),
        "range": {
            "from": from_date.isoformat() if from_date else None,
            "to": to_date.isoformat() if to_date else None,
        },
    }


# ---------------------------------------------------------------------------
# Revenue series
# ---------------------------------------------------------------------------
def _period_rows(granularity: str, from_date: date | None, to_date: date | None):
    if granularity == "month":
        expr = func.strftime("%Y-%m", Payment.paid_on)
    else:
        expr = func.strftime("%Y", Payment.paid_on)

    query = db.session.query(
        expr.label("period"),
        func.coalesce(func.sum(Payment.amount), 0).label("revenue"),
    ).filter(Payment.status == SUCCESSFUL)

    if from_date:
        query = query.filter(Payment.paid_on >= from_date)
    if to_date:
        query = query.filter(Payment.paid_on <= to_date)

    rows = query.group_by(expr).order_by(expr).all()
    return {str(row.period): float(row.revenue or 0) for row in rows}


def _month_periods(from_date: date | None, to_date: date | None):
    if from_date and to_date:
        start = date(from_date.year, from_date.month, 1)
        end = date(to_date.year, to_date.month, 1)
    else:
        end = date.today().replace(day=1)
        start = date(end.year - 1, end.month, 1)

    periods = []
    cursor = start
    while cursor <= end:
        periods.append(
            (
                f"{cursor.year:04d}-{cursor.month:02d}",
                f"{calendar.month_abbr[cursor.month]} {cursor.year}",
            )
        )
        cursor = (
            date(cursor.year + 1, 1, 1)
            if cursor.month == 12
            else date(cursor.year, cursor.month + 1, 1)
        )
    return periods


def revenue_series(
    from_date: date | None = None,
    to_date: date | None = None,
    granularity: str = "month",
) -> dict[str, Any]:
    if granularity not in {"month", "year"}:
        raise ApiError("Invalid 'granularity': expected 'month' or 'year'.")

    values = _period_rows(granularity, from_date, to_date)

    if granularity == "month":
        periods = _month_periods(from_date, to_date)
        if len(periods) > 60:
            raise ApiError("Date range too large for a monthly chart (max 60 months).")
    else:
        start_year = from_date.year if from_date else (to_date.year if to_date else date.today().year - 3)
        end_year = to_date.year if to_date else date.today().year
        if end_year - start_year > 20:
            raise ApiError("Date range too large for a yearly chart (max 20 years).")
        periods = [(str(year), str(year)) for year in range(start_year, end_year + 1)]

    items = [
        {"period": period, "label": label, "revenue": values.get(period, 0.0)}
        for period, label in periods
    ]

    return {
        "granularity": granularity,
        "currency": "INR",
        "items": items,
    }


# ---------------------------------------------------------------------------
# Invoice report
# ---------------------------------------------------------------------------
def list_invoices(
    *,
    page: int = 1,
    per_page: int = 20,
    status: str | None = None,
    customer: str | None = None,
    customer_id: int | None = None,
    date_field: str = "invoice_date",
    from_date: date | None = None,
    to_date: date | None = None,
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
    q: str | None = None,
    sort: str = "invoice_date",
    order: str = "desc",
) -> dict[str, Any]:
    today = date.today()
    paid = _paid_subquery()
    paid_amount = func.coalesce(paid.c.paid_amount, 0).label("paid_amount")
    outstanding = (Invoice.amount - func.coalesce(paid.c.paid_amount, 0)).label(
        "outstanding"
    )

    query = (
        db.session.query(Invoice, paid_amount, outstanding)
        .outerjoin(paid, paid.c.invoice_id == Invoice.id)
        .options(joinedload(Invoice.customer))
    )

    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Invoice.number.ilike(like),
                Invoice.customer.has(Customer.name.ilike(like)),
            )
        )

    if customer:
        query = query.filter(Invoice.customer.has(Customer.name.ilike(f"%{customer.strip()}%")))
    if customer_id is not None:
        query = query.filter(Invoice.customer_id == customer_id)

    if status and status != "all":
        if status == "overdue":
            query = query.filter(
                Invoice.status != "draft", Invoice.due_date < today, outstanding > 0
            )
        elif status in INVOICE_STATUSES:
            query = query.filter(Invoice.status == status)
        else:
            raise ApiError(
                "Invalid 'status': expected all, draft, confirmed, paid or overdue."
            )

    if date_field not in {"invoice_date", "due_date"}:
        raise ApiError("Invalid 'date_field': expected invoice_date or due_date.")
    date_column = Invoice.due_date if date_field == "due_date" else Invoice.invoice_date
    if from_date:
        query = query.filter(date_column >= from_date)
    if to_date:
        query = query.filter(date_column <= to_date)

    if amount_min is not None:
        query = query.filter(Invoice.amount >= amount_min)
    if amount_max is not None:
        query = query.filter(Invoice.amount <= amount_max)
    if amount_min is not None and amount_max is not None and amount_min > amount_max:
        raise ApiError("'amount_min' must not be greater than 'amount_max'.")

    sort_columns = {
        "invoice_date": Invoice.invoice_date,
        "due_date": Invoice.due_date,
        "amount": Invoice.amount,
        "status": Invoice.status,
        "customer": Customer.name,
    }
    sort_column = sort_columns.get(sort)
    if sort_column is None:
        raise ApiError("Invalid 'sort' value.")
    if order not in {"asc", "desc"}:
        raise ApiError("Invalid 'order': expected asc or desc.")

    if sort == "customer":
        query = query.join(Invoice.customer)

    query = query.order_by(
        sort_column.asc() if order == "asc" else sort_column.desc(),
        Invoice.id.desc(),
    )

    total_records = query.order_by(None).count()
    rows = query.offset((page - 1) * per_page).limit(per_page).all()

    items = []
    for invoice, paid_value, outstanding_value in rows:
        paid_decimal = Decimal(paid_value or 0)
        outstanding_decimal = Decimal(outstanding_value or 0)
        display_status = invoice.status
        if invoice.status != "draft" and invoice.due_date < today and outstanding_decimal > 0:
            display_status = "overdue"

        items.append(
            {
                "id": invoice.id,
                "number": invoice.number,
                "customer": {
                    "id": invoice.customer.id,
                    "name": invoice.customer.name,
                    "company": invoice.customer.company,
                },
                "invoice_date": invoice.invoice_date.isoformat(),
                "due_date": invoice.due_date.isoformat(),
                "amount": float(invoice.amount),
                "paid_amount": float(paid_decimal),
                "outstanding": float(outstanding_decimal),
                "status": invoice.status,
                "display_status": display_status,
                "is_overdue": display_status == "overdue",
            }
        )

    return {
        "items": items,
        "page": page,
        "per_page": per_page,
        "total_records": total_records,
        "total_pages": ceil(total_records / per_page) if total_records else 0,
        "currency": "INR",
    }

# Payment report
# ---------------------------------------------------------------------------
def list_payments(
    *,
    page: int = 1,
    per_page: int = 20,
    status: str | None = "successful",
    method: str | None = None,
    customer: str | None = None,
    customer_id: int | None = None,
    invoice_number: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
    q: str | None = None,
    order: str = "desc",
) -> dict[str, Any]:
    query = db.session.query(Payment).options(
        joinedload(Payment.customer), joinedload(Payment.invoice)
    )

    if status and status != "all":
        if status not in PAYMENT_STATUSES:
            raise ApiError(
                "Invalid 'status': expected all, successful, pending or failed."
            )
        query = query.filter(Payment.status == status)

    if method:
        query = query.filter(Payment.method == method)

    if customer:
        query = query.filter(Payment.customer.has(Customer.name.ilike(f"%{customer.strip()}%")))
    if customer_id is not None:
        query = query.filter(Payment.customer_id == customer_id)

    if invoice_number:
        like = f"%{invoice_number.strip()}%"
        query = query.filter(Payment.invoice.has(Invoice.number.ilike(like)))

    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Payment.reference.ilike(like),
                Payment.customer.has(Customer.name.ilike(like)),
                Payment.invoice.has(Invoice.number.ilike(like)),
            )
        )

    if from_date:
        query = query.filter(Payment.paid_on >= from_date)
    if to_date:
        query = query.filter(Payment.paid_on <= to_date)

    if amount_min is not None:
        query = query.filter(Payment.amount >= amount_min)
    if amount_max is not None:
        query = query.filter(Payment.amount <= amount_max)
    if amount_min is not None and amount_max is not None and amount_min > amount_max:
        raise ApiError("'amount_min' must not be greater than 'amount_max'.")

    if order not in {"asc", "desc"}:
        raise ApiError("Invalid 'order': expected asc or desc.")

    query = query.order_by(
        Payment.paid_on.asc() if order == "asc" else Payment.paid_on.desc(),
        Payment.id.desc(),
    )

    total_records = query.order_by(None).count()
    rows = query.offset((page - 1) * per_page).limit(per_page).all()

    items = [
        {
            "id": payment.id,
            "reference": payment.reference,
            "customer": {
                "id": payment.customer.id,
                "name": payment.customer.name,
                "company": payment.customer.company,
            },
            "invoice_id": payment.invoice_id,
            "invoice_number": payment.invoice.number,
            "method": payment.method,
            "amount": float(payment.amount),
            "paid_on": payment.paid_on.isoformat(),
            "status": payment.status,
            "notes": payment.notes,
        }
        for payment in rows
    ]

    return {
        "items": items,
        "page": page,
        "per_page": per_page,
        "total_records": total_records,
        "total_pages": ceil(total_records / per_page) if total_records else 0,
        "currency": "INR",
    }


SUBSCRIPTION_STATUSES = {"active", "trial", "paused", "canceled", "expired"}


# ---------------------------------------------------------------------------
# Subscription reporting
# ---------------------------------------------------------------------------
def subscription_summary() -> dict[str, Any]:
    """Return counts and aggregate financial value by subscription status."""
    status_counts_rows = (
        db.session.query(
            Subscription.status,
            func.count(Subscription.id).label("count"),
            func.coalesce(func.sum(Subscription.amount), 0).label("total_value"),
        )
        .group_by(Subscription.status)
        .all()
    )

    by_status = {
        row.status: {
            "count": int(row.count),
            "total_value": float(row.total_value),
        }
        for row in status_counts_rows
    }

    for expected in ["active", "trial", "paused", "canceled", "expired"]:
        if expected not in by_status:
            by_status[expected] = {"count": 0, "total_value": 0.0}

    plan_breakdown_rows = (
        db.session.query(
            Subscription.product_name,
            Subscription.plan_name,
            func.count(Subscription.id).label("count"),
            func.coalesce(func.sum(Subscription.amount), 0).label("mrr_equivalent"),
        )
        .filter(Subscription.status == "active")
        .group_by(Subscription.product_name, Subscription.plan_name)
        .order_by(func.count(Subscription.id).desc())
        .limit(10)
        .all()
    )

    plans = [
        {
            "product_name": row.product_name,
            "plan_name": row.plan_name,
            "active_count": int(row.count),
            "total_value": float(row.mrr_equivalent),
        }
        for row in plan_breakdown_rows
    ]

    total_active = by_status["active"]["count"]
    total_active_mrr = by_status["active"]["total_value"]

    return {
        "total_active": total_active,
        "total_active_value": total_active_mrr,
        "by_status": by_status,
        "top_plans": plans,
        "currency": "INR",
    }


def list_subscriptions(
    *,
    page: int = 1,
    per_page: int = 20,
    status: str | None = None,
    product: str | None = None,
    customer_id: int | None = None,
    q: str | None = None,
    order: str = "desc",
) -> dict[str, Any]:
    query = db.session.query(Subscription)

    if status and status != "all":
        if status not in SUBSCRIPTION_STATUSES:
            raise ApiError(
                "Invalid 'status': expected all, active, trial, paused, canceled or expired."
            )
        query = query.filter(Subscription.status == status)

    if product:
        query = query.filter(Subscription.product_name.ilike(f"%{product.strip()}%"))

    if customer_id is not None:
        query = query.filter(Subscription.customer_id == customer_id)

    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Subscription.product_name.ilike(like),
                Subscription.plan_name.ilike(like),
            )
        )

    if order not in {"asc", "desc"}:
        raise ApiError("Invalid 'order': expected asc or desc.")

    query = query.order_by(
        Subscription.renews_on.asc() if order == "asc" else Subscription.renews_on.desc(),
        Subscription.id.desc(),
    )

    total_records = query.order_by(None).count()
    rows = query.offset((page - 1) * per_page).limit(per_page).all()

    items = [
        {
            "id": sub.id,
            "customer_id": sub.customer_id,
            "product_name": sub.product_name,
            "plan_name": sub.plan_name,
            "status": sub.status,
            "amount": float(sub.amount),
            "billing_cycle": sub.billing_cycle,
            "started_on": sub.started_on.isoformat(),
            "renews_on": sub.renews_on.isoformat(),
        }
        for sub in rows
    ]

    return {
        "items": items,
        "page": page,
        "per_page": per_page,
        "total_records": total_records,
        "total_pages": ceil(total_records / per_page) if total_records else 0,
        "currency": "INR",
    }

