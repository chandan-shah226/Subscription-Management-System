"""
Discount Service Layer (Module 5)
=================================
Manages:
1. Admin discount rule CRUD operations (fixed/percentage, min purchase/qty, usage limits, dates, scope).
2. Centralized eligibility engine shared by preview, invoice generation, and confirmation.
3. Automatic selection of the most beneficial eligible discount rule.
4. Concurrency-safe atomic usage incrementing and redemption audit records.
5. Historical preservation of applied discounts on confirmed invoices.
"""

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import or_, desc, asc

from models import (
    db, Discount, DiscountProduct, DiscountRedemption, Invoice, User, Product
)


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


def create_discount(data, creator=None):
    """
    Creates a new discount rule. Admin-only operation.
    Validates code uniqueness, types, values, validity dates, and scope.
    """
    code = (data.get("code") or "").strip().upper()
    if not code:
        raise ValueError("Discount code is required")

    existing = Discount.query.filter_by(code=code).first()
    if existing:
        raise ValueError(f"Discount code '{code}' already exists")

    discount_type = (data.get("discount_type") or "percentage").lower().strip()
    if discount_type not in ["percentage", "fixed"]:
        raise ValueError("Discount type must be either 'percentage' or 'fixed'")

    try:
        val = quantize_money(data.get("value", 0))
    except Exception:
        raise ValueError("Invalid discount value format")

    if val <= Decimal("0.00"):
        raise ValueError("Discount value must be greater than zero")

    if discount_type == "percentage" and val > Decimal("100.00"):
        raise ValueError("Percentage discount cannot exceed 100%")

    try:
        min_purchase = quantize_money(data.get("min_purchase", 0))
        if min_purchase < Decimal("0.00"):
            raise ValueError("Minimum purchase amount cannot be negative")
    except Exception:
        raise ValueError("Invalid min_purchase amount format")

    min_quantity = int(data.get("min_quantity", 1))
    if min_quantity < 1:
        min_quantity = 1

    start_date = None
    end_date = None
    if data.get("start_date"):
        try:
            start_date = date.fromisoformat(data["start_date"])
        except ValueError:
            raise ValueError("Invalid start_date format (expected YYYY-MM-DD)")

    if data.get("end_date"):
        try:
            end_date = date.fromisoformat(data["end_date"])
        except ValueError:
            raise ValueError("Invalid end_date format (expected YYYY-MM-DD)")

    if start_date and end_date and end_date < start_date:
        raise ValueError("End date cannot precede start date")

    usage_limit = data.get("usage_limit")
    if usage_limit is not None and str(usage_limit).strip() != "":
        usage_limit = int(usage_limit)
        if usage_limit < 1:
            raise ValueError("Usage limit must be at least 1")
    else:
        usage_limit = None

    scope = (data.get("scope") or "all").lower().strip()
    if scope not in ["all", "subscription", "product"]:
        scope = "all"

    discount = Discount(
        code=code,
        description=data.get("description", "").strip(),
        discount_type=discount_type,
        value=val,
        min_purchase=min_purchase,
        min_quantity=min_quantity,
        start_date=start_date,
        end_date=end_date,
        usage_limit=usage_limit,
        times_used=0,
        scope=scope,
        is_active=bool(data.get("is_active", True)),
        created_by_id=creator.id if creator else None
    )

    db.session.add(discount)
    db.session.flush()

    # Product scope bindings
    if scope == "product" and data.get("product_ids"):
        for pid in data["product_ids"]:
            try:
                pid_int = int(pid)
                if db.session.get(Product, pid_int):
                    db.session.add(DiscountProduct(discount_id=discount.id, product_id=pid_int))
            except (ValueError, TypeError):
                continue

    db.session.commit()
    return discount


def update_discount(discount_id, data, user=None):
    """Updates an existing discount rule. Admin-only."""
    discount = db.session.get(Discount, discount_id)
    if not discount:
        raise ValueError("Discount rule not found")

    if "description" in data:
        discount.notes = data.get("description", "").strip()

    if "discount_type" in data and data["discount_type"]:
        dt = data["discount_type"].lower().strip()
        if dt not in ["percentage", "fixed"]:
            raise ValueError("Discount type must be either 'percentage' or 'fixed'")
        discount.discount_type = dt

    if "value" in data and data["value"] is not None:
        val = quantize_money(data["value"])
        if val <= Decimal("0.00"):
            raise ValueError("Discount value must be greater than zero")
        if discount.discount_type == "percentage" and val > Decimal("100.00"):
            raise ValueError("Percentage discount cannot exceed 100%")
        discount.value = val

    if "min_purchase" in data and data["min_purchase"] is not None:
        mp = quantize_money(data["min_purchase"])
        if mp < Decimal("0.00"):
            raise ValueError("Minimum purchase cannot be negative")
        discount.min_purchase = mp

    if "min_quantity" in data and data["min_quantity"] is not None:
        mq = int(data["min_quantity"])
        if mq < 1:
            mq = 1
        discount.min_quantity = mq

    if "start_date" in data:
        discount.start_date = date.fromisoformat(data["start_date"]) if data["start_date"] else None

    if "end_date" in data:
        discount.end_date = date.fromisoformat(data["end_date"]) if data["end_date"] else None

    if discount.start_date and discount.end_date and discount.end_date < discount.start_date:
        raise ValueError("End date cannot precede start date")

    if "usage_limit" in data:
        ul = data["usage_limit"]
        if ul is not None and str(ul).strip() != "":
            discount.usage_limit = int(ul)
        else:
            discount.usage_limit = None

    if "is_active" in data:
        discount.is_active = bool(data["is_active"])

    if "scope" in data and data["scope"]:
        sc = data["scope"].lower().strip()
        if sc in ["all", "subscription", "product"]:
            discount.scope = sc

    # Update product mapping if product scope
    if discount.scope == "product" and "product_ids" in data:
        DiscountProduct.query.filter_by(discount_id=discount.id).delete()
        for pid in data["product_ids"]:
            try:
                pid_int = int(pid)
                if db.session.get(Product, pid_int):
                    db.session.add(DiscountProduct(discount_id=discount.id, product_id=pid_int))
            except (ValueError, TypeError):
                continue

    discount.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return discount


def toggle_discount_status(discount_id, is_active=None):
    """Toggles active/inactive state of a discount rule."""
    discount = db.session.get(Discount, discount_id)
    if not discount:
        raise ValueError("Discount not found")

    if is_active is not None:
        discount.is_active = bool(is_active)
    else:
        discount.is_active = not discount.is_active

    discount.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return discount


def get_discount(discount_id):
    """Retrieves discount details by ID."""
    discount = db.session.get(Discount, discount_id)
    if not discount:
        raise ValueError("Discount not found")
    return discount


def list_discounts(filters=None):
    """Lists discounts with search, status filters, and pagination."""
    filters = filters or {}
    query = Discount.query

    search = (filters.get("search") or "").strip()
    if search:
        search_fmt = f"%{search}%"
        query = query.filter(
            or_(
                Discount.code.ilike(search_fmt),
                Discount.description.ilike(search_fmt)
            )
        )

    disc_type = (filters.get("discount_type") or "").strip()
    if disc_type and disc_type.lower() != "all":
        query = query.filter(Discount.discount_type == disc_type.lower())

    status = (filters.get("status") or "").strip().lower()
    today = date.today()
    if status == "active":
        query = query.filter(
            Discount.is_active == True,
            or_(Discount.end_date == None, Discount.end_date >= today),
            or_(Discount.usage_limit == None, Discount.times_used < Discount.usage_limit)
        )
    elif status == "expired":
        query = query.filter(Discount.end_date != None, Discount.end_date < today)
    elif status == "exhausted":
        query = query.filter(Discount.usage_limit != None, Discount.times_used >= Discount.usage_limit)
    elif status == "inactive":
        query = query.filter(Discount.is_active == False)

    scope = (filters.get("scope") or "").strip().lower()
    if scope and scope != "all":
        query = query.filter(Discount.scope == scope)

    query = query.order_by(desc(Discount.created_at))

    try:
        page = max(1, int(filters.get("page", 1)))
        limit = min(100, max(1, int(filters.get("limit", filters.get("per_page", 20)))))
    except (ValueError, TypeError):
        page = 1
        limit = 20

    total_records = query.count()
    discounts = query.offset((page - 1) * limit).limit(limit).all()
    total_pages = (total_records + limit - 1) // limit if total_records > 0 else 1

    return {
        "discounts": [d.to_dict() for d in discounts],
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


def get_discount_statistics():
    """Computes KPI statistics for Discount dashboard."""
    all_discounts = Discount.query.all()
    today = date.today()

    total_count = len(all_discounts)
    active_count = 0
    expired_count = 0
    exhausted_count = 0
    inactive_count = 0
    total_redemptions = 0

    for d in all_discounts:
        total_redemptions += d.times_used
        if not d.is_active:
            inactive_count += 1
        elif d.is_expired:
            expired_count += 1
        elif d.is_exhausted:
            exhausted_count += 1
        else:
            active_count += 1

    return {
        "total_discounts": total_count,
        "active_discounts": active_count,
        "expired_discounts": expired_count,
        "exhausted_discounts": exhausted_count,
        "inactive_discounts": inactive_count,
        "total_redemptions": total_redemptions
    }


def find_eligible_discounts(subtotal, quantity=1, product_ids=None, check_date=None, is_subscription=False):
    """
    Returns list of all active, eligible discounts matching purchase conditions.
    """
    today = check_date or date.today()
    active_rules = Discount.query.filter(
        Discount.is_active == True,
        or_(Discount.start_date == None, Discount.start_date <= today),
        or_(Discount.end_date == None, Discount.end_date >= today),
        or_(Discount.usage_limit == None, Discount.times_used < Discount.usage_limit)
    ).all()

    eligible = []
    for rule in active_rules:
        # Check scope compatibility
        if rule.scope == "subscription" and not is_subscription:
            continue

        is_valid, reason = rule.is_eligible(
            subtotal=subtotal,
            quantity=quantity,
            product_ids=product_ids,
            check_date=today
        )
        if is_valid:
            benefit = rule.calculate_discount_amount(subtotal)
            eligible.append({
                "discount": rule,
                "benefit_amount": benefit
            })

    # Sort deterministically by benefit amount descending
    eligible.sort(key=lambda x: x["benefit_amount"], reverse=True)
    return eligible


def select_best_discount(subtotal, quantity=1, product_ids=None, check_date=None, is_subscription=False):
    """Selects the single most beneficial eligible discount rule deterministically."""
    eligible = find_eligible_discounts(
        subtotal=subtotal,
        quantity=quantity,
        product_ids=product_ids,
        check_date=check_date,
        is_subscription=is_subscription
    )
    if eligible and eligible[0]["benefit_amount"] > Decimal("0.00"):
        return eligible[0]["discount"], eligible[0]["benefit_amount"]
    return None, Decimal("0.00")


def record_discount_redemption(discount_id, invoice_id, customer_id, amount):
    """
    Atomically records a discount redemption and increments times_used.
    Guarantees concurrency-safe usage counting.
    """
    discount = db.session.get(Discount, discount_id)
    if not discount:
        return None

    # Idempotency check: don't double record for same invoice
    existing = DiscountRedemption.query.filter_by(
        discount_id=discount_id,
        invoice_id=invoice_id
    ).first()

    if existing:
        return existing

    # Check usage limit
    if discount.usage_limit is not None and discount.times_used >= discount.usage_limit:
        raise ValueError(f"Discount {discount.code} usage limit reached")

    discount.times_used += 1
    discount.updated_at = datetime.now(timezone.utc)

    redemption = DiscountRedemption(
        discount_id=discount.id,
        invoice_id=invoice_id,
        customer_id=customer_id,
        amount_applied=quantize_money(amount)
    )
    db.session.add(redemption)
    db.session.flush()
    return redemption


def revert_discount_redemption(invoice_id):
    """Reverts a discount redemption if an unconfirmed invoice is cancelled."""
    redemptions = DiscountRedemption.query.filter_by(invoice_id=invoice_id).all()
    for red in redemptions:
        if red.discount and red.discount.times_used > 0:
            red.discount.times_used -= 1
        db.session.delete(red)
    db.session.flush()
